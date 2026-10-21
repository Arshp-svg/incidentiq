"""S3 storage service for raw events, snapshots, and reports."""

import json
from typing import Any
import boto3
from botocore.client import Config
from incidentiq.config import settings


class S3StorageService:
    def __init__(self) -> None:
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.bucket_name = settings.S3_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def ensure_bucket_exists(self) -> None:
        """Create bucket if it does not already exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
            except Exception:
                pass

    def upload_raw_events(self, incident_id: str, events: list[dict[str, Any]]) -> str:
        """Serialize events to JSONL and upload to incidents/{incident_id}/raw/events.jsonl."""
        s3_key = f"incidents/{incident_id}/raw/events.jsonl"
        try:
            self.ensure_bucket_exists()
            jsonl_content = "\n".join(json.dumps(evt, default=str) for evt in events) + "\n"

            self.client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=jsonl_content.encode("utf-8"),
                ContentType="application/x-ndjson",
            )
        except Exception:
            pass
        return s3_key

    def get_raw_events(self, s3_key: str) -> list[dict[str, Any]]:
        """Retrieve and parse raw JSONL events from S3."""
        response = self.client.get_object(Bucket=self.bucket_name, Key=s3_key)
        lines = response["Body"].read().decode("utf-8").strip().split("\n")
        return [json.loads(line) for line in lines if line]


s3_service = S3StorageService()
