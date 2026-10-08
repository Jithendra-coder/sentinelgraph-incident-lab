import json
import logging
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.evaluation import run_evaluations
from app.main import create_app
from app.models import Incident, IncidentStatus, Remediation, RunMetrics, ToolTrace, now_utc
from app.store import Store

ROOT = Path(__file__).parents[1]
SCENARIOS = json.loads((ROOT / "app" / "data" / "scenarios.v1.json").read_text(encoding="utf-8"))["scenarios"]
logging.getLogger("sentinelgraph").setLevel(logging.WARNING)


class IncidentLabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "test.sqlite3")
        self.app = create_app(self.store)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.temp.cleanup()

    def inject_and_wait(self, scenario_id, tenant="demo"):
        response = self.client.post("/api/incidents", json={"scenario_id": scenario_id}, headers={"X-Tenant-ID": tenant})
        self.assertEqual(response.status_code, 202, response.text)
        incident = response.json()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/incidents/{incident['id']}", headers={"X-Tenant-ID": tenant})
            self.assertEqual(response.status_code, 200, response.text)
            incident = response.json()
            if incident["status"] != "investigating":
                return incident
            time.sleep(0.12)
        self.fail("investigation did not reach a terminal review state")

    def test_four_scenarios_finish_with_cited_known_causes(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario["id"]):
                incident = self.inject_and_wait(scenario["id"])
                self.assertEqual(incident["status"], "awaiting_approval")
                self.assertEqual(incident["root_cause"]["cause_id"], scenario["ground_truth"]["cause_id"])
                self.assertTrue(incident["root_cause"]["supported"])
                self.assertEqual(len(incident["root_cause"]["citations"]), len(scenario["ground_truth"]["core_sources"]))
                self.assertEqual(len(incident["tool_trace"]), 6)
                self.assertTrue(all(call["request_id"] and call["incident_id"] and call["agent_run_id"] for call in incident["tool_trace"]))
                self.assertEqual(incident["runbook"]["id"], scenario["ground_truth"]["runbook_id"])
                self.assertEqual(incident["metrics"]["model_tokens"], 0)

    def test_core_source_failure_blocks_rca_and_remediation(self):
        self.client.put("/api/chaos", json={"fail_sources": ["sql"]})
        incident = self.inject_and_wait("database-saturation")
        self.assertEqual(incident["status"], "blocked")
        self.assertFalse(incident["root_cause"]["supported"])
        self.assertEqual(incident["root_cause"]["cause_id"], "unknown")
        self.assertIsNone(incident["remediation"])
        self.assertEqual(incident["failed_sources"], ["sql"])
        sql_call = next(call for call in incident["tool_trace"] if call["tool"] == "sql")
        self.assertEqual(sql_call["status"], "failed")
        self.assertFalse(any(call["permission"] == "write" for call in incident["tool_trace"]))

    def test_noncritical_failure_is_visible_and_confidence_is_reduced(self):
        self.client.put("/api/chaos", json={"fail_sources": ["logs"]})
        incident = self.inject_and_wait("database-saturation")
        self.assertEqual(incident["status"], "awaiting_approval")
        self.assertTrue(incident["root_cause"]["supported"])
        self.assertEqual(incident["quality"], "partial")
        self.assertEqual(incident["root_cause"]["confidence"], 0.82)
        self.assertIn("logs", incident["failed_sources"])
        self.assertEqual(incident["root_cause"]["quality"], "partial")

    def test_viewer_cannot_approve_but_sre_can_recover_simulation(self):
        incident = self.inject_and_wait("deployment-regression")
        endpoint = f"/api/incidents/{incident['id']}/approval"
        response = self.client.post(endpoint, json={"decision": "approve"}, headers={"X-Role": "viewer"})
        self.assertEqual(response.status_code, 403)
        before = self.client.get(f"/api/incidents/{incident['id']}").json()
        self.assertEqual(before["status"], "awaiting_approval")
        self.assertFalse(any(call["permission"] == "write" for call in before["tool_trace"]))
        self.assertTrue(any("rejected for viewer role" in event["message"] for event in before["timeline"]))
        recovered = self.client.post(endpoint, json={"decision": "approve"}, headers={"X-Role": "sre"})
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()["status"], "recovered")
        write = next(call for call in recovered.json()["tool_trace"] if call["tool"] == "remediation")
        self.assertEqual(write["permission"], "write")
        self.assertEqual(write["status"], "succeeded")

    def test_concurrent_approvals_execute_only_once(self):
        incident = self.inject_and_wait("deployment-regression")
        endpoint = f"/api/incidents/{incident['id']}/approval"
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    self.client.post,
                    endpoint,
                    json={"decision": "approve"},
                    headers={"X-Role": "sre"},
                )
                for _ in range(2)
            ]
            responses = [future.result() for future in futures]
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        final = self.client.get(f"/api/incidents/{incident['id']}").json()
        writes = [call for call in final["tool_trace"] if call["tool"] == "remediation"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["status"], "succeeded")

    def test_deny_never_runs_write_executor(self):
        incident = self.inject_and_wait("cache-outage")
        denied = self.client.post(f"/api/incidents/{incident['id']}/approval", json={"decision": "deny"})
        self.assertEqual(denied.status_code, 200, denied.text)
        self.assertEqual(denied.json()["status"], "blocked")
        self.assertFalse(any(call["permission"] == "write" for call in denied.json()["tool_trace"]))

    def test_malformed_adapter_payload_is_rejected_and_blocks_core_rca(self):
        response = self.client.put("/api/chaos", json={"malformed_source": "sql"})
        self.assertEqual(response.status_code, 200)
        incident = self.inject_and_wait("database-saturation")
        self.assertEqual(incident["status"], "blocked")
        self.assertIn("sql", incident["failed_sources"])
        sql_call = next(call for call in incident["tool_trace"] if call["tool"] == "sql")
        self.assertIn("strict evidence schema", sql_call["error"])
        self.assertFalse(incident["root_cause"]["supported"])

    def test_worker_failure_is_explicit_and_does_not_report_success(self):
        self.client.put("/api/chaos", json={"simulate_worker_crash": True})
        incident = self.inject_and_wait("database-saturation")
        self.assertEqual(incident["status"], "blocked")
        self.assertIsNone(incident["remediation"])
        self.assertTrue(any("failed explicitly" in event["message"] for event in incident["timeline"]))

    def test_tenant_qualified_lookup_does_not_disclose_incident(self):
        incident = self.inject_and_wait("upstream-timeout", tenant="team-a")
        self.assertEqual(self.client.get(f"/api/incidents/{incident['id']}", headers={"X-Tenant-ID": "team-b"}).status_code, 404)
        self.assertEqual(len(self.client.get("/api/incidents", headers={"X-Tenant-ID": "team-b"}).json()), 0)

    def test_idempotency_key_prevents_duplicate_incident_creation(self):
        headers = {"Idempotency-Key": "replay-checkout-001"}
        first = self.client.post("/api/incidents", json={"scenario_id": "database-saturation"}, headers=headers)
        second = self.client.post("/api/incidents", json={"scenario_id": "database-saturation"}, headers=headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(len(self.client.get("/api/incidents").json()), 1)

    def test_idempotency_key_rejects_a_different_scenario(self):
        headers = {"Idempotency-Key": "same-key-different-request"}
        first = self.client.post("/api/incidents", json={"scenario_id": "database-saturation"}, headers=headers)
        second = self.client.post("/api/incidents", json={"scenario_id": "cache-outage"}, headers=headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(len(self.client.get("/api/incidents").json()), 1)

    def test_chaos_settings_round_trip(self):
        config = {"fail_sources": ["sql"], "malformed_source": "logs", "simulate_worker_crash": True}
        self.assertEqual(self.client.put("/api/chaos", json=config).status_code, 200)
        self.assertEqual(self.client.get("/api/chaos").json(), config)

    def test_demo_eval_report_meets_retrieval_and_trace_thresholds(self):
        report = run_evaluations()
        self.assertEqual(report["label"], "SIMULATED")
        self.assertEqual(report["agent"]["correct_root_cause"], 1)
        self.assertEqual(report["agent"]["unsupported_evidence"], 0)
        self.assertGreaterEqual(report["retrieval"]["recall_at_1"], 0.75)
        self.assertGreaterEqual(report["retrieval"]["mrr"], 0.75)
        self.assertEqual(report["safety_checks"]["missing_core_source_blocks_rca"], 1)
        self.assertEqual(report["safety_checks"]["malicious_runbook_is_marked_untrusted"], 1)

    def test_health_and_prometheus_metrics_are_available(self):
        self.assertEqual(self.client.get("/api/health").json()["status"], "healthy")
        response = self.client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("sentinelgraph_investigation_latency_p95_ms", response.text)

    def test_prometheus_p95_uses_nearest_rank_for_small_samples(self):
        for index, latency in enumerate((10, 20, 30, 40)):
            self.store.save(
                Incident(
                    id=f"latency-{index}",
                    agent_run_id=f"run-{index}",
                    tenant_id="demo",
                    scenario_id="database-saturation",
                    title="Latency sample",
                    service="checkout-api",
                    symptom="test",
                    status=IncidentStatus.blocked,
                    completed_at=now_utc(),
                    metrics=RunMetrics(latency_ms=latency),
                )
            )
        response = self.client.get("/api/metrics")
        self.assertIn("sentinelgraph_investigation_latency_p95_ms 40", response.text)


class DomainValidationTests(unittest.TestCase):
    def test_app_creation_defers_database_initialization_until_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.sqlite3"
            app = create_app(Store(path))
            self.assertFalse(path.exists())
            with TestClient(app):
                self.assertTrue(path.exists())

    def test_incident_schema_rejects_unrecognized_fields(self):
        with self.assertRaises(ValidationError):
            Incident.model_validate({"id": "x", "extra_tool": "drop_database"})

    def test_store_restart_marks_in_progress_run_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "restart.sqlite3")
            store.initialize()
            incident = Incident(
                id="interrupted",
                agent_run_id="run-1",
                tenant_id="demo",
                scenario_id="database-saturation",
                title="Restart test",
                service="checkout-api",
                symptom="test",
                status=IncidentStatus.investigating,
            )
            store.save(incident)
            self.assertEqual(store.recover_interrupted(), 1)
            recovered = store.get("interrupted", "demo")
            self.assertEqual(recovered.status, IncidentStatus.blocked)
            self.assertIn("service restart", recovered.timeline[-1].message)

    def test_store_restart_blocks_an_interrupted_remediation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "approval-restart.sqlite3")
            store.initialize()
            incident = Incident(
                id="interrupted-approval",
                agent_run_id="run-approval",
                tenant_id="demo",
                scenario_id="database-saturation",
                title="Restart test",
                service="checkout-api",
                symptom="test",
                status=IncidentStatus.applying,
                root_cause={
                    "cause_id": "cause",
                    "summary": "supported",
                    "confidence": 1,
                    "citations": ["e1"],
                    "supported": True,
                    "quality": "complete",
                },
                remediation=Remediation(action="rollback", description="rollback", risk="risk", status="approved"),
                tool_trace=[
                    ToolTrace(
                        id="write-1",
                        incident_id="interrupted-approval",
                        agent_run_id="run-approval",
                        tool="remediation",
                        status="running",
                        permission="write",
                    )
                ],
            )
            store.save(incident)
            legacy = incident.model_copy(deep=True)
            legacy.id = "legacy-interrupted-approval"
            legacy.agent_run_id = "run-legacy-approval"
            legacy.status = IncidentStatus.awaiting_approval
            legacy.tool_trace[0].incident_id = legacy.id
            legacy.tool_trace[0].agent_run_id = legacy.agent_run_id
            store.save(legacy)
            self.assertEqual(store.recover_interrupted(), 2)
            recovered = store.get("interrupted-approval", "demo")
            self.assertEqual(recovered.status, IncidentStatus.blocked)
            self.assertEqual(recovered.remediation.status, "blocked")
            self.assertEqual(recovered.tool_trace[0].status, "blocked")
            self.assertIn("reconcile", recovered.timeline[-1].message)
            recovered_legacy = store.get("legacy-interrupted-approval", "demo")
            self.assertEqual(recovered_legacy.status, IncidentStatus.blocked)
            self.assertIn("reconcile", recovered_legacy.timeline[-1].message)


if __name__ == "__main__":
    unittest.main()
