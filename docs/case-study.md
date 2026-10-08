# SentinelGraph: evidence-first incident response

## Problem

During an outage, responders need to connect symptoms across metrics, traces, logs, deployment history, and database state. A generic log summary can sound convincing while hiding missing sources or unsupported claims. SentinelGraph demonstrates a reviewable path from an alert to cited evidence and an approval-gated recovery.

## Design

The local Incident Lab injects one of four versioned simulated failures. A fixed asynchronous investigation reads five typed sources, performs a service-filtered BM25 + sparse TF-IDF runbook search, validates the incident-specific core evidence, and reports citations. Metrics can optionally come from a configured Prometheus instant query; the other four sources remain fixtures, and mixing the two provenance types blocks fixture-grounded RCA. SQLite persists timeline events and tool traces. A separate allowlisted simulated remediation executor only runs after an SRE-role approval request.

## Decisions

- Demo Mode is deterministic and works without model credentials or third-party calls.
- The optional Prometheus connector is read-only and operator-configured; a live adapter for traces, logs, deployments, and SQL is still required for real multi-source RCA.
- Optional OpenAI Responses analysis provides a structured, evidence-ID-validated advisory. It has no tools and cannot alter the deterministic RCA or simulated approval gate.
- SQLite and one in-process worker keep the portfolio demo runnable with one container. Durable queue replay and multi-worker coordination are deferred until measured need exists.
- A fixed state sequence is used instead of LangGraph because the demo has one bounded path; adding a graph framework would not make this fixture flow more capable.
- BM25 + sparse TF-IDF provides reproducible hybrid lexical search. Semantic vectors and a reranker are deferred pending a larger labeled set.
- A fixture-grounded investigator preserves the known-cause demo. Its 100% score checks implementation consistency with those fixtures, not general RCA or LLM quality.

## Failure behavior

Core-source failure, mixed live/fixture evidence, malformed evidence, a failed worker, or a service restart blocks an unsupported root cause and remediation. Optional-source failure remains visible as partial evidence and reduces the demo confidence score. Viewer approval is rejected; deny records an audit event and never calls the write executor. Concurrent approval requests are claimed transactionally, and interrupted writes are blocked for reconciliation. See the [security report](security-report.md) and [evaluation suite](../evals/README.md).

## Results

The current reproducible local measurements are in [`benchmarks/reports/latest.json`](../benchmarks/reports/latest.json). The report identifies the Python/platform, SQLite setup, four-run sample size, measured latency, and simulated classification score. The corresponding fixture and retrieval scores are in [`evals/reports/latest.json`](../evals/reports/latest.json). Both reports state their limits; neither establishes production throughput or model quality.

## What is not proven

The role and tenant headers are demonstration controls, not authenticated identity. The fixtures are curated; the confidence value is a fixed completeness score, not a probability. The model advisory has not been quality-evaluated against an independent incident dataset. There is no live multi-source adapter, semantic retriever, database/message broker cluster, cloud deployment, load test, or saved screen recording. See the [architecture](architecture.md) and [threat model](threat-model.md) for upgrade boundaries.
