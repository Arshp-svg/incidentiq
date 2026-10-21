"""AI benchmark evaluation harness for IncidentIQ.

Measures:
1. Root-cause accuracy (identifies known cause keywords)
2. Evidence validity (100% of cited evidence IDs exist in telemetry)
3. Evidence relevance (cited evidence IDs match expected ground truth)
4. Abstention quality (agent refrains from false claims on inconclusive evidence)
5. Retrieval recall@k (relevant runbook retrieved from pgvector)
6. Latency (median p50 and p95 investigation duration)
7. Estimated cost (input/output token usage)
"""

import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from incidentiq.agents.graph import investigation_graph
from incidentiq.agents.state import InvestigationState
from incidentiq.agents.output import validate_report_evidence


@dataclass
class IncidentEvaluationResult:
    incident_id: str
    scenario_type: str
    title: str
    root_cause_accurate: bool
    evidence_valid: bool
    evidence_relevant: bool
    abstention_accurate: bool
    retrieval_success: bool
    latency_ms: float
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    estimated_cost_usd: float
    claim: str
    summary: str
    cited_evidence_ids: list[str]
    retrieved_runbooks: list[str]


@dataclass
class BenchmarkSummary:
    total_incidents: int
    root_cause_accuracy: float
    evidence_validity_rate: float
    evidence_relevance_rate: float
    abstention_quality_rate: float
    retrieval_recall_at_k: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_estimated_cost_usd: float
    results: list[IncidentEvaluationResult] = field(default_factory=list)
    scenario_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)


def evaluate_single_incident(incident: dict[str, Any], top_k: int = 3) -> IncidentEvaluationResult:
    """Run a single labeled incident through the LangGraph workflow and score against ground truth."""
    inc_id = incident["id"]
    scenario_type = incident["scenario_type"]
    gt = incident["ground_truth"]
    events = incident.get("events", [])
    should_abstain = gt.get("should_abstain", False)

    # Initial state (isolated in-memory run)
    state: InvestigationState = {
        "incident_id": inc_id,
        "job_id": "",  # Empty job_id skips database write pollution
        "incident_title": incident["title"],
        "service_name": incident["service_name"],
        "severity": incident["severity"],
        "events": events,
    }

    start_time = time.perf_counter()
    final_state = investigation_graph.invoke(state)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    report = final_state.get("report", {})
    root_cause = report.get("root_cause", {})
    claim = root_cause.get("claim", "")
    summary = report.get("summary", "")
    cited_ids = root_cause.get("evidence_ids", [])
    runbook_chunks = final_state.get("runbook_chunks", [])
    retrieved_docs = list({c.get("document_name") for c in runbook_chunks if c.get("document_name")})

    # 1. Evidence Validity: Every cited ID must exist in telemetry
    is_valid, _ = validate_report_evidence(report, events)

    # 2. Abstention Quality
    # Inconclusive should be identified if should_abstain is True
    is_inconclusive = (
        "inconclusive" in summary.lower()
        or "inconclusive" in claim.lower()
        or "insufficient" in summary.lower()
        or root_cause.get("confidence", 1.0) <= 0.35
    )
    if should_abstain:
        abstention_accurate = is_inconclusive
    else:
        abstention_accurate = not is_inconclusive

    # 3. Root-Cause Accuracy
    if should_abstain:
        # For abstention cases, accuracy means abstaining
        root_cause_accurate = is_inconclusive
    else:
        expected_keywords = [kw.lower() for kw in gt.get("expected_claim_keywords", [])]
        claim_lower = f"{claim} {summary}".lower()
        # True if any significant subset of expected keywords matches
        matches = [kw for kw in expected_keywords if kw in claim_lower]
        root_cause_accurate = len(matches) >= 1

    # 4. Evidence Relevance: At least one cited ID matches expected ground truth evidence
    expected_ids = set(gt.get("expected_evidence_ids", []))
    if should_abstain:
        evidence_relevant = True
    else:
        evidence_relevant = bool(expected_ids.intersection(set(cited_ids)))

    # 5. Retrieval Recall@k
    expected_runbook = gt.get("expected_runbook")
    if expected_runbook:
        expected_stem = expected_runbook.replace(".md", "")
        retrieval_success = any(
            doc in (expected_runbook, expected_stem) for doc in retrieved_docs
        )
    else:
        retrieval_success = True

    # 6. Cost Estimation (standard mini instruct model rates: $0.15/1M in, $0.60/1M out)
    prompt_tokens = 350 + len(events) * 60 + len(runbook_chunks) * 120
    completion_tokens = 160
    cost_usd = (prompt_tokens * 0.00000015) + (completion_tokens * 0.00000060)

    return IncidentEvaluationResult(
        incident_id=inc_id,
        scenario_type=scenario_type,
        title=incident["title"],
        root_cause_accurate=root_cause_accurate,
        evidence_valid=is_valid,
        evidence_relevant=evidence_relevant,
        abstention_accurate=abstention_accurate,
        retrieval_success=retrieval_success,
        latency_ms=elapsed_ms,
        estimated_prompt_tokens=prompt_tokens,
        estimated_completion_tokens=completion_tokens,
        estimated_cost_usd=cost_usd,
        claim=claim,
        summary=summary,
        cited_evidence_ids=cited_ids,
        retrieved_runbooks=retrieved_docs,
    )


def run_benchmark(dataset_path: Path) -> BenchmarkSummary:
    """Execute the full benchmark suite over the labeled incident dataset."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        incidents = json.load(f)

    results: list[IncidentEvaluationResult] = []
    latencies: list[float] = []

    for inc in incidents:
        res = evaluate_single_incident(inc)
        results.append(res)
        latencies.append(res.latency_ms)

    latencies.sort()
    n = len(results)
    p50 = latencies[int(n * 0.5)] if n > 0 else 0.0
    p95 = latencies[int(n * 0.95)] if n > 0 else 0.0

    accuracy = sum(1 for r in results if r.root_cause_accurate) / n if n else 0.0
    validity = sum(1 for r in results if r.evidence_valid) / n if n else 0.0
    relevance = sum(1 for r in results if r.evidence_relevant) / n if n else 0.0
    abstention = sum(1 for r in results if r.abstention_accurate) / n if n else 0.0

    retrieval_cases = [r for r in results if r.scenario_type != "E"]
    retrieval_recall = (
        sum(1 for r in retrieval_cases if r.retrieval_success) / len(retrieval_cases)
        if retrieval_cases else 0.0
    )

    total_cost = sum(r.estimated_cost_usd for r in results)

    # Breakdown by scenario
    breakdown: dict[str, dict[str, Any]] = {}
    for stype in ("A", "B", "C", "D", "E"):
        s_cases = [r for r in results if r.scenario_type == stype]
        if s_cases:
            breakdown[stype] = {
                "count": len(s_cases),
                "accuracy": sum(1 for r in s_cases if r.root_cause_accurate) / len(s_cases),
                "validity": sum(1 for r in s_cases if r.evidence_valid) / len(s_cases),
                "avg_latency_ms": sum(r.latency_ms for r in s_cases) / len(s_cases),
            }

    return BenchmarkSummary(
        total_incidents=n,
        root_cause_accuracy=accuracy,
        evidence_validity_rate=validity,
        evidence_relevance_rate=relevance,
        abstention_quality_rate=abstention,
        retrieval_recall_at_k=retrieval_recall,
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        total_estimated_cost_usd=total_cost,
        results=results,
        scenario_breakdown=breakdown,
    )
