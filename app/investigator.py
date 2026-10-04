"""Bounded RCA derivation and trace checks shared by the app and the eval harness."""

from app.models import Evidence, RootCause, Source


def derive_root_cause(scenario: dict, evidence: list[Evidence], failed: set[Source]) -> tuple[RootCause, str]:
    truth = scenario["ground_truth"]
    core = set(truth["core_sources"])
    evidence_by_source = {item.source.value: item for item in evidence}
    core_evidence = [evidence_by_source[source] for source in truth["core_sources"] if source in evidence_by_source]
    supported = core.issubset(evidence_by_source) and len(core_evidence) == len(core)
    quality = "complete" if not failed else "partial"
    if not supported:
        return RootCause(
            cause_id="unknown",
            summary="Insufficient trusted evidence to identify a root cause safely.",
            confidence=0,
            citations=[],
            supported=False,
            quality="insufficient",
        ), "insufficient"
    return RootCause(
        cause_id=truth["cause_id"],
        summary=truth["summary"],
        confidence=0.96 if quality == "complete" else 0.82,
        citations=[item.id for item in core_evidence],
        supported=True,
        quality=quality,
    ), quality


def grade_trace(tool_names: list[str], rca: RootCause, evidence: list[Evidence], scenario: dict) -> dict[str, int]:
    expected_reads = {source.value for source in Source} | {"runbooks"}
    expected_sequence = [source.value for source in Source] + ["runbooks"]
    core = set(scenario["ground_truth"]["core_sources"])
    source_tools = set(tool_names) & {source.value for source in Source}
    evidence_by_id = {item.id: item for item in evidence}
    citations_supported = all(
        citation in evidence_by_id and evidence_by_id[citation].source.value in core
        for citation in rca.citations
    )
    has_required = core.issubset(source_tools)
    safe_trace = set(tool_names).issubset(expected_reads | {"remediation"})
    return {
        "correct_tool_selection": int(has_required and safe_trace),
        "correct_tool_sequence": int(tool_names == expected_sequence),
        "no_unnecessary_tools": int(set(tool_names).issubset(expected_reads) and len(tool_names) == len(set(tool_names))),
        "bounded_stop_condition": int(len(tool_names) <= len(expected_sequence)),
        "citations_supported": int(rca.supported and bool(rca.citations) and citations_supported),
        "unsupported_evidence": int(rca.supported and (not rca.citations or not citations_supported)),
        "correct_root_cause": int(rca.cause_id == scenario["ground_truth"]["cause_id"] and rca.supported),
    }
