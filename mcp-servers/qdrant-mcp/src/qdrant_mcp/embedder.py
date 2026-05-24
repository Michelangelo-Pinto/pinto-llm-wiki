"""Lazy-loaded SentenceTransformer embedding model.

Uses all-MiniLM-L6-v2 (384 dimensions) which is the same model used
by the ingestion pipeline and Qdrant's own default configuration.
The model is loaded once and reused across all tool calls via a module-level singleton.

Cold start: ~2s for model download + load (~80 MB memory).
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

_model = None


def get_model() -> "SentenceTransformer":
    """Return the lazy-loaded SentenceTransformer singleton.

    The model is loaded on first access and cached for subsequent calls.
    Thread-safe in practice because FastMCP async tools run sequentially.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: all-MiniLM-L6-v2")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded (384-dim vectors)")
    return _model


def compute_embedding(text: str) -> List[float]:
    """Generate a 384-dim embedding vector for the given text.

    Args:
        text: The text to embed. Should be pre-chunked and trimmed.

    Returns:
        A list of 384 floats representing the embedding vector.
    """
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def compute_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embedding vectors for a batch of texts.

    Args:
        texts: List of text strings to embed. Batch encoding is more efficient
               than calling compute_embedding in a loop.

    Returns:
        List of embedding vectors, each a list of 384 floats.
    """
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
