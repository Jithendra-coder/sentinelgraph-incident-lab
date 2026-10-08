# Evidence pack index

- **Trust boundaries and data flow:** [architecture diagram](architecture.md)
- **Versioned incident ground truth:** [`app/data/scenarios.v1.json`](../app/data/scenarios.v1.json), version 1.0.0
- **Labeled retrieval set:** [`evals/dataset.v1.json`](../evals/dataset.v1.json), version 1.0.0
- **Evaluation output and limitations:** [`evals/reports/latest.json`](../evals/reports/latest.json)
- **Local benchmark, environment, and measured latency:** [`benchmarks/reports/latest.json`](../benchmarks/reports/latest.json)
- **Attack boundary and tested failure cases:** [security report](security-report.md)
- **Failure/recovery test cases:** [`tests/test_incident_lab.py`](../tests/test_incident_lab.py)
- **Interactive agent trace:** the running local browser demo at <http://127.0.0.1:8765> shows the completed simulated database incident, citations, approval audit, rollback write trace, and recovered health.
- **Demo recording:** not saved. The local flow is repeatable using [the walkthrough](demo.md); record it when preparing the portfolio submission.

The current trace was exercised during development, but a screenshot/recording binary is not included in the repository. All fixture scores are clearly labeled simulated; local latency and zero model API spend describe the four-run Demo Mode benchmark, which calls no model.
