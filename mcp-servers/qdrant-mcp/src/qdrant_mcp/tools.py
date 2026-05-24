"""MCP tools for Qdrant vector database operations.

Tools are organized into two groups:
- Collection management: create, list, inspect, delete collections
- Point operations: search, upsert chunks, delete by filter, scroll

All tools return JSON strings for consistent agent parsing.
Errors are returned as {"error": "..."} rather than raised.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from .embedder import compute_embedding, compute_embeddings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Qdrant client singleton
# ---------------------------------------------------------------------------
_client: Optional[QdrantClient] = None


def _get_client() -> QdrantClient:
    """Return the QdrantClient singleton.

    Reads QDRANT_URL from environment (default: http://qdrant-db:6334).
    """
    global _client
    if _client is None:
        import os

        url = os.environ.get("QDRANT_URL", "http://qdrant-db:6334")
        _client = QdrantClient(url=url)
        logger.info("Qdrant client connected to %s", url)
    return _client


# ---------------------------------------------------------------------------
# Collection management tools
# ---------------------------------------------------------------------------


def qdrant_create_collection(
    name: str,
    vector_size: int = 384,
    distance: str = "Cosine",
) -> str:
    """Create a new Qdrant collection for storing vector embeddings.

    Collections organize vectors into namespaces. Each collection has a fixed
    vector size and distance metric. The default 384-dim + Cosine matches
    the all-MiniLM-L6-v2 embedding model.

    Args:
        name: Unique collection name. Use snake_case (e.g., "wiki_pages",
              "document_chunks").
        vector_size: Dimensionality of the embedding vectors. Default 384
                     for all-MiniLM-L6-v2.
        distance: Distance metric for similarity search. One of "Cosine",
                  "Euclid", or "Dot". Cosine is recommended for normalized
                  embeddings.

    Returns:
        JSON with status and collection name, or error.
    """
    try:
        client = _get_client()
        dist = models.Distance.COSINE
        if distance.lower() == "euclid":
            dist = models.Distance.EUCLID
        elif distance.lower() == "dot":
            dist = models.Distance.DOT

        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=dist,
            ),
            # Store payload on disk to save RAM at scale
            on_disk_payload=True,
        )
        logger.info("Created collection '%s' (size=%d, distance=%s)", name, vector_size, distance)
        return json.dumps({"status": "created", "collection": name, "vector_size": vector_size, "distance": distance})
    except UnexpectedResponse as e:
        error_msg = f"Failed to create collection '{name}': {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Unexpected error creating collection '{name}': {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def qdrant_list_collections() -> str:
    """List all collections in the Qdrant database.

    Returns:
        JSON with a list of collection names.
    """
    try:
        client = _get_client()
        collections = client.get_collections()
        names = [c.name for c in collections.collections]
        logger.info("Listed %d collections", len(names))
        return json.dumps({"collections": names, "count": len(names)})
    except Exception as e:
        error_msg = f"Failed to list collections: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def qdrant_collection_info(name: str) -> str:
    """Get detailed information about a Qdrant collection.

    Args:
        name: The collection name.

    Returns:
        JSON with vector count, index status, segments, and config.
    """
    try:
        client = _get_client()
        info = client.get_collection(collection_name=name)
        logger.info("Retrieved info for collection '%s'", name)
        return json.dumps(str(info), default=str)
    except UnexpectedResponse:
        return json.dumps({"error": f"Collection '{name}' not found"})
    except Exception as e:
        error_msg = f"Failed to get collection info: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def qdrant_delete_collection(name: str) -> str:
    """Delete an entire collection and all its vectors.

    This operation is irreversible. Use with caution.

    Args:
        name: The collection name to delete.

    Returns:
        JSON with status.
    """
    try:
        client = _get_client()
        # Check if collection exists first for clear, idempotent semantics
        try:
            client.get_collection(collection_name=name)
        except UnexpectedResponse:
            logger.info("Collection '%s' did not exist", name)
            return json.dumps({"status": "not_found", "collection": name, "note": "Collection did not exist"})

        client.delete_collection(collection_name=name)
        logger.info("Deleted collection '%s'", name)
        return json.dumps({"status": "deleted", "collection": name})
    except Exception as e:
        error_msg = f"Failed to delete collection: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


# ---------------------------------------------------------------------------
# Point operations tools
# ---------------------------------------------------------------------------


def qdrant_search(
    collection: str,
    query_text: str,
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    score_threshold: float = 0.0,
    with_payload: bool = True,
) -> str:
    """Search for semantically similar vectors in a Qdrant collection.

    Embeds the query text using all-MiniLM-L6-v2 and performs approximate
    nearest neighbor (ANN) search via HNSW index. Results are ranked by
    cosine similarity score (higher = more similar).

    Args:
        collection: Name of the Qdrant collection to search.
        query_text: The natural language query text to embed and search with.
        limit: Maximum number of results to return (default 10).
        filters: Optional payload filters as a dict. Example:
                 {"must": [{"key": "file_type", "match": {"value": "pdf"}}]}
                 Filter keys must have payload indexes created beforehand.
        score_threshold: Minimum similarity score (0.0 to 1.0). Results below
                         this threshold are excluded.
        with_payload: Whether to include the payload in results (default True).

    Returns:
        JSON with ranked search results including id, score, and payload.
    """
    try:
        if not query_text.strip():
            return json.dumps({"error": "Query text cannot be empty"})

        client = _get_client()
        query_vector = compute_embedding(query_text)

        # Build filter object from dict if provided
        qdrant_filter = None
        if filters:
            qdrant_filter = _build_filter(filters)

        response = client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=limit,
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
            with_payload=with_payload,
        )

        formatted = []
        for hit in response.points:
            item = {
                "id": hit.id,
                "score": round(hit.score, 4),
            }
            if with_payload and hit.payload:
                item["payload"] = hit.payload
            formatted.append(item)

        logger.info(
            "Search in '%s': query='%s...' returned %d results",
            collection,
            query_text[:50],
            len(formatted),
        )
        return json.dumps({
            "query": query_text,
            "collection": collection,
            "results": formatted,
            "count": len(formatted),
        })
    except UnexpectedResponse as e:
        error_msg = f"Search failed: collection '{collection}' may not exist: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Search failed: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def qdrant_upsert_chunks(
    collection: str,
    chunks: List[Dict[str, Any]],
) -> str:
    """Insert or update vector points in a Qdrant collection.

    Each chunk must contain a 'text' field for embedding. Optional 'payload'
    dict is stored as metadata alongside the vector. If no 'id' is provided,
    a UUID is generated automatically.

    Payload best practices:
    - Include 'document_id' (source file hash) for document-level filtering
    - Include 'chunk_index' and 'source_file' for traceability
    - Include 'content_hash' for dedup and idempotent re-ingestion
    - Keep payloads under 1 KB per point for optimal performance

    Args:
        collection: Target collection name.
        chunks: List of chunk dicts, each with:
                - text (str, required): Text content to embed.
                - payload (dict, optional): Metadata to store.
                - id (str, optional): Custom point ID. Auto-generated if absent.

    Returns:
        JSON with status and count of upserted points.
    """
    try:
        if not chunks:
            return json.dumps({"error": "No chunks provided"})

        client = _get_client()

        # Extract texts and compute embeddings in batch for efficiency
        texts = [c["text"] for c in chunks]
        embeddings = compute_embeddings(texts)

        points = []
        for i, chunk in enumerate(chunks):
            point_id = chunk.get("id", str(uuid.uuid4()))
            payload = chunk.get("payload", {"text": chunk["text"]})
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embeddings[i],
                    payload=payload,
                )
            )

        client.upsert(
            collection_name=collection,
            points=points,
        )

        logger.info("Upserted %d points to collection '%s'", len(points), collection)
        return json.dumps({
            "status": "upserted",
            "collection": collection,
            "count": len(points),
        })
    except UnexpectedResponse as e:
        error_msg = f"Upsert failed: collection '{collection}' may not exist: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Upsert failed: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def qdrant_delete_by_filter(
    collection: str,
    filter: Dict[str, Any],
) -> str:
    """Delete points matching a payload filter from a Qdrant collection.

    Use this to remove all chunks belonging to a specific document or
    clean up stale data before re-ingestion.

    Args:
        collection: Target collection name.
        filter: Payload filter dict. Example to delete by document_id:
                {"must": [{"key": "document_id", "match": {"value": "abc123"}}]}

    Returns:
        JSON with status.
    """
    try:
        client = _get_client()
        qdrant_filter = _build_filter(filter)
        result = client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(filter=qdrant_filter),
        )
        logger.info(
            "Deleted points from '%s' matching filter: %s",
            collection,
            result.status,
        )
        return json.dumps({"status": "deleted", "collection": collection})
    except Exception as e:
        error_msg = f"Delete by filter failed: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def qdrant_scroll(
    collection: str,
    limit: int = 50,
    offset: Optional[str] = None,
    with_payload: bool = True,
    with_vector: bool = False,
) -> str:
    """Paginate through all points in a Qdrant collection.

    Useful for inspecting collection contents, debugging, or bulk exports.
    Not intended for search — use qdrant_search for relevance-ranked queries.

    Args:
        collection: Target collection name.
        limit: Maximum points per page (default 50).
        offset: Point ID to start scrolling from. Pass the ID from the
                "next_offset" field in the previous response for pagination.
        with_payload: Include payload data (default True).
        with_vector: Include embedding vectors (default False, vectors are
                     large and rarely needed for inspection).

    Returns:
        JSON with points list and optional next_offset for pagination.
    """
    try:
        client = _get_client()
        results, next_offset = client.scroll(
            collection_name=collection,
            limit=limit,
            offset=offset,
            with_payload=with_payload,
            with_vectors=with_vector,
        )

        points = []
        for point in results:
            item = {"id": point.id}
            if with_payload and point.payload:
                item["payload"] = point.payload
            points.append(item)

        logger.info("Scrolled %d points from '%s'", len(points), collection)
        return json.dumps({
            "collection": collection,
            "points": points,
            "count": len(points),
            "next_offset": next_offset,
        })
    except UnexpectedResponse as e:
        error_msg = f"Scroll failed: collection '{collection}' may not exist: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Scroll failed: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


# ---------------------------------------------------------------------------
# Filter builder helper
# ---------------------------------------------------------------------------


def _build_filter(filter_dict: Dict[str, Any]) -> models.Filter:
    """Convert a simplified filter dict to a Qdrant Filter object.

    Supported structure:
        {"must": [{"key": "field", "match": {"value": "exact"}}]}
        {"must": [{"key": "field", "range": {"gte": 0, "lte": 100}}]}
    """
    def _build_condition(cond: dict) -> models.FieldCondition:
        key = cond["key"]
        if "match" in cond:
            return models.FieldCondition(key=key, match=models.MatchValue(value=cond["match"]["value"]))
        if "range" in cond:
            r = cond["range"]
            return models.FieldCondition(key=key, range=models.Range(gt=r.get("gt"), gte=r.get("gte"), lt=r.get("lt"), lte=r.get("lte")))
        raise ValueError(f"Unsupported filter condition: {cond}")

    must_conditions = []
    if "must" in filter_dict:
        must_conditions = [_build_condition(c) for c in filter_dict["must"]]

    return models.Filter(must=must_conditions if must_conditions else None)
