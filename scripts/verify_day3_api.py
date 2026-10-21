"""Comprehensive test script for Day 3 REST API endpoints."""

import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from services.api.main import app


def verify_day3_api():
    print("\n=======================================================")
    print(" Day 3 Task 1: Verifying Complete REST API Suite")
    print("=======================================================")
    client = TestClient(app)

    # 1. Test POST /api/v1/demo/run (202 Accepted + Idempotency)
    print("\n[1/6] Testing POST /api/v1/demo/run (One-click demo trigger)...", end=" ")
    idemp_key = f"demo-test-{uuid.uuid4().hex[:8]}"
    res_demo = client.post("/api/v1/demo/run", headers={"Idempotency-Key": idemp_key})
    assert res_demo.status_code == 202, f"Expected 202, got {res_demo.status_code}: {res_demo.text}"
    demo_data = res_demo.json()
    assert demo_data["status"] == "queued"
    assert "status_url" in demo_data
    assert demo_data["incident_id"]
    demo_inc_id = demo_data["incident_id"]
    demo_job_id = demo_data["job_id"]
    print(f"SUCCESS (Job: {demo_job_id}, Status: {demo_data['status']})")

    # Replay with same idempotency key should return same job
    print("  -> Verifying Idempotency-Key replay...", end=" ")
    res_demo_replay = client.post("/api/v1/demo/run", headers={"Idempotency-Key": idemp_key})
    assert res_demo_replay.status_code == 202
    assert res_demo_replay.json()["job_id"] == demo_job_id
    print("SUCCESS (Duplicate request safely returned original job)")

    # 2. Test GET /api/v1/jobs/{id}
    print(f"\n[2/6] Polling GET /api/v1/jobs/{demo_job_id}...", end=" ")
    res_job = client.get(f"/api/v1/jobs/{demo_job_id}")
    assert res_job.status_code == 200, f"Expected 200, got {res_job.status_code}"
    job_data = res_job.json()
    assert job_data["status"] in ["queued", "running", "completed"]
    print(f"SUCCESS (Job Status: '{job_data['status']}')")

    # 3. Test POST /api/v1/incidents (201 Created from event batch)
    print("\n[3/6] Testing POST /api/v1/incidents (Batch creation & conflict check)...", end=" ")
    batch_key = f"batch-test-{uuid.uuid4().hex[:8]}"
    batch_payload = {
        "title": "Payment gateway latency spike",
        "service_name": "payments",
        "severity": "critical",
        "events": [
            {
                "event_id": f"evt-pay-{uuid.uuid4().hex[:4]}",
                "timestamp": "2026-10-21T12:00:00Z",
                "service": "payments",
                "event_type": "error",
                "severity": "critical",
                "message": "Payment gateway connection reset",
                "attributes": {"gateway": "stripe-us-east", "error_code": "ETIMEDOUT"}
            }
        ]
    }
    res_create = client.post("/api/v1/incidents", json=batch_payload, headers={"Idempotency-Key": batch_key})
    assert res_create.status_code == 201, f"Expected 201, got {res_create.status_code}: {res_create.text}"
    created_inc = res_create.json()
    batch_inc_id = created_inc["id"]
    assert created_inc["service_name"] == "payments"
    print(f"SUCCESS (Created Incident ID: {batch_inc_id})")

    # Incompatible reuse of idempotency key must return 409 Conflict
    print("  -> Testing 409 Conflict on incompatible idempotency key reuse...", end=" ")
    incompatible_payload = {**batch_payload, "severity": "low"}
    res_conflict = client.post("/api/v1/incidents", json=incompatible_payload, headers={"Idempotency-Key": batch_key})
    assert res_conflict.status_code == 409, f"Expected 409, got {res_conflict.status_code}"
    print("SUCCESS (409 Conflict correctly rejected mismatching payload)")

    # 4. Test GET /api/v1/incidents (Pagination)
    print("\n[4/6] Testing GET /api/v1/incidents (Paginated list)...", end=" ")
    res_list = client.get("/api/v1/incidents?limit=5&offset=0")
    assert res_list.status_code == 200, f"Expected 200, got {res_list.status_code}"
    list_data = res_list.json()
    assert list_data["total"] >= 2
    assert len(list_data["items"]) <= 5
    print(f"SUCCESS (Total Incidents: {list_data['total']}, Retrieved: {len(list_data['items'])})")

    # 5. Test GET /api/v1/incidents/{id}/events (Chronological timeline)
    print(f"\n[5/6] Testing GET /api/v1/incidents/{demo_inc_id}/events...", end=" ")
    res_events = client.get(f"/api/v1/incidents/{demo_inc_id}/events")
    assert res_events.status_code == 200, f"Expected 200, got {res_events.status_code}"
    events = res_events.json()
    assert len(events) >= 5, f"Expected at least 5 events, got {len(events)}"
    print(f"SUCCESS (Found {len(events)} chronological timeline events)")
    print(f"  First Event: [{events[0]['source_event_id']}] ({events[0]['service_name']}) - {events[0]['event_type']}")

    # 6. Test POST /api/v1/incidents/{id}/feedback (Validation constraints)
    print(f"\n[6/6] Testing POST /api/v1/incidents/{demo_inc_id}/feedback...", end=" ")
    # Valid feedback
    res_fb = client.post(
        f"/api/v1/incidents/{demo_inc_id}/feedback",
        json={"rating": "helpful", "comment": "Accurately pinpointed database pool exhaustion."}
    )
    assert res_fb.status_code == 201, f"Expected 201, got {res_fb.status_code}: {res_fb.text}"
    fb_data = res_fb.json()
    assert fb_data["rating"] == "helpful"
    print(f"SUCCESS (Feedback ID: {fb_data['id']}, Rating: '{fb_data['rating']}')")

    # Invalid rating constraint check
    print("  -> Testing validation rejection on invalid rating...", end=" ")
    res_invalid_fb = client.post(
        f"/api/v1/incidents/{demo_inc_id}/feedback",
        json={"rating": "superb"}  # Not in ('helpful', 'incorrect', 'incomplete')
    )
    assert res_invalid_fb.status_code == 422, f"Expected 422, got {res_invalid_fb.status_code}"
    print("SUCCESS (422 Unprocessable Entity rejected invalid rating)")

    print("\n=======================================================")
    print(" Day 3 REST API Endpoints Verification: ALL PASSED!")
    print("=======================================================\n")


if __name__ == "__main__":
    verify_day3_api()
