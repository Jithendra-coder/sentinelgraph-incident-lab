from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def now_utc() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(StrEnum):
    metrics = "metrics"
    traces = "traces"
    logs = "logs"
    deployments = "deployments"
    sql = "sql"


class IncidentStatus(StrEnum):
    investigating = "investigating"
    awaiting_approval = "awaiting_approval"
    applying = "applying"
    blocked = "blocked"
    recovered = "recovered"


class TimelineEvent(StrictModel):
    at: datetime = Field(default_factory=now_utc)
    request_id: str = "demo"
    kind: Literal["alert", "tool", "evidence", "analysis", "approval", "recovery", "failure"]
    message: str


class Evidence(StrictModel):
    id: str
    source: Source
    summary: str
    observed_value: str
    collected_at: datetime = Field(default_factory=now_utc)
    provenance: Literal["SIMULATED", "PROMETHEUS"] = "SIMULATED"
    trust: Literal["observed", "untrusted"] = "observed"


class ToolTrace(StrictModel):
    id: str
    request_id: str = "demo"
    incident_id: str
    agent_run_id: str
    tool: Source | Literal["runbooks", "remediation", "orchestrator"]
    status: Literal["running", "succeeded", "failed", "blocked"]
    started_at: datetime = Field(default_factory=now_utc)
    completed_at: datetime | None = None
    evidence_id: str | None = None
    error: str | None = None
    permission: Literal["read", "write"] = "read"


class RootCause(StrictModel):
    cause_id: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    citations: list[str]
    supported: bool
    quality: Literal["complete", "partial", "insufficient"]


class Remediation(StrictModel):
    action: str
    description: str
    risk: str
    status: Literal["pending", "approved", "applied", "blocked"] = "pending"
    approval_required: bool = True
    actor: str | None = None
    approved_at: datetime | None = None


class RetrievedRunbook(StrictModel):
    id: str
    title: str
    score: float
    trust: Literal["untrusted"] = "untrusted"
    version: str


class RunMetrics(StrictModel):
    latency_ms: float = 0
    latency_label: Literal["MEASURED"] = "MEASURED"
    api_cost_usd: float = 0
    cost_label: Literal["MEASURED"] = "MEASURED"
    model_tokens: int = 0
    tool_calls: int = 0
    failed_tools: int = 0
    retries: int = 0


class Incident(StrictModel):
    id: str
    agent_run_id: str
    tenant_id: str
    scenario_id: str
    title: str
    service: str
    symptom: str
    status: IncidentStatus
    quality: Literal["complete", "partial", "insufficient"] = "insufficient"
    created_at: datetime = Field(default_factory=now_utc)
    completed_at: datetime | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    tool_trace: list[ToolTrace] = Field(default_factory=list)
    root_cause: RootCause | None = None
    remediation: Remediation | None = None
    runbook: RetrievedRunbook | None = None
    failed_sources: list[Source] = Field(default_factory=list)
    requested_failures: list[Source] = Field(default_factory=list)
    malformed_source: Source | None = None
    simulate_worker_crash: bool = False
    metrics: RunMetrics = Field(default_factory=RunMetrics)


class IncidentCreate(StrictModel):
    scenario_id: str


class ApprovalRequest(StrictModel):
    decision: Literal["approve", "deny"]


class ChaosConfig(StrictModel):
    fail_sources: list[Source] = Field(default_factory=list, max_length=5)
    malformed_source: Source | None = None
    simulate_worker_crash: bool = False


class Health(StrictModel):
    status: Literal["healthy", "degraded"]
    active_investigations: int
    scenario_count: int
