"""Embedding generation using 384-dimensional dense vectors."""

from typing import Sequence
import numpy as np
from fastembed import TextEmbedding

# Model produces 384-dimensional dense vector embeddings matching our PostgreSQL VECTOR(384) schema
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_embedding_model: TextEmbedding | None = None


def get_embedding_model() -> TextEmbedding:
    """Singleton instance of the FastEmbed text embedding model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = TextEmbedding(model_name=MODEL_NAME)
    return _embedding_model


def embed_text(text: str) -> list[float]:
    """Generate a single 384-dim normalized embedding vector."""
    model = get_embedding_model()
    embeddings = list(model.embed([text]))
    vec = embeddings[0]
    if isinstance(vec, np.ndarray):
        return vec.tolist()
    return list(vec)


def embed_batch(texts: Sequence[str]) -> list[list[float]]:
    """Generate 384-dim normalized embedding vectors for a batch of texts."""
    model = get_embedding_model()
    embeddings = list(model.embed(texts))
    return [vec.tolist() if isinstance(vec, np.ndarray) else list(vec) for vec in embeddings]
