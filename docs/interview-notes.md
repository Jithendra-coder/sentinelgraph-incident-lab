# Interview discussion map

## Why use a fixed state machine instead of LangGraph?

The demo currently has one bounded sequence and no alternate model-driven branches. A fixed sequence makes tool order, stop behavior, and failure propagation easy to inspect. A graph library becomes useful when measured requirements add meaningful branches, parallel evidence collection, durable resumability, or versioned graph traces.

## How are invented evidence and dangerous tools prevented?

The investigator uses a typed evidence schema, rejects extra fields, requires scenario-specific core sources, and validates citation IDs against collected evidence. The optional Prometheus read uses an operator-configured query; incident requests cannot change its URL or PromQL. A live metrics observation cannot be combined with fixture ground truth to claim a supported diagnosis. The separate writer supports three fixed simulated actions and checks the approval role. The demo does not claim real identity enforcement; authentication must precede any external deployment.

## What happens when a source is unavailable?

Every source has a persisted trace. A missing core source results in `blocked` with an unsupported `unknown` cause and no remediation. A missing optional source is labeled `partial`, with a lower fixed completeness score and reduced confidence.

## How are duplicate approvals prevented?

The SQLite store uses an immediate write transaction to claim a pending decision and move it to `applying` before the handler runs the simulated write. A concurrent request sees a non-pending state and receives HTTP 409. A restart marks an in-flight remediation blocked for reconciliation instead of replaying an action with an uncertain outcome.

## How is retrieval evaluated?

The versioned evaluation set contains four service-scoped labeled queries. It records Recall@1, Recall@3, and MRR for BM25 + sparse TF-IDF. The query set is too small to imply general semantic retrieval quality; add independently authored incident/runbook pairs before comparing embedding models or rerankers.

## How would this change at 100x volume or with real tenants?

Measure concurrency and storage first. Replace the in-process task set with a durable queue and lease/idempotency policy, move state to managed PostgreSQL, and derive tenant/role identity from an authenticated principal. Keep source adapters read-only and separately credentialed. Add per-tenant quotas and queue-depth alerts only with an explicit workload.

## Is the RCA accuracy really 100%?

It is 4/4 on the project's own curated fixtures, where the deterministic lab knows each injected cause. This proves the end-to-end scenario contract and regression path. It is not an independent benchmark and does not demonstrate general AI diagnostic accuracy.
