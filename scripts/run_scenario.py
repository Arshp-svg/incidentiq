"""CLI script to run a seeded scenario from start to finish and produce a grounded report."""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, InvestigationJob, IncidentEvent, InvestigationFinding
from incidentiq.storage.s3 import s3_service
from incidentiq.agents.output import validate_report_evidence
from services.worker.runner import run_investigation_job


def run_scenario(scenario_path: Path | None = None) -> dict:
    if scenario_path is None:
        scenario_path = Path(__file__).resolve().parents[1] / "data" / "scenarios" / "checkout_latency.json"

    print(f"\n=======================================================")
    print(f" IncidentIQ: Running Seeded Investigation Scenario")
    print(f" Scenario: {scenario_path.name}")
    print(f"=======================================================")

    # 1. Load scenario definition
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)

    incident_id = uuid.uuid4()
    job_id = uuid.uuid4()
    events_data = scenario.get("events", [])

    print(f"\n[1/5] Ingesting scenario into PostgreSQL & MinIO...")
    print(f"  Incident ID: {incident_id}")
    print(f"  Job ID:      {job_id}")
    print(f"  Title:       {scenario['title']}")
    print(f"  Service:     {scenario['service_name']} (Severity: {scenario['severity']})")
    print(f"  Events:      {len(events_data)} telemetry events")

    # Upload raw events to S3
    s3_key = s3_service.upload_raw_events(str(incident_id), events_data)

    # Persist in DB
    with SessionLocal() as db:
        inc = Incident(
            id=incident_id,
            title=scenario["title"],
            service_name=scenario["service_name"],
            severity=scenario["severity"],
            status="investigating",
            started_at=datetime.now(timezone.utc),
        )
        job = InvestigationJob(
            id=job_id,
            incident_id=incident_id,
            status="queued",
        )
        db.add(inc)
        db.add(job)

        for evt in events_data:
            dt = datetime.fromisoformat(evt["timestamp"].replace("Z", "+00:00"))
            db_evt = IncidentEvent(
                id=uuid.uuid4(),
                incident_id=incident_id,
                source_event_id=evt["event_id"],
                service_name=evt["service"],
                event_type=evt["event_type"],
                occurred_at=dt,
                payload={**evt["attributes"], "message": evt.get("message", "")},
                s3_key=s3_key,
            )
            db.add(db_evt)

        db.commit()

    print(f"  -> Ingestion complete (Raw S3: {s3_key})")

    # 2. Run LangGraph investigation workflow
    print(f"\n[2/5] Running LangGraph investigation workflow...")
    start_time = datetime.now()
    report = run_investigation_job(str(incident_id), str(job_id))
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"  -> Workflow completed in {elapsed:.2f}s")

    # 3. Validate evidence grounding
    print(f"\n[3/5] Validating evidence references...")
    is_valid, errors = validate_report_evidence(report, events_data)
    if not is_valid:
        print(f"  FAILED: Report failed evidence validation: {errors}")
        sys.exit(1)

    cited_ids = report.get("root_cause", {}).get("evidence_ids", [])
    print(f"  SUCCESS: All cited evidence IDs {cited_ids} verified against ingested telemetry.")

    # 4. Verify DB findings and S3 report
    print(f"\n[4/5] Verifying database findings and S3 report artifact...")
    with SessionLocal() as db:
        job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
        findings = db.query(InvestigationFinding).filter(InvestigationFinding.job_id == job_id).all()
        assert job and job.status == "completed", f"Expected job status 'completed', got {job.status if job else None}"
        assert len(findings) > 0, "No findings recorded in PostgreSQL"
        print(f"  -> PostgreSQL job marked 'completed'")
        print(f"  -> PostgreSQL findings persisted: {len(findings)} finding(s)")

    report_s3_key = f"incidents/{incident_id}/reports/report.json"
    s3_obj = s3_service.client.get_object(Bucket=s3_service.bucket_name, Key=report_s3_key)
    persisted_report = json.loads(s3_obj["Body"].read().decode("utf-8"))
    assert persisted_report["incident_id"] == str(incident_id), "S3 report ID mismatch"
    print(f"  -> MinIO report verified at: {report_s3_key}")

    # 5. Output Grounded Investigation Report
    print(f"\n[5/5] Final Grounded Investigation Report:")
    print("-------------------------------------------------------")
    print(f"SUMMARY: {report.get('summary')}")
    print(f"\nROOT CAUSE HYPOTHESIS:")
    print(f"  Claim:           {report.get('root_cause', {}).get('claim')}")
    print(f"  Confidence:      {report.get('root_cause', {}).get('confidence')}")
    print(f"  Supporting IDs:  {report.get('root_cause', {}).get('evidence_ids')}")
    print(f"\nAFFECTED SERVICES:")
    for svc in report.get("affected_services", []):
        print(f"  - {svc}")
    print(f"\nALTERNATIVE EXPLANATIONS:")
    for alt in report.get("alternatives", []):
        print(f"  - {alt}")
    print(f"\nRECOMMENDED ACTIONABLE CHECKS:")
    for chk in report.get("recommended_checks", []):
        print(f"  - {chk}")
    print(f"\nLIMITATIONS:")
    for lim in report.get("limitations", []):
        print(f"  - {lim}")
    print("-------------------------------------------------------")
    print("\nSeeded incident investigation verified SUCCESSFUL!\n")
    return report


if __name__ == "__main__":
    run_scenario()
