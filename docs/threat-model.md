# Threat model

## Assets

Incident records, source observations, evidence citations, runbook guidance, tenant-scoped local state, and approval audit history.

## Untrusted inputs

Scenario IDs, tenant headers, role headers, chaos requests, and retrieved runbook text. Pydantic request models reject unknown fields. The scenario selector only addresses the four checked-in fixtures. Retrieved text never becomes executable tool instructions; the unsafe test runbook remains labeled `untrusted`.

## Controls implemented

- Every evidence adapter is read-only and accepts no caller-supplied query or command.
- Database operations use SQLite parameter binding and tenant-qualified incident lookups.
- Root causes require every scenario's core evidence source and cite only evidence IDs returned by those sources. Missing core evidence produces an unsupported cause and blocked remediation.
- Confidence is a fixed completeness score for this fixture lab, not a probability estimate.
- Remediation is a distinct route and executor, allowlisted, and requires `X-Role: sre`; viewer requests are rejected. Approval and execution are separately audited.
- Structured logs omit request headers and request bodies. No external model is called, and no secrets are needed in Demo Mode.
- The optional Prometheus URL, query, and bearer token are operator-provided environment settings. The adapter sends only a read-only instant query, rejects redirects and oversized/malformed results, and never accepts a URL or PromQL expression from an incident request.
- Scenario ground truth is rejected when evidence includes a live Prometheus observation, preventing a fixture label from being presented as a live diagnosis.
- Chaos settings are explicit, tenant-keyed within the single-process simulator, and copied into the incident record for audit.

## Limits

This is a local lab, not a production security boundary. The role and tenant headers demonstrate policy flow but are not cryptographically authenticated; a caller can choose them. There is no real RBAC identity provider, CSRF protection for public hosting, tenant secret/key management, external model prompt defense, or real write connection. The configured Prometheus endpoint is trusted operator input; do not let untrusted users configure it. Keep the service on localhost or a trusted demo network. Add authentication and server-derived tenant identity before any multi-user deployment.
