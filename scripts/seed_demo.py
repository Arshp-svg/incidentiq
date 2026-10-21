"""Unified demo seeding and environment bootstrap script for IncidentIQ.

Performs complete platform initialization:
1. Runs Alembic database migrations to head (PostgreSQL + pgvector schema).
2. Seeds service dependency graph and constraints into Neo4j.
3. Indexes markdown runbooks into pgvector and uploads source markdown to MinIO S3.
4. Seeds the canonical demo incident scenario and completes the initial investigation.
"""

import sys
import json
import uuid
import argparse
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from alembic.config import Config
from alembic import command

from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, InvestigationJob, IncidentEvent, InvestigationFinding
from incidentiq.graph.client import get_driver, close_driver
from incidentiq.graph.queries import init_graph_schema, seed_service_topology
from incidentiq.retrieval.indexer import index_all_runbooks
from incidentiq.storage.s3 import s3_service
from services.worker.runner import run_investigation_job


def apply_migrations():
    """Apply Alembic migrations up to head."""
    print("\n[1/4] Applying PostgreSQL database migrations...", end=" ")
    try:
        alembic_cfg = Config(str(ROOT_DIR / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
        print("SUCCESS (Schema migrated to HEAD)")
    except Exception as e:
        print(f"FAILED: {e}")
        raise


def seed_neo4j_graph():
    """Create constraints and seed service dependency graph."""
    print("\n[2/4] Seeding Neo4j service dependency graph...", end=" ")
    driver = get_driver()
    try:
        with driver.session() as session:
            init_graph_schema(session)
            counts = seed_service_topology(session)
            print(f"SUCCESS ({counts['services']} services, {counts['relationships']} relationships)")
            return counts
    finally:
        close_driver()


def index_runbooks():
    """Parse, chunk, embed, and index markdown runbooks into pgvector and MinIO."""
    print("\n[3/4] Indexing markdown runbooks into pgvector & MinIO...", end=" ")
    runbooks_dir = ROOT_DIR / "data" / "runbooks"
    results = index_all_runbooks(runbooks_dir)
    total_chunks = sum(results.values())
    print(f"SUCCESS ({len(results)} runbooks, {total_chunks} chunks indexed)")
    for name, cnt in results.items():
        print(f"      • {name}: {cnt} chunks")
    return results


def seed_demo_scenario(execute_workflow: bool = True):
    """Seed the canonical checkout latency scenario into DB and MinIO."""
    scenario_path = ROOT_DIR / "data" / "scenarios" / "checkout_latency.json"
    print(f"\n[4/4] Seeding canonical demo incident scenario ({scenario_path.name})...")
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)

    incident_id = uuid.uuid4()
    job_id = uuid.uuid4()
    events_data = scenario.get("events", [])

    # Upload raw events to MinIO
    s3_key = s3_service.upload_raw_events(str(incident_id), events_data)

    # Persist Incident and Job in PostgreSQL
    with SessionLocal() as db:
        inc = Incident(
            id=incident_id,
            title=scenario["title"],
            service_name=scenario["service_name"],
            severity=scenario["severity"],
            status="investigating" if execute_workflow else "open",
            started_at=datetime.now(timezone.utc),
        )
        job = InvestigationJob(
            id=job_id,
            incident_id=incident_id,
            status="queued",
            attempt_count=0,
        )
        db.add(inc)
        db.add(job)

        for evt in events_data:
            ie = IncidentEvent(
                id=uuid.uuid4(),
                incident_id=incident_id,
                source_event_id=evt["event_id"],
                service_name=evt["service"],
                event_type=evt["event_type"],
                occurred_at=datetime.fromisoformat(evt["timestamp"].replace("Z", "+00:00")),
                payload=evt.get("attributes", {}),
                s3_key=s3_key,
            )
            db.add(ie)
        db.commit()

    print(f"  -> Incident created: {incident_id} ({scenario['title']})")
    print(f"  -> Investigation job queued: {job_id}")

    if execute_workflow:
        print("  -> Executing LangGraph investigation workflow for demo report...")
        report = run_investigation_job(str(incident_id), str(job_id))
        print("  -> SUCCESS: Investigation completed and findings persisted!")
        print(f"     Claim:      {report.get('root_cause', {}).get('claim', 'N/A')}")
        print(f"     Confidence: {report.get('root_cause', {}).get('confidence', 0.0) * 100:.0f}%")
        print(f"     Evidence:   {report.get('root_cause', {}).get('evidence_ids', [])}")

    return incident_id, job_id


def main():
    parser = argparse.ArgumentParser(description="IncidentIQ unified demo environment seed script")
    parser.add_argument("--skip-workflow", action="store_true", help="Seed incident without running workflow")
    args = parser.parse_args()

    print("=" * 70)
    print(" IncidentIQ: Production Demo Environment Seeding & Bootstrap")
    print("=" * 70)

    try:
        apply_migrations()
        seed_neo4j_graph()
        index_runbooks()
        inc_id, j_id = seed_demo_scenario(execute_workflow=not args.skip_workflow)

        print("\n" + "=" * 70)
        print(" DEMO ENVIRONMENT SUCCESSFULLY SEEDED AND READY!")
        print("=" * 70)
        print(f"• API Live Probe:   http://localhost:8000/health/live")
        print(f"• API Docs URL:     http://localhost:8000/docs")
        print(f"• Web Dashboard:    http://localhost:5173 (dev) or http://localhost:3000 (prod)")
        print(f"• Demo Incident ID: {inc_id}")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\nSeeding FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
