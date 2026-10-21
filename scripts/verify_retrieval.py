"""Verify RAG pipeline: Ingest runbooks, store pgvector embeddings, and test semantic search."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from incidentiq.retrieval.indexer import index_all_runbooks
from incidentiq.retrieval.search import search_runbooks


def verify_retrieval():
    print("\n--- Day 2 Task 1: Ingesting Runbooks & Verifying pgvector Retrieval ---")

    # 1. Ingest and embed runbooks
    print("[1/3] Indexing markdown runbooks into PostgreSQL and MinIO...", end=" ")
    results = index_all_runbooks()
    total_chunks = sum(results.values())
    print(f"DONE ({len(results)} files indexed, {total_chunks} total chunks)")
    for filename, count in results.items():
        print(f"  - {filename}: {count} chunks")

    assert total_chunks > 0, "No chunks were indexed!"

    # 2. Test semantic query: Database latency
    query1 = "checkout service database query timeout and latency"
    print(f"\n[2/3] Querying pgvector for: '{query1}'...")
    matches1 = search_runbooks(query=query1, top_k=2)
    for m in matches1:
        print(f"  -> [{m['similarity_score']}] {m['document_name']} (Section: {m['section']})")

    assert len(matches1) > 0, "No results returned for query 1"
    top_doc = matches1[0]["document_name"]
    assert "checkout" in top_doc or "latency" in top_doc, f"Unexpected top document: {top_doc}"
    assert matches1[0]["similarity_score"] > 0.5, f"Low similarity score: {matches1[0]['similarity_score']}"

    # 3. Test semantic query: Payment gateway outage
    query2 = "third-party payment gateway outage 504 gateway timeout"
    print(f"\n[3/3] Querying pgvector for: '{query2}'...")
    matches2 = search_runbooks(query=query2, top_k=2)
    for m in matches2:
        print(f"  -> [{m['similarity_score']}] {m['document_name']} (Section: {m['section']})")

    assert len(matches2) > 0, "No results returned for query 2"
    assert "payment" in matches2[0]["document_name"], f"Expected payment runbook, got {matches2[0]['document_name']}"
    assert matches2[0]["similarity_score"] > 0.5, f"Low similarity score: {matches2[0]['similarity_score']}"

    print("\npgvector runbook ingestion and semantic retrieval verification SUCCESSFUL!\n")


if __name__ == "__main__":
    verify_retrieval()
