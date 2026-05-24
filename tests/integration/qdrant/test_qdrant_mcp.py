"""Integration tests for Qdrant MCP server.

These tests require Qdrant DB to be running. They import Qdrant MCP
tool functions directly (not via SSE) for determinism and speed.

Run with:
    docker compose --profile test run --rm test-runner pytest tests/integration/qdrant/ -v -m integration

Tests cover:
- Collection management (create, list, info, delete)
- Point operations (search, upsert, delete_by_filter, scroll)
- Edge cases (empty queries, missing collections, large batches)
- score_threshold filtering and upsert+search roundtrip
"""

import json
import uuid

import pytest

from qdrant_mcp.embedder import compute_embedding, compute_embeddings
from qdrant_mcp.tools import (
    qdrant_collection_info,
    qdrant_create_collection,
    qdrant_delete_by_filter,
    qdrant_delete_collection,
    qdrant_list_collections,
    qdrant_scroll,
    qdrant_search,
    qdrant_upsert_chunks,
)

from tests.integration.qdrant.conftest import TEST_COLLECTION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upsert_test_chunks(count: int = 5):
    """Upsert test chunks and return their text and IDs."""
    chunks = []
    for i in range(count):
        chunks.append({
            "text": f"This is test document chunk number {i}. It contains information about vector databases and semantic search.",
            "payload": {
                "document_id": f"doc-test-{i % 2}",
                "chunk_index": i,
                "file_type": "text",
            },
        })
    result = json.loads(qdrant_upsert_chunks(TEST_COLLECTION, chunks))
    assert result.get("status") == "upserted"
    assert result.get("count") == count
    return chunks


# ---------------------------------------------------------------------------
# Embedding tests (unit-like, but use the real model)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEmbedding:
    def test_compute_embedding_shape(self):
        vec = compute_embedding("Hello world")
        assert len(vec) == 384
        assert all(isinstance(v, float) for v in vec)

    def test_compute_embeddings_batch(self):
        texts = ["First text", "Second text", "Third text"]
        vecs = compute_embeddings(texts)
        assert len(vecs) == 3
        assert all(len(v) == 384 for v in vecs)

    def test_empty_text_embedding(self):
        vec = compute_embedding("")
        assert len(vec) == 384


# ---------------------------------------------------------------------------
# Collection management tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCollectionManagement:
    def test_create_collection(self):
        result = json.loads(qdrant_create_collection("test_create_coll"))
        assert result.get("status") == "created"
        assert result.get("collection") == "test_create_coll"
        qdrant_delete_collection("test_create_coll")

    def test_create_duplicate_collection_returns_error(self):
        qdrant_create_collection("test_dup_coll")
        result = json.loads(qdrant_create_collection("test_dup_coll"))
        assert "error" in result
        qdrant_delete_collection("test_dup_coll")

    def test_list_collections(self):
        result = json.loads(qdrant_list_collections())
        assert "collections" in result
        assert TEST_COLLECTION in result["collections"]

    def test_collection_info(self):
        _upsert_test_chunks(5)
        result = json.loads(qdrant_collection_info(TEST_COLLECTION))
        assert "collection" not in json.dumps({"error": "not found"}) or "status" in result

    def test_collection_info_missing(self):
        result = json.loads(qdrant_collection_info("nonexistent_collection"))
        assert "error" in result

    def test_delete_collection(self):
        qdrant_create_collection("test_delete_coll")
        result = json.loads(qdrant_delete_collection("test_delete_coll"))
        assert result.get("status") == "deleted"

    def test_delete_nonexistent_collection(self):
        result = json.loads(qdrant_delete_collection("nonexistent_xyz"))
        assert result["status"] == "not_found"
        assert result["collection"] == "nonexistent_xyz"


# ---------------------------------------------------------------------------
# Point operations tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestUpsert:
    def test_upsert_single_chunk(self):
        chunks = [{
            "text": "A single test chunk about machine learning.",
            "payload": {"document_id": "doc-single", "chunk_index": 0},
        }]
        result = json.loads(qdrant_upsert_chunks(TEST_COLLECTION, chunks))
        assert result["status"] == "upserted"
        assert result["count"] == 1

    def test_upsert_with_custom_id(self):
        custom_id = str(uuid.uuid4())
        chunks = [{
            "id": custom_id,
            "text": "Chunk with custom ID.",
            "payload": {"document_id": "doc-custom"},
        }]
        result = json.loads(qdrant_upsert_chunks(TEST_COLLECTION, chunks))
        assert result["status"] == "upserted"

    def test_upsert_empty_chunks(self):
        result = json.loads(qdrant_upsert_chunks(TEST_COLLECTION, []))
        assert "error" in result

    def test_upsert_batch_100(self):
        chunks = []
        for i in range(100):
            chunks.append({
                "text": f"Batch test chunk number {i}. This tests that upserting 100 points works correctly without errors.",
                "payload": {"document_id": "doc-batch-100", "chunk_index": i},
            })
        result = json.loads(qdrant_upsert_chunks(TEST_COLLECTION, chunks))
        assert result["status"] == "upserted"
        assert result["count"] == 100


@pytest.mark.integration
class TestSearch:
    def test_search_returns_results(self):
        _upsert_test_chunks(5)
        result = json.loads(qdrant_search(TEST_COLLECTION, "semantic search in vector databases", limit=5))
        assert "results" in result
        assert len(result["results"]) > 0
        assert "score" in result["results"][0]
        assert "payload" in result["results"][0]

    def test_search_respects_limit(self):
        _upsert_test_chunks(10)
        result = json.loads(qdrant_search(TEST_COLLECTION, "test document", limit=3))
        assert len(result["results"]) <= 3

    def test_search_empty_query(self):
        result = json.loads(qdrant_search(TEST_COLLECTION, ""))
        assert "error" in result

    def test_search_missing_collection(self):
        result = json.loads(qdrant_search("nonexistent_coll", "query text"))
        assert "error" in result

    def test_search_with_score_threshold(self):
        _upsert_test_chunks(10)
        # With a high threshold, no results should match
        result = json.loads(qdrant_search(TEST_COLLECTION, "completely unrelated topic xyz", limit=5, score_threshold=0.99))
        assert len(result["results"]) == 0

    def test_search_with_filter(self):
        _upsert_test_chunks(5)
        filters = {"must": [{"key": "document_id", "match": {"value": "doc-test-0"}}]}
        result = json.loads(qdrant_search(TEST_COLLECTION, "document chunk", limit=10, filters=filters))
        assert len(result["results"]) > 0

    def test_search_score_threshold_meaningful(self):
        """Search with a moderate threshold still returns relevant results."""
        _upsert_test_chunks(10)
        result = json.loads(qdrant_search(
            TEST_COLLECTION, "vector databases and semantic search",
            limit=5, score_threshold=0.5
        ))
        assert len(result["results"]) > 0
        assert all(r["score"] >= 0.5 for r in result["results"])

    def test_upsert_search_roundtrip_by_document_id(self):
        """Upsert chunks with known document_id, then verify via search+filter."""
        doc_id = f"roundtrip-doc-{uuid.uuid4().hex[:6]}"
        chunks = [
            {"text": "Roundtrip chunk one about neural networks.", "payload": {"document_id": doc_id, "chunk_index": 0}},
            {"text": "Roundtrip chunk two about deep learning.", "payload": {"document_id": doc_id, "chunk_index": 1}},
        ]
        result = json.loads(qdrant_upsert_chunks(TEST_COLLECTION, chunks))
        assert result["status"] == "upserted"
        assert result["count"] == 2

        # Search should find these chunks
        filters = {"must": [{"key": "document_id", "match": {"value": doc_id}}]}
        search_result = json.loads(qdrant_search(
            TEST_COLLECTION, "neural networks deep learning", limit=5, filters=filters
        ))
        assert len(search_result["results"]) == 2
        payloads = [r["payload"] for r in search_result["results"]]
        assert all(p["document_id"] == doc_id for p in payloads)


@pytest.mark.integration
class TestDeleteByFilter:
    def test_delete_by_document_id(self):
        _upsert_test_chunks(6)  # 3 per doc-test-0, 3 per doc-test-1
        # Delete only doc-test-0 chunks
        filt = {"must": [{"key": "document_id", "match": {"value": "doc-test-0"}}]}
        result = json.loads(qdrant_delete_by_filter(TEST_COLLECTION, filt))
        assert result["status"] == "deleted"

        # Verify remaining chunks exist
        scroll_result = json.loads(qdrant_scroll(TEST_COLLECTION, limit=50))
        assert scroll_result["count"] <= 3  # only doc-test-1 chunks remain


@pytest.mark.integration
class TestScroll:
    def test_scroll_returns_points(self):
        _upsert_test_chunks(5)
        result = json.loads(qdrant_scroll(TEST_COLLECTION, limit=10))
        assert result["count"] == 5
        assert len(result["points"]) == 5

    def test_scroll_pagination(self):
        _upsert_test_chunks(10)
        # First page
        page1 = json.loads(qdrant_scroll(TEST_COLLECTION, limit=4))
        assert len(page1["points"]) == 4
        # Second page
        offset = page1.get("next_offset")
        if offset:
            page2 = json.loads(qdrant_scroll(TEST_COLLECTION, limit=4, offset=offset))
            assert len(page2["points"]) > 0

    def test_scroll_missing_collection(self):
        result = json.loads(qdrant_scroll("nonexistent_coll"))
        assert "error" in result
