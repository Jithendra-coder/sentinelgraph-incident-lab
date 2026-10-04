# Evaluation suite

`dataset.v1.json` labels four runbook queries. Incident root-cause labels and their core sources live in `app/data/scenarios.v1.json` version 1.0.0. The harness calls the same RCA derivation and trace grader as the app and reports tool selection/order, extra tool use, stop condition, citation support, unsupported evidence, RCA fixture agreement, Recall@1/3, and MRR.

Run it with `python evals/run.py --check`. Output is written to `evals/reports/latest.json`; thresholds are version-controlled in the runner. Report label `SIMULATED` applies to all fixture quality scores. It is a regression contract for this deterministic product, not an independent accuracy benchmark.

## Current error taxonomy

- **Missing required source:** unsupported `unknown` cause, no citations, no remediation, and blocked state.
- **Missing optional source:** explicit source failure, partial label, lower fixed confidence, with core citations retained.
- **Malformed adapter output:** strict schema rejection, persisted failed tool, no evidence from that call.
- **Runbook retrieval miss:** remediation remains blocked.
- **Worker failure/restart:** terminal blocked incident with an explicit failure event.
- **Unauthorized or denied approval:** rejected/audited, with no write executor call.

## Regression history

The repository began empty, so there is no pre-existing quality baseline. The first integration run exposed leaked SQLite connection handles and repeated WAL-mode setup; closing each connection and initializing WAL once fixed both the locked Windows temp databases and the slow polling. The final suite includes connection-restart, duplicate injection, schema, source-failure, malformed-output, worker, tenant-scope, retrieval, and approval checks. Current results are stored with the report rather than inferred from console output.
