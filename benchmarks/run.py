import argparse
import json
import logging
import math
import platform
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.store import Store  # noqa: E402

logging.getLogger("sentinelgraph").setLevel(logging.WARNING)


def run() -> dict:
    dataset = json.loads((ROOT / "app" / "data" / "scenarios.v1.json").read_text(encoding="utf-8"))
    expected = {row["id"]: row["ground_truth"]["cause_id"] for row in dataset["scenarios"]}
    latencies = []
    correct = 0
    with (
        patch.dict(
            "os.environ",
            {
                "SENTINELGRAPH_ANALYSIS_PROVIDER": "demo",
                "SENTINELGRAPH_PROMETHEUS_URL": "",
                "SENTINELGRAPH_PROMETHEUS_QUERY": "",
                "SENTINELGRAPH_PROMETHEUS_TOKEN": "",
            },
        ),
        tempfile.TemporaryDirectory() as directory,
        TestClient(create_app(Store(Path(directory) / "benchmark.sqlite3"))) as client,
    ):
        for scenario_id, cause_id in expected.items():
            response = client.post("/api/incidents", json={"scenario_id": scenario_id})
            response.raise_for_status()
            incident_id = response.json()["id"]
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                result = client.get(f"/api/incidents/{incident_id}").json()
                if result["status"] != "investigating":
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError(f"{scenario_id} failed to finish within 5 seconds")
            if result["status"] != "awaiting_approval" or result["root_cause"]["cause_id"] != cause_id:
                raise RuntimeError(f"Unexpected investigation result for {scenario_id}")
            correct += 1
            latencies.append(result["metrics"]["latency_ms"])
    ordered = sorted(latencies)
    report = {
        "scenario_dataset_version": dataset["version"],
        "classification_label": "SIMULATED",
        "latency_label": "MEASURED",
        "sample_size": len(latencies),
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "storage": "temporary local SQLite"},
        "latency_ms": {
            "p50": round((ordered[1] + ordered[2]) / 2, 2) if len(ordered) >= 4 else round(ordered[len(ordered) // 2], 2),
            "p95": round(ordered[math.ceil(0.95 * len(ordered)) - 1], 2),
            "runs": [round(value, 2) for value in latencies],
        },
        "scenario_replay_accuracy": {"correct": correct, "total": len(expected), "rate": round(correct / len(expected), 4), "label": "SIMULATED"},
        "model_api_spend_usd": {"value": 0, "label": "MEASURED", "scope": "No model provider called; excludes local compute and hosting."},
        "limitations": "Four curated deterministic runs in one local process; not a load test or a production/model quality benchmark.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure four deterministic local incident replays.")
    parser.add_argument("--check", action="store_true", help="Fail if any deterministic scenario replay does not pass.")
    args = parser.parse_args()
    report = run()
    if args.check and report["scenario_replay_accuracy"]["rate"] != 1:
        return 1
    output = json.dumps(report, indent=2) + "\n"
    destination = ROOT / "benchmarks" / "reports" / "latest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
