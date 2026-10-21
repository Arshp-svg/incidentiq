"""Run script for Day 4 Task 3: AI Benchmark Evaluation Suite.

Executes all 40 labeled evaluation cases through the LangGraph pipeline and computes:
- Root-cause accuracy
- Evidence validity (100% resolution required)
- Evidence relevance
- Abstention quality
- Retrieval recall@3
- p50 and p95 latency
- Estimated cost
"""

import sys
import json
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from incidentiq.agents.evaluation import run_benchmark


DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "evaluation" / "incidents.json"
RESULTS_FILE = Path(__file__).resolve().parents[1] / "data" / "evaluation" / "benchmark_results.json"


def main():
    print("=" * 70)
    print(" IncidentIQ: AI Agent Benchmark Evaluation Suite (Day 4 Task 3)")
    print("=" * 70)

    if not DATA_FILE.exists():
        print(f"Error: Dataset not found at {DATA_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[1/3] Loading evaluation dataset from {DATA_FILE}...")
    print(f"[2/3] Executing 40 incidents across Scenarios A through E through LangGraph...")

    summary = run_benchmark(DATA_FILE)

    print(f"\n[3/3] Benchmark Execution Completed in {sum(r.latency_ms for r in summary.results) / 1000.0:.2f}s total runtime.")
    print("\n" + "=" * 70)
    print(" EVALUATION BENCHMARK RESULTS SUMMARY")
    print("=" * 70)

    print(f"\nTotal Incidents Evaluated:    {summary.total_incidents}")
    print(f"Root-Cause Accuracy:          {summary.root_cause_accuracy * 100:.1f}%")
    print(f"Evidence Validity Rate:       {summary.evidence_validity_rate * 100:.1f}%  (Target: 100% - zero hallucinated IDs)")
    print(f"Evidence Relevance Rate:      {summary.evidence_relevance_rate * 100:.1f}%")
    print(f"Abstention Quality Rate:      {summary.abstention_quality_rate * 100:.1f}%  (Avoids false assertions on noise)")
    print(f"Retrieval Recall@3:           {summary.retrieval_recall_at_k * 100:.1f}%  (Expected runbook in top-3 chunks)")
    print(f"Median (p50) Latency:         {summary.p50_latency_ms:.1f} ms")
    print(f"95th-Percentile (p95) Latency:{summary.p95_latency_ms:.1f} ms")
    print(f"Total Estimated Cost:         ${summary.total_estimated_cost_usd:.5f} USD")
    print(f"Cost per Investigation:       ${summary.total_estimated_cost_usd / summary.total_incidents:.6f} USD")

    print("\n" + "-" * 70)
    print(f"{'Scenario':<12} | {'Description':<32} | {'Cases':<6} | {'Accuracy':<8} | {'Validity'}")
    print("-" * 70)
    scenario_desc = {
        "A": "Database latency spike",
        "B": "Faulty deployment",
        "C": "Payment provider outage",
        "D": "Connection-pool exhaustion",
        "E": "Insufficient evidence (abstain)",
    }
    for stype, d in summary.scenario_breakdown.items():
        print(f"Scenario {stype:<3} | {scenario_desc.get(stype, ''):<32} | {d['count']:<6} | {d['accuracy']*100:>6.1f}%  | {d['validity']*100:>6.1f}%")
    print("-" * 70)

    # Export results JSON
    export_data = {
        "total_incidents": summary.total_incidents,
        "metrics": {
            "root_cause_accuracy": summary.root_cause_accuracy,
            "evidence_validity_rate": summary.evidence_validity_rate,
            "evidence_relevance_rate": summary.evidence_relevance_rate,
            "abstention_quality_rate": summary.abstention_quality_rate,
            "retrieval_recall_at_k": summary.retrieval_recall_at_k,
            "p50_latency_ms": summary.p50_latency_ms,
            "p95_latency_ms": summary.p95_latency_ms,
            "total_estimated_cost_usd": summary.total_estimated_cost_usd,
            "cost_per_investigation_usd": summary.total_estimated_cost_usd / summary.total_incidents,
        },
        "scenario_breakdown": summary.scenario_breakdown,
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)

    print(f"\nFull benchmark report exported to:\n  {RESULTS_FILE}")

    # Acceptance Checks
    assert summary.evidence_validity_rate == 1.0, "Evidence validity must be 100%!"
    assert summary.abstention_quality_rate >= 0.85, "Abstention quality must be >= 85%!"
    assert summary.root_cause_accuracy >= 0.80, "Root cause accuracy baseline must be >= 80%!"
    assert summary.retrieval_recall_at_k >= 0.80, "Retrieval recall@3 must be >= 80%!"

    print("\n" + "=" * 70)
    print(" BENCHMARK ACCEPTANCE CRITERIA MET!")
    print("=" * 70)


if __name__ == "__main__":
    main()
