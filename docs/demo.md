# Demo walkthrough

Run with `docker compose up --build` and open <http://localhost:8000>, or start the Python app directly using the README. The demo uses local fixtures and works without network access after dependencies are installed.

## 60-second path

1. Confirm **Healthy** in the system indicator.
2. Select **Database connection pool saturation** or **Deployment regression in checkout**.
3. Watch the timeline record each of five read-only source calls and the service-filtered runbook lookup.
4. Open the root-cause citations and compare their evidence IDs with the observed metrics/SQL or deployment/trace cards.
5. Select **SRE approver** and approve the simulated rollback. A viewer request is rejected with HTTP 403.
6. Confirm the remediation write trace, recovered state, latency, zero model tokens, zero API spend, and `/api/metrics`.

Every result is simulated except local wall-clock latency. The $0 API spend and zero tokens are measured for a run with no model provider; cloud hosting/compute cost is not included.

## Failure demonstration

Select a core source such as `sql` for the database scenario in Chaos controls, save it, then start the scenario. The failed adapter appears in the trace; the missing core evidence blocks the root cause and remediation. Try a non-core source failure to see an explicitly marked partial investigation with reduced confidence. Clear chaos controls to restore the standard path.

## Technical walkthrough

Show `app/main.py`'s fixed read sequence, `app/investigator.py`'s source and citation gate, and the separate approval executor. Run `python evals/run.py --check` for the labeled retrieval and deterministic trace checks. The report in `evals/reports/latest.json` is labeled SIMULATED and must not be described as independent LLM accuracy.
