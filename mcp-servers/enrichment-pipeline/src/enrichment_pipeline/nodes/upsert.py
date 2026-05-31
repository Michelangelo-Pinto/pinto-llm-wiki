"""Upsert enriched payloads back to Qdrant preserving point IDs."""

import logging
import os

from qdrant_client import QdrantClient, models

from ..logger import StepTimer

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = os.environ.get("QDRANT_COLLECTION_DOCUMENTS", "documents")


def _get_qdrant() -> QdrantClient:
    url = os.environ.get("QDRANT_URL", "http://qdrant-db:6334")
    return QdrantClient(url=url)


def upsert_enriched_chunks(state: dict) -> dict:
    """Write enriched payloads to Qdrant using existing point IDs and vectors."""
    document_id = state["document_id"]
    collection = state.get("collection", DEFAULT_COLLECTION)
    chunks = state.get("enriched_chunks") or state.get("chunks", [])

    with StepTimer(state, "upsert_enriched", document_id) as timer:
        client = _get_qdrant()
        points = []

        for chunk in chunks:
            point_id = chunk.get("id")
            vector = chunk.get("vector")
            payload = chunk.get("payload", {})
            if point_id is None or vector is None:
                logger.warning("Skipping chunk without id/vector for %s", document_id)
                continue
            points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))

        if points:
            client.upsert(collection_name=collection, points=points)
            timer.extra["points_updated"] = len(points)
        else:
            timer.extra["points_updated"] = 0
            logger.warning("No points to upsert for document %s", document_id)

        state["status"] = "upserted"

    return state
