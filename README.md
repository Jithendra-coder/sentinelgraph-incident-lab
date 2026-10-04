# SentinelGraph

SentinelGraph is a local incident investigation lab. Inject one of four reproducible failures, inspect the read-only evidence and tool trace, review a cited root-cause finding, then approve a controlled **simulated** recovery.

The Demo Mode path is deterministic and needs no external model, cloud service, or network connection. It uses versioned fixtures, five typed read adapters, a service-filtered BM25 + sparse TF-IDF runbook retriever, a bounded investigator, SQLite, and a separate approval-gated simulated write executor.

## Run locally

Use Python 3.11 or newer. From the project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test,lint]"
python -m uvicorn app.main:app --reload
```

If Python 3.12 is not installed, use an available Python 3.11+ launcher (for example `py -3.11`). Open <http://127.0.0.1:8000>. API docs are at <http://127.0.0.1:8000/api/docs>. Runtime data is stored in `data/sentinelgraph.sqlite3` and ignored by Git.

Or run the optional container setup with `docker compose up --build`.

## Verify

```powershell
python -m unittest discover -s tests -v
python evals/run.py --check
python benchmarks/run.py --check
ruff check app tests evals benchmarks
```

The evaluation report is written to `evals/reports/latest.json`. The local measurement report is written to `benchmarks/reports/latest.json`. Each labels simulated classification separately from measured local latency and API spend. Four fixture replays are a functional demo measurement, not a load test or independent measure of model accuracy.

## Incident Lab flow

1. Pick database saturation, deployment regression, cache outage, or upstream timeout.
2. Inspect the chronological tool trace and simulated evidence cards as each source returns.
3. Review root cause confidence and evidence-ID citations. If a required source is missing, the investigator blocks an unsupported cause and all remediation.
4. Select the local **SRE approver** demo role and approve the allowlisted action. The viewer role is rejected by the API.
5. Inspect recovery and per-run latency, token count, API spend, and `/api/metrics`.

Use the visible Chaos controls to fail an evidence adapter on the next run, or inspect `PUT /api/chaos` for malformed-output and worker-interruption cases. `Idempotency-Key` on incident injection prevents a retried request from creating a second incident for the same tenant/key.

## Project notes

- [Architecture and tradeoffs](docs/architecture.md)
- [Threat model and limits](docs/threat-model.md)
- [Recruiter demo walkthrough](docs/demo.md)
- [Current phase, results, and remaining gaps](PROJECT_STATUS.md)
- [Local deployment boundary](infrastructure/README.md)

This is not connected to production systems and does not call an LLM. Root-cause labels and evidence are curated simulated data. The demo's role/tenant headers illustrate policy checks but are not authenticated identities; do not expose the local app publicly. See the threat model before adapting it.
