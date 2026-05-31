"""Qdrant helpers: fetch document chunks with vectors for enrichment upsert."""

import logging
import os
from typing import Any, Dict, List

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = os.environ.get("QDRANT_COLLECTION_DOCUMENTS", "documents")


def _get_client() -> QdrantClient:
    url = os.environ.get("QDRANT_URL", "http://qdrant-db:6334")
    return QdrantClient(url=url)


def fetch_document_chunks(
    document_id: str,
    collection: str = DEFAULT_COLLECTION,
) -> List[Dict[str, Any]]:
    """Scroll all Qdrant points for a document_id, including vectors.

    Returns list of dicts: {id, vector, payload}.
    Uses flat document_id field for filter (backward compatible).
    """
    client = _get_client()
    chunks: List[Dict[str, Any]] = []
    offset = None

    doc_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=document_id),
            )
        ]
    )

    while True:
        results, next_offset = client.scroll(
            collection_name=collection,
            scroll_filter=doc_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        for point in results:
            chunks.append({
                "id": point.id,
                "vector": point.vector,
                "payload": point.payload or {},
            })
        if next_offset is None:
            break
        offset = next_offset

    # Sort by chunk_index for deterministic processing
    chunks.sort(key=lambda c: c["payload"].get("core", {}).get("chunk_index", c["payload"].get("chunk_index", 0)))
    logger.info("Fetched %d chunks for document_id=%s", len(chunks), document_id)
    return chunks
