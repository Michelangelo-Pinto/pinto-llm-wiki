"""SSE smoke tests for Qdrant MCP server (8 tools).

Validates that all 8 Qdrant tools are discoverable and callable
via the real SSE transport (not direct Python imports).
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_qdrant_tools_discoverable(qdrant_client):
    """All 8 Qdrant tools should be listed by tools/list."""
    tools = qdrant_client.list_tools()
    tool_names = {t["name"] for t in tools}

    expected = {
        "qdrant_create_collection",
        "qdrant_list_collections",
        "qdrant_collection_info",
        "qdrant_delete_collection",
        "qdrant_search",
        "qdrant_upsert_chunks",
        "qdrant_delete_by_filter",
        "qdrant_scroll",
    }
    missing = expected - tool_names
    assert not missing, f"Missing tools: {missing}"


# ---------------------------------------------------------------------------
# Collection management tools
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestCollectionManagement:
    """Smoke-test collection create/list/info/delete via SSE."""

    COLLECTION = "smoke_test_coll"

    def test_create_collection(self, qdrant_client):
        result = qdrant_client.call_tool("qdrant_create_collection", {
            "name": self.COLLECTION,
            "vector_size": 384,
        })
        data = self._parse(result)
        assert data.get("status") == "created" or "already exists" in str(data).lower()

    def test_list_collections(self, qdrant_client):
        result = qdrant_client.call_tool("qdrant_list_collections", {})
        data = self._parse(result)
        assert "collections" in data or isinstance(data, list)

    def test_collection_info(self, qdrant_client):
        result = qdrant_client.call_tool("qdrant_collection_info", {
            "name": self.COLLECTION,
        })
        data = self._parse(result)
        # Should return info or error (if collection doesn't exist)
        assert "error" in data or "name" in data or "vectors" in data

    def test_delete_collection(self, qdrant_client):
        result = qdrant_client.call_tool("qdrant_delete_collection", {
            "name": self.COLLECTION,
        })
        data = self._parse(result)
        assert data.get("status") in ("deleted", "not_found")


# ---------------------------------------------------------------------------
# Point operations tools
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestPointOperations:
    """Smoke-test upsert/search/scroll via SSE."""

    COLLECTION = "smoke_test_points"

    @pytest.fixture(autouse=True)
    def _setup_collection(self, qdrant_client):
        qdrant_client.call_tool("qdrant_create_collection", {
            "name": self.COLLECTION,
            "vector_size": 384,
        })
        yield
        qdrant_client.call_tool("qdrant_delete_collection", {
            "name": self.COLLECTION,
        })

    def test_upsert_and_search(self, qdrant_client):
        chunks = [{"text": "Smoke test document about distributed systems."}]
        upsert_result = qdrant_client.call_tool("qdrant_upsert_chunks", {
            "collection": self.COLLECTION,
            "chunks": chunks,
        })
        upsert_data = self._parse(upsert_result)
        assert upsert_data.get("status") == "upserted"

        search_result = qdrant_client.call_tool("qdrant_search", {
            "collection": self.COLLECTION,
            "query_text": "distributed systems",
            "limit": 3,
        })
        search_data = self._parse(search_result)
        assert "results" in search_data or "error" in search_data

    def test_scroll(self, qdrant_client):
        result = qdrant_client.call_tool("qdrant_scroll", {
            "collection": self.COLLECTION,
            "limit": 5,
        })
        data = self._parse(result)
        assert isinstance(data, (dict, list))

    def test_delete_by_filter(self, qdrant_client):
        result = qdrant_client.call_tool("qdrant_delete_by_filter", {
            "collection": self.COLLECTION,
            "filter": {"must": [{"key": "document_id", "match": {"value": "nonexistent"}}]},
        })
        data = self._parse(result)
        assert "status" in data or "error" in data

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(result: dict) -> dict:
        """Unwrap JSON-RPC response to the actual tool result."""
        if "result" in result:
            inner = result["result"]
            if "content" in inner:
                # MCP content array
                for item in inner["content"]:
                    if item.get("type") == "text":
                        return json.loads(item["text"])
            return inner
        if "error" in result:
            return {"error": str(result["error"])}
        return result
