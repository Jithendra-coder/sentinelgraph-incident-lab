import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation import run_evaluations


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SentinelGraph's versioned deterministic evaluation.")
    parser.add_argument("--check", action="store_true", help="Fail when any current regression threshold is missed.")
    args = parser.parse_args()
    report = run_evaluations()
    output = json.dumps(report, indent=2) + "\n"
    if args.check:
        assert report["agent"]["correct_root_cause"] == 1, "RCA regression"
        assert report["agent"]["correct_tool_selection"] == 1, "Tool selection regression"
        assert report["agent"]["correct_tool_sequence"] == 1, "Tool sequence regression"
        assert report["agent"]["bounded_stop_condition"] == 1, "Investigator stop condition regression"
        assert report["agent"]["unsupported_evidence"] == 0, "Unsupported evidence regression"
        assert report["retrieval"]["recall_at_1"] >= 0.75, "Retrieval Recall@1 below threshold"
        assert report["retrieval"]["mrr"] >= 0.75, "Retrieval MRR below threshold"
        assert report["safety_checks"]["missing_core_source_blocks_rca"] == 1, "Core evidence safety regression"
        assert report["safety_checks"]["malicious_runbook_is_marked_untrusted"] == 1, "Runbook trust label regression"
    destination = Path(__file__).parent / "reports" / "latest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
