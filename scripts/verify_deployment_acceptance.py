"""Deployment Acceptance & Security Audit Verification Script (Day 5 Task 3).

Verifies the Deployment Acceptance Checklist from Page 12 of the blueprint:
1. GET /health/ready reports dependency readiness honestly without leaking credentials.
2. The demo workflow creates and completes a full investigation.
3. Data persistence: API queries retrieve incidents cleanly without state loss.
4. Evidence linkage: Report citations resolve strictly to real telemetry events.
5. Security Audit: Zero secrets, database credentials, or private S3 keys leak to client endpoints.
"""

import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from services.api.main import app

FORBIDDEN_SECRET_SUBSTRINGS = [
    "incidentiq_password",
    "minioadminpassword",
    "testpassword123",
    "postgresql+psycopg://",
    "bolt://neo4j",
    "sk-proj-",
    "sk-ant-",
]


def audit_payload_for_secrets(payload_str: str, context: str):
    """Assert that sensitive credentials or connection strings never leak in API output."""
    for secret in FORBIDDEN_SECRET_SUBSTRINGS:
        assert secret not in payload_str, (
            f"SECURITY VIOLATION: Forbidden secret/credential string '{secret}' leaked in {context}!"
        )


def verify_deployment_checklist():
    print("=" * 70)
    print(" Day 5 Task 3: Deployment Acceptance Checklist & Security Audit")
    print("=" * 70)

    client = TestClient(app)

    # -------------------------------------------------------------
    # Checklist Item 1: Honest Dependency Health Reporting
    # -------------------------------------------------------------
    print("\n[1/5] Checking GET /health/ready honest dependency reporting...", end=" ")
    res_ready = client.get("/health/ready")
    assert res_ready.status_code == 200, f"Health ready check failed: {res_ready.text}"
    ready_data = res_ready.json()
    assert ready_data["status"] == "ready"
    assert "details" in ready_data
    assert ready_data["details"].get("postgres") == "healthy"
    assert ready_data["details"].get("neo4j") == "healthy"
    assert ready_data["details"].get("s3") == "healthy"
    audit_payload_for_secrets(res_ready.text, "GET /health/ready")
    print("SUCCESS (PostgreSQL, Neo4j, and MinIO reported healthy)")

    # -------------------------------------------------------------
    # Checklist Item 2: Demo Investigation Creation & Completion
    # -------------------------------------------------------------
    print("\n[2/5] Triggering Demo Investigation (POST /api/v1/demo/run)...", end=" ")
    res_demo = client.post("/api/v1/demo/run")
    assert res_demo.status_code == 202, f"Demo run failed: {res_demo.text}"
    demo_data = res_demo.json()
    incident_id = demo_data["incident_id"]
    job_id = demo_data["job_id"]
    audit_payload_for_secrets(res_demo.text, "POST /api/v1/demo/run")
    print(f"ACCEPTED (Incident ID: {incident_id}, Job ID: {job_id})")

    print("      Polling investigation job until completion...", end=" ")
    completed = False
    for attempt in range(1, 15):
        time.sleep(0.5)
        res_job = client.get(f"/api/v1/jobs/{job_id}")
        assert res_job.status_code == 200
        job_data = res_job.json()
        audit_payload_for_secrets(res_job.text, f"GET /api/v1/jobs/{job_id}")
        if job_data["status"] == "completed":
            completed = True
            print(f"SUCCESS (Completed in attempt {attempt})")
            break
        elif job_data["status"] == "failed":
            raise RuntimeError(f"Investigation job failed: {job_data.get('error_message')}")
    assert completed, "Investigation job timed out before reaching completed status"

    # -------------------------------------------------------------
    # Checklist Item 3: Data Durability & Incident List Retention
    # -------------------------------------------------------------
    print("\n[3/5] Verifying Data Durability (GET /api/v1/incidents)...", end=" ")
    res_list = client.get("/api/v1/incidents?limit=50")
    assert res_list.status_code == 200
    list_data = res_list.json()
    incident_ids = [item["id"] for item in list_data["items"]]
    assert incident_id in incident_ids, f"Newly created demo incident {incident_id} not found in persisted list!"
    audit_payload_for_secrets(res_list.text, "GET /api/v1/incidents")
    print(f"SUCCESS (Retained {list_data['total']} persisted incidents in PostgreSQL)")

    # -------------------------------------------------------------
    # Checklist Item 4: Report Evidence Linkage & Document Tracing
    # -------------------------------------------------------------
    print("\n[4/5] Verifying Report & Grounded Evidence Traceability...", end=" ")
    res_report = client.get(f"/api/v1/incidents/{incident_id}/report")
    assert res_report.status_code == 200
    report_data = res_report.json()
    audit_payload_for_secrets(res_report.text, f"GET /api/v1/incidents/{incident_id}/report")

    # Fetch incident events
    res_events = client.get(f"/api/v1/incidents/{incident_id}/events")
    assert res_events.status_code == 200
    events_data = res_events.json()
    audit_payload_for_secrets(res_events.text, f"GET /api/v1/incidents/{incident_id}/events")
    valid_event_ids = {e.get("source_event_id") or e.get("event_id") for e in events_data}

    # Verify cited evidence strictly links to existing events
    cited_ids = report_data.get("root_cause", {}).get("evidence_ids", [])
    assert len(cited_ids) > 0, "Report does not cite any evidence IDs!"
    for cid in cited_ids:
        assert cid in valid_event_ids, f"Cited evidence ID '{cid}' does not exist in incident events {valid_event_ids}!"
    print(f"SUCCESS (100% of cited evidence {cited_ids} resolved to verified events)")

    # -------------------------------------------------------------
    # Checklist Item 5: Comprehensive Security & Secret Leak Audit
    # -------------------------------------------------------------
    print("\n[5/5] Running Comprehensive Secret Leak Audit on Client Bundles...", end=" ")
    # Inspect frontend source files for leaked credentials
    web_src = ROOT_DIR / "apps" / "web" / "src"
    for ts_file in web_src.rglob("*.ts*"):
        content = ts_file.read_text(encoding="utf-8")
        audit_payload_for_secrets(content, f"Frontend bundle file: {ts_file.name}")
    print("SUCCESS (Zero credentials, connection strings, or private keys in client code)")

    print("\n" + "=" * 70)
    print(" ALL DEPLOYMENT ACCEPTANCE & SECURITY AUDIT CHECKS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    verify_deployment_checklist()
