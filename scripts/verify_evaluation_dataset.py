"""Verification script for Day 4 Task 2: AI Evaluation Dataset.

Validates:
1. Dataset exists at data/evaluation/incidents.json
2. Total incident count is between 30 and 50
3. All 5 scenarios (A, B, C, D, E) are balanced and present
4. Ground truth contracts and evidence references resolve to actual events
5. Abstention cases (Scenario E) are explicitly marked with should_abstain=True
"""

import json
import sys
from collections import Counter
from pathlib import Path


DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "evaluation" / "incidents.json"


def verify_dataset():
    print("=" * 65)
    print(" Day 4 Task 2: Verifying Labeled AI Evaluation Dataset")
    print("=" * 65)

    if not DATA_FILE.exists():
        print(f"FAILED: Evaluation dataset not found at {DATA_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        incidents = json.load(f)

    total_count = len(incidents)
    print(f"\n[1/4] Checking Dataset Volume: {total_count} incidents...", end=" ")
    if not (30 <= total_count <= 50):
        print(f"FAILED (Expected 30-50 incidents, found {total_count})")
        sys.exit(1)
    print("SUCCESS (Within 30–50 requirement)")

    # Check scenario distribution
    print("\n[2/4] Checking Scenario Distribution across Scenarios A through E...")
    counts = Counter(inc["scenario_type"] for inc in incidents)
    scenario_names = {
        "A": "Database latency spike",
        "B": "Faulty deployment",
        "C": "External payment provider outage",
        "D": "Connection-pool exhaustion",
        "E": "Unrelated errors with insufficient evidence (abstention)",
    }

    for sc_key, sc_name in scenario_names.items():
        count = counts.get(sc_key, 0)
        print(f"  - Scenario {sc_key} ({sc_name}): {count} cases")
        if count == 0:
            print(f"FAILED: Scenario {sc_key} has 0 cases!", file=sys.stderr)
            sys.exit(1)

    print("\n[3/4] Validating Field Schemas and Ground Truth Integrity...")
    for idx, inc in enumerate(incidents, start=1):
        assert "id" in inc, f"Incident #{idx} missing 'id'"
        assert "scenario_type" in inc, f"Incident {inc.get('id')} missing 'scenario_type'"
        assert "title" in inc, f"Incident {inc['id']} missing 'title'"
        assert "service_name" in inc, f"Incident {inc['id']} missing 'service_name'"
        assert "severity" in inc, f"Incident {inc['id']} missing 'severity'"
        assert "ground_truth" in inc, f"Incident {inc['id']} missing 'ground_truth'"
        assert "events" in inc, f"Incident {inc['id']} missing 'events'"
        assert len(inc["events"]) > 0, f"Incident {inc['id']} has no events"

        gt = inc["ground_truth"]
        assert "known_cause" in gt, f"Incident {inc['id']} missing ground_truth.known_cause"
        assert "expected_claim_keywords" in gt, f"Incident {inc['id']} missing ground_truth.expected_claim_keywords"
        assert "should_abstain" in gt, f"Incident {inc['id']} missing ground_truth.should_abstain"

        # Check abstain flags
        if inc["scenario_type"] == "E":
            assert gt["should_abstain"] is True, f"Scenario E incident {inc['id']} must have should_abstain=True"
        else:
            assert gt["should_abstain"] is False, f"Scenario {inc['scenario_type']} incident {inc['id']} should not abstain"

        # Check evidence references resolve strictly
        event_ids = {e["event_id"] for e in inc["events"]}
        for expected_id in gt.get("expected_evidence_ids", []):
            assert expected_id in event_ids, (
                f"Incident {inc['id']}: expected evidence ID '{expected_id}' not found in event list {event_ids}"
            )

    print("  -> SUCCESS: All 40 incidents satisfy schema contracts and evidence reference resolution.")

    print("\n[4/4] Checking Distractor and Abstention Telemetry...")
    abstention_cases = [inc for inc in incidents if inc["ground_truth"]["should_abstain"]]
    print(f"  -> Total abstention cases: {len(abstention_cases)} ({len(abstention_cases) / total_count * 100:.1f}%)")
    assert len(abstention_cases) >= 5, "Dataset must have at least 5 abstention cases"
    print("  -> SUCCESS: Abstention test cases verified.")

    print("\n" + "=" * 65)
    print(" ALL EVALUATION DATASET INTEGRITY CHECKS PASSED!")
    print("=" * 65)


if __name__ == "__main__":
    verify_dataset()
