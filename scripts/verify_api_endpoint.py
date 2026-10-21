"""Verify FastAPI endpoints: health probes, job status, incident details, and final report."""

import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from services.api.main import app
from scripts.run_scenario import run_scenario


def verify_api_endpoints():
    print("\n--- Day 2 Task 5: Verifying FastAPI Endpoints ---")
    client = TestClient(app)

    # 1. Test /health/live
    print("[1/5] Testing GET /health/live...", end=" ")
    res_live = client.get("/health/live")
    assert res_live.status_code == 200, f"Expected 200, got {res_live.status_code}"
    data_live = res_live.json()
    assert data_live["status"] == "live"
    print(f"SUCCESS ({data_live})")

    # 2. Test /health/ready
    print("[2/5] Testing GET /health/ready...", end=" ")
    res_ready = client.get("/health/ready")
    assert res_ready.status_code == 200, f"Expected 200, got {res_ready.status_code}: {res_ready.text}"
    data_ready = res_ready.json()
    assert data_ready["status"] == "ready"
    assert data_ready["details"]["postgres"] == "healthy"
    assert data_ready["details"]["neo4j"] == "healthy"
    assert data_ready["details"]["s3"] == "healthy"
    print(f"SUCCESS ({data_ready['details']})")

    # 3. Ensure a completed incident exists by running the scenario
    print("[3/5] Seeding an incident investigation scenario...", end=" ")
    report = run_scenario()
    incident_id = report["incident_id"]
    print(f"DONE (Incident ID: {incident_id})")

    # 4. Test GET /api/v1/incidents/{id}
    print(f"[4/5] Testing GET /api/v1/incidents/{incident_id}...", end=" ")
    res_inc = client.get(f"/api/v1/incidents/{incident_id}")
    assert res_inc.status_code == 200, f"Expected 200, got {res_inc.status_code}"
    data_inc = res_inc.json()
    assert data_inc["service_name"] == "checkout"
    print(f"SUCCESS (Title: '{data_inc['title']}', Severity: {data_inc['severity']})")

    # 5. Test GET /api/v1/incidents/{id}/report
    print(f"[5/5] Testing GET /api/v1/incidents/{incident_id}/report...", end=" ")
    res_rep = client.get(f"/api/v1/incidents/{incident_id}/report")
    assert res_rep.status_code == 200, f"Expected 200, got {res_rep.status_code}"
    data_rep = res_rep.json()
    assert data_rep["incident_id"] == incident_id
    assert "root_cause" in data_rep
    assert data_rep["root_cause"]["claim"]
    assert len(data_rep["root_cause"]["evidence_ids"]) > 0
    print(f"SUCCESS (Report Summary: '{data_rep['summary']}')")
    print(f"  Root Cause Claim: {data_rep['root_cause']['claim']}")
    print(f"  Confidence:       {data_rep['root_cause']['confidence']}")
    print(f"  Evidence IDs:     {data_rep['root_cause']['evidence_ids']}")
    print(f"  Affected:         {data_rep['affected_services']}")

    print("\nAll FastAPI endpoints verified SUCCESSFUL!\n")


if __name__ == "__main__":
    verify_api_endpoints()
