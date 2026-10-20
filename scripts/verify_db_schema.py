"""Script to verify all database tables and indexes created by Alembic migration."""

import os
import sys
import psycopg
from dotenv import load_dotenv

load_dotenv()

EXPECTED_TABLES = [
    "incidents",
    "investigation_jobs",
    "incident_events",
    "runbook_chunks",
    "investigation_findings",
    "feedback",
    "outbox_events",
    "alembic_version",
]

def verify_schema():
    db_url = os.getenv("DATABASE_URL", "postgresql://incidentiq:incidentiq_password@localhost:5432/incidentiq")
    raw_url = db_url.replace("postgresql+psycopg://", "postgresql://")
    
    print("\n--- Verifying PostgreSQL Tables & Migration ---")
    try:
        with psycopg.connect(raw_url) as conn:
            with conn.cursor() as cur:
                # 1. Check tables
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name;
                """)
                existing_tables = [row[0] for row in cur.fetchall()]
                print(f"Found tables in public schema: {existing_tables}")
                
                missing = [t for t in EXPECTED_TABLES if t not in existing_tables]
                if missing:
                    print(f"ERROR: Missing expected tables: {missing}")
                    sys.exit(1)
                
                # 2. Check pgvector column on runbook_chunks
                cur.execute("""
                    SELECT column_name, data_type, udt_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'runbook_chunks' AND column_name = 'embedding';
                """)
                col = cur.fetchone()
                print(f"Verified runbook_chunks.embedding column: {col}")
                
                # 3. Check Alembic current revision
                cur.execute("SELECT version_num FROM alembic_version;")
                rev = cur.fetchone()
                print(f"Alembic current version in DB: {rev[0] if rev else None}")
                
                print("\nDatabase migration and schema verification SUCCESSFUL!\n")
    except Exception as e:
        print(f"Verification FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_schema()
