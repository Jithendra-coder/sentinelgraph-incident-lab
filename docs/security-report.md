# Local security and abuse report

**Scope:** deterministic local Demo Mode, dataset 1.0.0. No provider, customer data, or production system was connected.

## Checks run

- Unknown fields on Pydantic domain and request models are rejected.
- An unavailable required SQL evidence source produces a failed trace, an unsupported `unknown` cause, blocked status, and no remediation.
- An injected malformed SQL adapter payload is rejected by strict schema validation and blocks the incident.
- The unsafe runbook test fixture can be retrieved but is marked untrusted. Optional model analysis receives the symptom and collected evidence as data, has no tools, and cannot execute runbook text or actions.
- `viewer` cannot approve. The rejection is recorded; no write trace appears. The `sre` role can approve the fixed rollback simulation.
- Denial records an audit event and never starts the write executor.
- An incident ID created under one tenant header returns 404 under another tenant header; repeat submissions with one idempotency key do not create a duplicate.
- Worker crash and interrupted-service restart become explicit blocked incidents.
- Concurrent approval requests produce exactly one remediation execution.
- A restart during approval marks the in-flight remediation blocked and requires reconciliation before retrying.
- Chaos configuration reads back the full saved configuration; an idempotency key reused for a different scenario is rejected.

The API/integration cases are in [`tests/test_incident_lab.py`](../tests/test_incident_lab.py); deterministic scoring checks are in [`evals/reports/latest.json`](../evals/reports/latest.json).

## Limits

Tenant and role headers are caller-controlled. The tests validate route scoping and policy flow only; they do not prove authenticated authorization or prevent header spoofing. The optional OpenAI advisory has no tool channel and does not control the deterministic diagnosis or approval gate; its output is not yet evaluated against an independent incident set. No Redis, PostgreSQL, or external service exists to simulate its outage. Do not expose this demo publicly or connect real remediation credentials.
