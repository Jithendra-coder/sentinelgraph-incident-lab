# SentinelGraph project status

**Current phase:** P14 — optional OpenAI advisory analysis
**Status:** P14 implementation and mocked integration checks complete. The provider is opt-in and advisory-only; no API key or live Prometheus endpoint was configured, so external connectivity and model quality remain unverified. The local Demo Mode remains the default; a saved recording, local Docker smoke test, and cloud deployment remain unverified.
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
| P12 incident and approval integrity | Complete for local Demo Mode | Chaos settings round-trip; mismatched idempotency keys return conflict; SQLite transaction atomically claims approval; duplicate concurrent approvals execute once; interrupted remediation is blocked for reconciliation; startup defers DB recovery until app lifespan; P95 uses nearest-rank calculation |
| P13 Prometheus metrics read | Complete for mocked adapter path | Optional operator-configured instant query, bearer token from environment, strict vector parsing, bounded response, explicit provenance, source failure trace, mixed live/fixture RCA blocked; live endpoint unavailable for verification |
| P14 optional model advisory | Complete for mocked adapter path | OpenAI Responses Structured Outputs, opt-in provider and key, no tools or stored response, evidence-ID citation validation, advisory isolated from deterministic diagnosis and approval; live API and independent quality evaluation remain unverified |

## Latest verification

- Validation ran with Python 3.11 (the shell default is unsupported Python 3.10); project supports Python 3.11+ and the container/CI target is Python 3.12.
- Unit/integration suite: **31 tests passed**; Ruff and `node --check` passed.
- Deterministic evaluation: 4 labeled scenarios; tool selection/order and citation support 1.0, unsupported evidence 0; retrieval Recall@1/3 and MRR 1.0 on 4 queries. These fixture-driven scores are simulated consistency checks, not model quality results.
- Local measurement (`benchmarks/reports/latest.json`): 4 replay runs, P50 **1089.21 ms**, P95 **1117.94 ms** on temporary SQLite. Classification score 4/4 is labeled SIMULATED; model API spend $0 is measured because the run calls no model. This is a small functional sample, not a load test.
- Wheel build succeeded and includes the static UI, versioned scenario data, and optional telemetry and AI extras.
- Live browser flow: healthy start → database incident → five evidence cards/citations → viewer HTTP 403 → SRE-approved simulated rollback → healthy recovery.
- Docker CLI was not available in the current shell, so Compose validation and a local image build could not be rerun. CI remains configured to build the image.

## Known limits and next upgrade

- RCA remains deterministic and tied to fixture labels so Demo Mode can reproduce the entire path. The opt-in model output is a human-review advisory; it has not been evaluated for incident accuracy.
- No production auth or real tenant identity. Only metrics has an optional live Prometheus adapter; traces, logs, deployments, and SQL still use fixtures. There is no PostgreSQL, Redis, durable worker queue, OpenTelemetry collector, Prometheus/Grafana deployment, cloud IaC, or public hosting.
- Four curated incidents and four retrieval queries are too small for broad accuracy/latency claims. The benchmark is a functional local measurement, not a concurrency/load test. Model/provider behavior is mocked in tests; a live API key and Prometheus endpoint were not available.
- A persistent agent trace screenshot and recorded chaos/recovery walkthrough still need capture when preparing a portfolio submission.
- The next smallest production-readiness milestones are CI coverage for the optional OpenAI SDK path and an independent evaluation dataset, then live adapters for the remaining evidence sources.
