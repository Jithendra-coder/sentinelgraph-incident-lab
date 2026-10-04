# SentinelGraph project status

**Current phase:** P11 — reproducible local Demo Mode and evidence pack
**Status:** Local portfolio release complete. The technical walkthrough is working; a saved recording, local Docker smoke test, and cloud deployment remain unverified.
**Baseline:** Workspace was empty on 2026-10-04: no existing code, tests, dependency files, repository history, or behaviors.

## Phase gates

| Phase | Result | Evidence |
|---|---|---|
| P0 domain, threat model, ground truth | Complete | Strict Pydantic schemas, versioned scenario fixtures, threat model |
| P1 deterministic simulator | Complete | Four known causes: database pool saturation, release regression, cache outage, upstream timeout |
| P2 end-to-end RCA | Complete for Demo Mode | Evidence-backed citations, confidence, blocked state when required core evidence is absent |
| P3 multi-source adapters | Complete for fixtures | Five typed, persisted read traces with explicit failure states |
| P4 bounded state/orchestration | Complete for local demo | Fixed five-source sequence + one runbook retrieval; no free-form loop; SQLite persistence and restart blocking |
| P5 hybrid retrieval | Complete for lexical baseline | Service filtering, BM25 + sparse TF-IDF, four labeled retrieval queries |
| P6 agent/trace evaluation | Complete for deterministic harness | Tool selection, unnecessary tools, citation support, unsupported evidence, RCA, recall@1, MRR |
| P7 approval boundary | Complete for local policy demo | Viewer blocked; SRE approval audited; separate three-action allowlisted simulated writer |
| P8 abuse/data safety | Partial and explicitly local | Strict schemas, untrusted runbook fixture, input limits, tenant-qualified reads, failure tests; headers are not authentication |
| P9 observability | Partial local implementation | JSON request logs, correlated IDs, per-tool timestamps/failures, run metrics, `/api/metrics`; no OpenTelemetry/Grafana/queue dashboard |
| P10 failure/recovery | Complete for app-level chaos cases | Source outage, malformed evidence, worker failure/restart tests; no model, Redis, or broker exists to chaos-test |
| P11 delivery/demo pack | Complete for local walkthrough; packaging evidence partial | Responsive Incident Lab, Dockerfile/Compose, CI image build, case study, interview notes, security report, evidence index. Live UI path verified in browser. No saved recording; Docker CLI never returned engine information for a local image smoke test. |

## Latest verification

- Python 3.11.0 on Windows 10; project supports Python 3.11+ and the container/CI target is Python 3.12.
- Unit/integration suite: **13 tests passed**; Ruff, Python compile, and `node --check` passed.
- Deterministic evaluation: 4 labeled scenarios; tool selection/order and citation support 1.0, unsupported evidence 0; retrieval Recall@1/3 and MRR 1.0 on 4 queries. These fixture-driven scores are simulated consistency checks, not model quality results.
- Local measurement (`benchmarks/reports/latest.json`): 4 replay runs, P50 **1,022.75 ms**, P95 **1,041.13 ms** on temporary SQLite. Classification score 4/4 is labeled SIMULATED; model API spend $0 is measured because the run calls no model. This is a small functional sample, not a load test.
- Wheel build succeeded and includes the static UI and versioned scenario data.
- Live browser flow: healthy start → database incident → five evidence cards/citations → viewer HTTP 403 → SRE-approved simulated rollback → healthy recovery.
- Docker Compose syntax validation passed. Docker Desktop was started; its engine pipe appeared, but `docker info` and `docker version` stalled without a server response, so the local image build remains unverified.

## Known limits and next upgrade

- No LangGraph or LLM; RCA is deterministic and tied to fixture labels so Demo Mode can reproduce the entire path. These scores cannot prove general AI performance.
- No production auth, real tenant identity, external live adapters, PostgreSQL, Redis, durable worker queue, OpenTelemetry collector, Prometheus/Grafana deployment, cloud IaC, or public hosting.
- Four curated incidents and four retrieval queries are too small for broad accuracy/latency claims. The benchmark is a functional local measurement, not a concurrency/load test.
- A persistent agent trace screenshot and recorded chaos/recovery walkthrough still need capture when preparing a portfolio submission.
- The next smallest production-readiness milestone is authenticated identity and isolated tenant credentials, followed by a real read-only adapter and dataset-based quality evaluation.
