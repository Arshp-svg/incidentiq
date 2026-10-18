"""Verification script to test connectivity to PostgreSQL, Kafka, Neo4j, and MinIO."""

import os
import sys
import psycopg
from neo4j import GraphDatabase
import boto3
from kafka import KafkaProducer

def check_postgres():
    db_url = os.getenv("DATABASE_URL", "postgresql://incidentiq:incidentiq_password@localhost:5432/incidentiq")
    print("[1/4] Checking PostgreSQL & pgvector...", end=" ")
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("SELECT typname FROM pg_type WHERE typname = 'vector';")
                res = cur.fetchone()
                if res and res[0] == 'vector':
                    print("SUCCESS (PostgreSQL ready, pgvector extension enabled)")
                    return True
                else:
                    print("FAILED (pgvector extension not found)")
                    return False
    except Exception as e:
        print(f"FAILED ({e})")
        return False

def check_kafka():
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print("[2/4] Checking Apache Kafka...", end=" ")
    try:
        producer = KafkaProducer(
            bootstrap_servers=bootstrap,
            request_timeout_ms=5000,
            api_version_auto_timeout_ms=5000
        )
        partitions = producer.partitions_for("test-ping")
        producer.close()
        print(f"SUCCESS (Kafka reachable at {bootstrap})")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False

def check_neo4j():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "incidentiq_password")
    print("[3/4] Checking Neo4j...", end=" ")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        with driver.session() as session:
            result = session.run("RETURN 1 AS val")
            val = result.single()["val"]
            if val == 1:
                print(f"SUCCESS (Neo4j reachable at {uri})")
                driver.close()
                return True
        driver.close()
        print("FAILED (Unexpected result)")
        return False
    except Exception as e:
        print(f"FAILED ({e})")
        return False

def check_minio():
    endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    access = os.getenv("S3_ACCESS_KEY", "minioadmin")
    secret = os.getenv("S3_SECRET_KEY", "minioadminpassword")
    bucket = os.getenv("S3_BUCKET_NAME", "incidentiq-artifacts")
    print("[4/4] Checking MinIO (S3 API)...", end=" ")
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            region_name="us-east-1"
        )
        response = s3.list_buckets()
        buckets = [b["Name"] for b in response.get("Buckets", [])]
        print(f"SUCCESS (MinIO reachable, buckets found: {buckets})")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("\n--- Verifying IncidentIQ Infrastructure Services ---")
    p = check_postgres()
    k = check_kafka()
    n = check_neo4j()
    m = check_minio()

    if all([p, k, n, m]):
        print("\nAll 4 services are healthy and reachable!\n")
        sys.exit(0)
    else:
        print("\nOne or more services failed. Please check the logs via: docker compose logs\n")
        sys.exit(1)
