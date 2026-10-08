import asyncio
import json
import logging
import math
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.evaluation import run_evaluations
from app.investigator import derive_root_cause
from app.models import (
    ApprovalRequest,
    ChaosConfig,
    Evidence,
    Health,
    Incident,
    IncidentCreate,
    IncidentStatus,
    Remediation,
    RetrievedRunbook,
    RunMetrics,
    Source,
    TimelineEvent,
    ToolTrace,
    now_utc,
)
from app.retrieval import retrieve
from app.store import Store

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("sentinelgraph")
request_context: ContextVar[str] = ContextVar("request_id", default="startup")
ROOT = Path(__file__).parent
SCENARIOS = json.loads((ROOT / "data" / "scenarios.v1.json").read_text(encoding="utf-8"))
SCENARIO_BY_ID = {scenario["id"]: scenario for scenario in SCENARIOS["scenarios"]}
SOURCES = list(Source)
TENANT = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")
ALLOWED_REMEDIATIONS = {"rollback", "failover", "circuit_breaker"}


def create_app(store: Store | None = None, prometheus_metrics=None, openai_analysis=None) -> FastAPI:
    db = store or Store(Path(os.getenv("SENTINELGRAPH_DB", "data/sentinelgraph.sqlite3")))
    if prometheus_metrics is None:
        prometheus_url = os.getenv("SENTINELGRAPH_PROMETHEUS_URL", "").strip()
        prometheus_query = os.getenv("SENTINELGRAPH_PROMETHEUS_QUERY", "").strip()
        prometheus_token = os.getenv("SENTINELGRAPH_PROMETHEUS_TOKEN", "").strip()
        if prometheus_url or prometheus_query or prometheus_token:
            if not prometheus_url or not prometheus_query:
                raise RuntimeError("Set both SENTINELGRAPH_PROMETHEUS_URL and SENTINELGRAPH_PROMETHEUS_QUERY.")
            from app.prometheus import PrometheusMetrics

            prometheus_metrics = PrometheusMetrics(prometheus_url, prometheus_query, prometheus_token or None)
    analysis_provider = os.getenv("SENTINELGRAPH_ANALYSIS_PROVIDER", "demo").strip().lower() or "demo"
    if analysis_provider not in {"demo", "openai"}:
        raise RuntimeError("SENTINELGRAPH_ANALYSIS_PROVIDER must be 'demo' or 'openai'.")
    if openai_analysis is None and analysis_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when SENTINELGRAPH_ANALYSIS_PROVIDER=openai.")
        from app.openai_analysis import OpenAIAnalysis

        model = os.getenv("SENTINELGRAPH_OPENAI_MODEL", "").strip() or "gpt-6.1-sol"
        openai_analysis = OpenAIAnalysis(api_key, model)

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        try:
            db.recover_interrupted()
            yield
        finally:
            analyzer = _application.state.openai_analysis
            if analyzer:
                close = getattr(analyzer, "close", None)
                if close:
                    await close()

    application = FastAPI(
        title="SentinelGraph", version="1.0.0", docs_url="/api/docs", redoc_url=None, lifespan=lifespan
    )
    application.state.store = db
    application.state.tasks = set()
    application.state.chaos = {}
    application.state.prometheus_metrics = prometheus_metrics
    application.state.openai_analysis = openai_analysis

    @application.middleware("http")
    async def observe_request(request: Request, call_next):
        request_id = uuid.uuid4().hex
        token = request_context.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            logger.info(json.dumps({"request_id": request_id, "method": request.method, "path": request.url.path, "duration_ms": elapsed}))
            request_context.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

    def tenant_or_400(tenant_id: str) -> str:
        if not TENANT.fullmatch(tenant_id):
            raise HTTPException(400, "Tenant ID must contain 1-40 letters, digits, _ or -.")
        return tenant_id

    def load_incident(incident_id: str, tenant_id: str) -> Incident:
        incident = db.get(incident_id, tenant_or_400(tenant_id))
        if not incident:
            raise HTTPException(404, "Incident not found.")
        return incident

    def event(incident: Incident, kind: str, message: str) -> None:
        incident.timeline.append(TimelineEvent(kind=kind, message=message, request_id=request_context.get()))

    def trace(incident: Incident, tool: Source | str, status: str, **kwargs) -> ToolTrace:
        return ToolTrace(
            id=uuid.uuid4().hex,
            incident_id=incident.id,
            agent_run_id=incident.agent_run_id,
            request_id=request_context.get(),
            tool=tool,
            status=status,
            **kwargs,
        )

    async def investigate(incident: Incident, scenario: dict, chaos: ChaosConfig) -> None:
        started = time.perf_counter()
        failures = set(chaos.fail_sources)
        model_tokens = 0
        model_attempted = False
        try:
            for source in SOURCES:
                call = trace(incident, source, "running")
                incident.tool_trace.append(call)
                event(incident, "tool", f"Read-only {source.value} adapter started.")
                db.save(incident)
                await asyncio.sleep(0.16)
                if source in failures:
                    call.status = "failed"
                    call.error = f"{source.value} source unavailable (chaos injection)."
                    incident.failed_sources.append(source)
                    event(incident, "failure", f"{source.value} evidence source failed explicitly; no evidence was recorded for it.")
                elif source == chaos.malformed_source:
                    # Strict schema validation makes malformed adapter output an explicit tool failure.
                    try:
                        Evidence.model_validate({"id": "malformed", "source": source.value, "summary": "bad", "observed_value": "bad", "unexpected": "rejected"})
                    except ValidationError:
                        call.status = "failed"
                        call.error = "Malformed adapter output rejected by the strict evidence schema."
                        incident.failed_sources.append(source)
                        event(incident, "failure", f"{source.value} malformed adapter output rejected; no evidence was recorded for it.")
                    else:
                        raise ValueError("Chaos malformed-output control did not produce malformed output.")
                else:
                    try:
                        if source == Source.metrics and application.state.prometheus_metrics:
                            evidence = await application.state.prometheus_metrics.collect(incident.id)
                        else:
                            evidence = Evidence(
                                id=f"ev-{incident.id[:8]}-{source.value}",
                                source=source,
                                summary=f"{source.value.title()} observation for {scenario['service']}",
                                observed_value=scenario["signals"][source.value],
                            )
                    except RuntimeError as exc:
                        call.status = "failed"
                        call.error = str(exc)
                        incident.failed_sources.append(source)
                        event(incident, "failure", "Prometheus metrics query failed; no live evidence was recorded.")
                    else:
                        incident.evidence.append(evidence)
                        call.status = "succeeded"
                        call.evidence_id = evidence.id
                        event(
                            incident,
                            "evidence",
                            f"{source.value} returned {evidence.provenance.lower()} evidence {evidence.id}.",
                        )
                call.completed_at = now_utc()
                db.save(incident)
                if chaos.simulate_worker_crash and source == Source.metrics:
                    raise RuntimeError("Simulated investigation worker exit after the first persisted tool result.")

            query = " ".join([incident.symptom, *(item.observed_value for item in incident.evidence)])
            lookup = trace(incident, "runbooks", "running")
            incident.tool_trace.append(lookup)
            event(incident, "tool", "Hybrid runbook retrieval started (BM25 + TF-IDF cosine; service-filtered).")
            db.save(incident)
            await asyncio.sleep(0.08)
            found = retrieve(query, incident.service)
            lookup.completed_at = now_utc()
            if found:
                runbook_id, title, score = found
                incident.runbook = RetrievedRunbook(id=runbook_id, title=title, score=score, version="1.0.0")
                lookup.status = "succeeded"
                event(incident, "evidence", f"Runbook {runbook_id} retrieved; marked untrusted guidance.")
            else:
                lookup.status = "failed"
                lookup.error = "No service-matched runbook had a positive retrieval score."
                event(incident, "failure", "No matching runbook was retrieved; remediation remains blocked.")
            db.save(incident)

            if application.state.openai_analysis and incident.evidence:
                model_attempted = True
                analysis = trace(incident, "model_analysis", "running", permission="read")
                incident.tool_trace.append(analysis)
                event(incident, "tool", "OpenAI advisory started; symptom and evidence are sent to the configured provider.")
                db.save(incident)
                try:
                    incident.advisory, model_tokens = await application.state.openai_analysis.analyze(
                        incident.symptom, incident.evidence
                    )
                except RuntimeError as exc:
                    analysis.status = "failed"
                    analysis.error = str(exc)
                    event(incident, "failure", "OpenAI advisory failed; deterministic policy remains in control.")
                else:
                    analysis.status = "succeeded"
                    event(incident, "analysis", "OpenAI advisory is available for human review; it does not change RCA or remediation policy.")
                analysis.completed_at = now_utc()
                db.save(incident)

            incident.root_cause, incident.quality = derive_root_cause(scenario, incident.evidence, set(incident.failed_sources))
            supported = incident.root_cause.supported
            if supported:
                event(incident, "analysis", f"Root cause supported by {len(incident.root_cause.citations)} required evidence sources; confidence {incident.root_cause.confidence:.0%}.")
            else:
                event(incident, "failure", "Evidence did not satisfy the scenario provenance and source policy; remediation is blocked.")

            truth = scenario["ground_truth"]
            if supported and incident.runbook:
                proposal = truth["remediation"]
                if proposal["action"] not in ALLOWED_REMEDIATIONS:
                    raise ValueError("Dataset remediation action is not in the safe allowlist.")
                incident.remediation = Remediation(**proposal)
                incident.status = IncidentStatus.awaiting_approval
                event(incident, "analysis", "Read-only investigation complete. A separate SRE approval is required before the simulated write action.")
            else:
                incident.status = IncidentStatus.blocked
                if supported:
                    incident.quality = "insufficient"
                    incident.root_cause.quality = "insufficient"
                if incident.remediation:
                    incident.remediation.status = "blocked"

            incident.completed_at = now_utc()
            incident.metrics = RunMetrics(
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                api_cost_usd=None if model_attempted else 0,
                cost_label="UNKNOWN" if model_attempted else "MEASURED",
                model_tokens=model_tokens,
                tool_calls=len(incident.tool_trace),
                failed_tools=sum(call.status == "failed" for call in incident.tool_trace),
            )
            db.save(incident)
        except asyncio.CancelledError:
            incident.status = IncidentStatus.blocked
            event(incident, "failure", "Investigation was cancelled; no remediation was run.")
            incident.completed_at = now_utc()
            db.save(incident)
            raise
        except Exception as exc:  # noqa: BLE001 - unexpected worker failures must fail closed
            incident.status = IncidentStatus.blocked
            incident.quality = "insufficient"
            failed_call = trace(incident, "orchestrator", "failed", completed_at=now_utc(), error=f"Investigation aborted ({type(exc).__name__}).")
            incident.tool_trace.append(failed_call)
            event(incident, "failure", f"Investigation failed explicitly: {type(exc).__name__}.")
            incident.completed_at = now_utc()
            incident.metrics = RunMetrics(
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                api_cost_usd=None if model_attempted else 0,
                cost_label="UNKNOWN" if model_attempted else "MEASURED",
                model_tokens=model_tokens,
                tool_calls=len(incident.tool_trace),
                failed_tools=sum(call.status == "failed" for call in incident.tool_trace),
            )
            db.save(incident)

    @application.get("/")
    async def home():
        return FileResponse(ROOT / "static" / "index.html")

    @application.get("/api/health", response_model=Health)
    async def health(x_tenant_id: str = Header("demo")):
        tenant = tenant_or_400(x_tenant_id)
        incidents = db.list(tenant)
        active = sum(1 for task in application.state.tasks if not task.done())
        unresolved = any(row.status != IncidentStatus.recovered for row in incidents)
        return Health(status="degraded" if unresolved else "healthy", active_investigations=active, scenario_count=len(SCENARIO_BY_ID))

    @application.get("/api/scenarios")
    async def scenarios():
        return [{"id": row["id"], "title": row["title"], "service": row["service"], "symptom": row["symptom"]} for row in SCENARIOS["scenarios"]]

    @application.get("/api/incidents", response_model=list[Incident])
    async def list_incidents(x_tenant_id: str = Header("demo")):
        return db.list(tenant_or_400(x_tenant_id))

    @application.post("/api/incidents", response_model=Incident, status_code=202)
    async def create_incident(
        payload: IncidentCreate,
        response: Response,
        x_tenant_id: str = Header("demo"),
        idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ):
        scenario = SCENARIO_BY_ID.get(payload.scenario_id)
        if not scenario:
            raise HTTPException(404, "Unknown deterministic scenario.")
        if idempotency_key is not None and (not 1 <= len(idempotency_key) <= 100 or not re.fullmatch(r"[a-zA-Z0-9._:-]+", idempotency_key)):
            raise HTTPException(400, "Idempotency-Key must be 1-100 letters, digits, ., _, : or -.")
        tenant = tenant_or_400(x_tenant_id)
        incident_id = uuid.uuid4().hex
        request_id = request_context.get()
        incident = Incident(
            id=incident_id,
            agent_run_id=uuid.uuid4().hex,
            tenant_id=tenant,
            scenario_id=scenario["id"],
            title=scenario["title"],
            service=scenario["service"],
            symptom=scenario["symptom"],
            status=IncidentStatus.investigating,
            timeline=[TimelineEvent(kind="alert", message=scenario["symptom"], request_id=request_id)],
            requested_failures=sorted(application.state.chaos.get(tenant, ChaosConfig()).fail_sources, key=lambda item: item.value),
            malformed_source=application.state.chaos.get(tenant, ChaosConfig()).malformed_source,
            simulate_worker_crash=application.state.chaos.get(tenant, ChaosConfig()).simulate_worker_crash,
        )
        incident, created = db.create_or_get(incident, idempotency_key)
        if not created:
            if incident.scenario_id != scenario["id"]:
                raise HTTPException(409, "Idempotency-Key was already used for a different scenario.")
            response.status_code = 200
            return incident
        chaos = application.state.chaos.get(tenant, ChaosConfig())
        task = asyncio.create_task(investigate(incident, scenario, chaos))
        application.state.tasks.add(task)
        task.add_done_callback(application.state.tasks.discard)
        return incident

    @application.get("/api/incidents/{incident_id}", response_model=Incident)
    async def get_incident(incident_id: str, x_tenant_id: str = Header("demo")):
        return load_incident(incident_id, x_tenant_id)

    @application.get("/api/chaos", response_model=ChaosConfig)
    async def get_chaos(x_tenant_id: str = Header("demo")):
        return application.state.chaos.get(tenant_or_400(x_tenant_id), ChaosConfig())

    @application.put("/api/chaos", response_model=ChaosConfig)
    async def set_chaos(payload: ChaosConfig, x_tenant_id: str = Header("demo")):
        tenant = tenant_or_400(x_tenant_id)
        application.state.chaos[tenant] = payload
        return payload

    @application.get("/api/evaluations")
    async def evaluations():
        return run_evaluations()

    @application.post("/api/incidents/{incident_id}/approval", response_model=Incident)
    async def approve(
        incident_id: str,
        payload: ApprovalRequest,
        x_role: Literal["viewer", "sre"] = Header("viewer"),
        x_tenant_id: str = Header("demo"),
    ):
        incident = load_incident(incident_id, x_tenant_id)
        if payload.decision == "approve" and x_role != "sre":
            event(incident, "approval", "Approval request rejected for viewer role; no write action ran.")
            db.save(incident)
            raise HTTPException(403, "SRE role required to approve remediation.")
        incident, decided = db.decide_approval(
            incident.id, incident.tenant_id, payload.decision, x_role, request_context.get()
        )
        if not incident:
            raise HTTPException(404, "Incident not found.")
        if not decided:
            raise HTTPException(409, "Incident has no supported remediation awaiting approval.")
        if payload.decision == "deny":
            return incident
        write = trace(incident, "remediation", "running", permission="write")
        incident.tool_trace.append(write)
        event(incident, "tool", f"Isolated write executor started action {incident.remediation.action} after approval.")
        db.save(incident)
        await asyncio.sleep(0.12)
        if x_role != "sre" or incident.remediation.action not in ALLOWED_REMEDIATIONS:
            write.status = "blocked"
            write.completed_at = now_utc()
            write.error = "Write policy rejected the action."
            incident.remediation.status = "blocked"
            incident.status = IncidentStatus.blocked
            event(incident, "failure", "Write policy blocked remediation.")
        else:
            write.status = "succeeded"
            write.completed_at = now_utc()
            incident.remediation.status = "applied"
            incident.status = IncidentStatus.recovered
            event(incident, "recovery", f"Simulation health recovered after approved {incident.remediation.action}.")
        incident.metrics.tool_calls = len(incident.tool_trace)
        db.save(incident)
        return incident

    @application.get("/api/metrics")
    async def metrics(x_tenant_id: str = Header("demo")):
        tenant = tenant_or_400(x_tenant_id)
        incidents = db.list(tenant)
        latencies = sorted(row.metrics.latency_ms for row in incidents if row.completed_at)
        p95 = latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else 0
        lines = [
            "# HELP sentinelgraph_incidents_total Reproducible simulated incidents by state.",
            "# TYPE sentinelgraph_incidents_total gauge",
            f"sentinelgraph_incidents_total {len(incidents)}",
            "# HELP sentinelgraph_investigation_latency_p95_ms P95 latency measured from local deterministic runs.",
            "# TYPE sentinelgraph_investigation_latency_p95_ms gauge",
            f"sentinelgraph_investigation_latency_p95_ms {p95}",
            "# HELP sentinelgraph_active_investigations Current in-process investigation tasks.",
            "# TYPE sentinelgraph_active_investigations gauge",
            f"sentinelgraph_active_investigations {sum(not task.done() for task in application.state.tasks)}",
            "# HELP sentinelgraph_tool_failures_total Explicit source and tool failures in the local dataset.",
            "# TYPE sentinelgraph_tool_failures_total counter",
            f"sentinelgraph_tool_failures_total {sum(row.metrics.failed_tools for row in incidents)}",
        ]
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    application.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return application


app = create_app()
