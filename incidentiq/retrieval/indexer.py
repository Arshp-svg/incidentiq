"""Runbook parser, chunker, embedder, and database indexer."""

import re
import uuid
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from incidentiq.db.session import SessionLocal
from incidentiq.db.models import RunbookChunk
from incidentiq.retrieval.embeddings import embed_batch
from incidentiq.storage.s3 import s3_service


def parse_markdown_into_chunks(content: str, doc_name: str) -> list[dict[str, Any]]:
    """Split a runbook into logical section chunks with metadata."""
    # Extract service name if defined in header
    service_match = re.search(r"##\s*Service:\s*([^\n]+)", content, re.IGNORECASE)
    service_name = service_match.group(1).strip() if service_match else "general"

    # Split on headers (## or ###)
    sections = re.split(r"(?m)^(?=##\s+)", content)
    chunks = []
    chunk_index = 0

    for sec in sections:
        sec_text = sec.strip()
        if not sec_text:
            continue

        # Extract section title
        header_match = re.match(r"##\s*([^\n]+)", sec_text)
        section_title = header_match.group(1).strip() if header_match else "Overview"

        chunks.append({
            "document_name": doc_name,
            "chunk_index": chunk_index,
            "content": sec_text,
            "metadata": {
                "source": doc_name,
                "service": service_name,
                "section": section_title,
            },
        })
        chunk_index += 1

    return chunks


def index_runbook_file(db: Session, file_path: Path) -> int:
    """Index a single markdown runbook into PostgreSQL and MinIO."""
    doc_name = file_path.stem
    content = file_path.read_text(encoding="utf-8")

    # 1. Upload source runbook to S3 (Blueprint layout: runbooks/{document_id}/source.md)
    s3_key = f"runbooks/{doc_name}/source.md"
    s3_service.client.put_object(
        Bucket=s3_service.bucket_name,
        Key=s3_key,
        Body=content.encode("utf-8"),
        ContentType="text/markdown",
    )

    # 2. Chunk markdown
    chunks = parse_markdown_into_chunks(content, doc_name)
    if not chunks:
        return 0

    # 3. Batch generate 384-dim embeddings
    texts = [c["content"] for c in chunks]
    embeddings = embed_batch(texts)

    # 4. Upsert into runbook_chunks
    for c, emb in zip(chunks, embeddings):
        stmt = insert(RunbookChunk).values(
            id=uuid.uuid4(),
            document_name=c["document_name"],
            chunk_index=c["chunk_index"],
            content=c["content"],
            metadata_=c["metadata"],
            embedding=emb,
        ).on_conflict_do_update(
            constraint="uq_runbook_document_chunk",
            set_={
                "content": c["content"],
                "metadata": c["metadata"],
                "embedding": emb,
            },
        )
        db.execute(stmt)

    db.commit()
    return len(chunks)


def index_all_runbooks(runbooks_dir: Path | None = None) -> dict[str, int]:
    """Index all markdown files from the runbooks directory."""
    if runbooks_dir is None:
        runbooks_dir = Path(__file__).resolve().parents[2] / "data" / "runbooks"

    results = {}
    with SessionLocal() as db:
        for md_file in runbooks_dir.glob("*.md"):
            indexed_count = index_runbook_file(db, md_file)
            results[md_file.name] = indexed_count

    return results
