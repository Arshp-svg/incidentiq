"""End-to-end product verification testing the complete browser-to-report workflow."""

import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from services.api.main import app


def verify_full_product_flow():
    print("\n=======================================================")
    print(" Milestone 3: End-to-End Product Workflow Verification")
    print("=======================================================")
    client = TestClient(app)

    # 1. System Readiness Probe
    print("\n[1/5] Checking System Readiness (Browser Dashboard Load)...", end=" ")
    res_health = client.get("/health/ready")
    assert res_health.status_code == 200, f"System health check failed: {res_health.text}"
    health_data = res_health.json()
    assert health_data["status"] == "ready"
    print(f"SUCCESS (System Status: {health_data['status'].upper()})")

    # 2. Click "Run Demo Incident"
    print("\n[2/5] Simulating User Click: 'Run Demo Incident'...", end=" ")
    res_demo = client.post("/api/v1/demo/run")
    assert res_demo.status_code == 202, f"Demo run failed: {res_demo.status_code}"
    demo_job = res_demo.json()
    incident_id = demo_job["incident_id"]
    job_id = demo_job["job_id"]
    print(f"ACCEPTED (Incident ID: {incident_id}, Job ID: {job_id})")

    # 3. Live Job Status Polling
    print("\n[3/5] Polling Investigation Job Status (React useEffect Polling)...")
    status = demo_job["status"]
    attempts = 0
    max_attempts = 15

    while status in ["queued", "running"] and attempts < max_attempts:
        time.sleep(0.5)
        res_poll = client.get(f"/api/v1/jobs/{job_id}")
        assert res_poll.status_code == 200
        job_info = res_poll.json()
        status = job_info["status"]
        attempts += 1
        print(f"  Attempt {attempts}: Status = {status.upper()}")

    assert status == "completed", f"Investigation job did not complete successfully (ended in '{status}')"
    print(f"  -> SUCCESS: Investigation successfully completed!")

    # 4. Fetching Rendered Investigation Report
    print(f"\n[4/5] Fetching Final Investigation Report for Dashboard...", end=" ")
    res_report = client.get(f"/api/v1/incidents/{incident_id}/report")
    assert res_report.status_code == 200, f"Failed to retrieve report: {res_report.status_code}"
    report = res_report.json()

    assert report["incident_id"] == incident_id
    assert "root_cause" in report
    assert report["root_cause"]["confidence"] >= 0.7
    assert len(report["root_cause"]["evidence_ids"]) >= 1
    assert len(report["affected_services"]) >= 1
    print("SUCCESS")
    print(f"  Summary:     {report['summary']}")
    print(f"  Claim:       {report['root_cause']['claim']}")
    print(f"  Confidence:  {int(report['root_cause']['confidence'] * 100)}%")
    print(f"  Evidence:    {report['root_cause']['evidence_ids']}")
    print(f"  Topology:    {report['affected_services']}")

    # 5. User Submitting Feedback from UI
    print(f"\n[5/5] Submitting Engineer Feedback ('helpful')...", end=" ")
    res_fb = client.post(
        f"/api/v1/incidents/{incident_id}/feedback",
        json={"rating": "helpful", "comment": "Verified root cause directly matches database latency logs."},
    )
    assert res_fb.status_code == 201, f"Feedback submission failed: {res_fb.status_code}"
    fb = res_fb.json()
    assert fb["rating"] == "helpful"
    print(f"SUCCESS (Feedback ID: {fb['id']}, Status: Recorded)")

    print("\n=======================================================")
    print(" Milestone 3: End-to-End Product Flow VERIFIED!")
    print("=======================================================\n")


if __name__ == "__main__":
    verify_full_product_flow()
