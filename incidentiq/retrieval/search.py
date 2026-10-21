"""Vector similarity search over runbook chunks using PostgreSQL pgvector."""

from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from incidentiq.db.session import SessionLocal
from incidentiq.retrieval.embeddings import embed_text


def search_runbooks(
    query: str,
    top_k: int = 3,
    service_name: str | None = None,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    """Search runbook chunks by semantic similarity using pgvector cosine distance."""
    if not query.strip():
        return []

    # 1. Embed search query into 384-dimensional vector
    query_vector = embed_text(query)
    vector_str = f"[{','.join(str(x) for x in query_vector)}]"

    # 2. Build parameterized SQL query using cosine distance (<=> operator)
    if service_name:
        sql = text("""
            SELECT 
                document_name,
                chunk_index,
                content,
                metadata,
                1 - (embedding <=> CAST(:vector AS vector)) AS similarity_score
            FROM runbook_chunks
            WHERE metadata->>'service' = :service_name OR metadata->>'service' = 'general'
            ORDER BY embedding <=> CAST(:vector AS vector)
            LIMIT :top_k;
        """)
        params = {"vector": vector_str, "top_k": top_k, "service_name": service_name}
    else:
        sql = text("""
            SELECT 
                document_name,
                chunk_index,
                content,
                metadata,
                1 - (embedding <=> CAST(:vector AS vector)) AS similarity_score
            FROM runbook_chunks
            ORDER BY embedding <=> CAST(:vector AS vector)
            LIMIT :top_k;
        """)
        params = {"vector": vector_str, "top_k": top_k}

    def _execute(session: Session) -> list[dict[str, Any]]:
        result = session.execute(sql, params)
        rows = []
        for r in result:
            rows.append({
                "document_name": r.document_name,
                "chunk_index": r.chunk_index,
                "section": r.metadata.get("section", "General") if isinstance(r.metadata, dict) else "General",
                "service": r.metadata.get("service", "unknown") if isinstance(r.metadata, dict) else "unknown",
                "similarity_score": round(float(r.similarity_score), 4),
                "content": r.content,
            })
        return rows

    if db is not None:
        return _execute(db)

    with SessionLocal() as session:
        return _execute(session)
