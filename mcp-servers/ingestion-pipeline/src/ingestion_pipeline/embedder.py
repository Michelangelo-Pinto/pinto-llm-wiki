"""Lazy-loaded SentenceTransformer embedding model for the ingestion pipeline."""

import logging
from typing import List

logger = logging.getLogger(__name__)

_model = None


def get_model() -> "SentenceTransformer":
    """Return the lazy-loaded sentence-transformers singleton."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: all-MiniLM-L6-v2")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded (384-dim)")
    return _model


def embed_chunks(texts: List[str]) -> List[List[float]]:
    """Generate 384-dim embeddings for a batch of text chunks."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
