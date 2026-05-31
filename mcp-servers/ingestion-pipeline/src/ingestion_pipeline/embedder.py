"""Lazy-loaded SentenceTransformer embedding model for the ingestion pipeline.

Design decisions:
- all-MiniLM-L6-v2: 384-dim embeddings, ~80 MB, fast inference, pre-downloaded
  in Docker image to avoid cold-start network downloads on first request
- Lazy singleton pattern: model is loaded once on first call and shared across
  all requests. Global _model variable avoids re-loading the 80 MB model per call.
- L2 normalization (normalize_embeddings=True): ensures cosine similarity in Qdrant
  is equivalent to dot product, which is faster in HNSW index
- Single batch encoding: SentenceTransformers internally batches by token count,
  so passing the full chunk list is optimal without manual mini-batching
"""

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
