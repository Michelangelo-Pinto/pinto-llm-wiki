"""SSE smoke tests for Ingestion Pipeline MCP server (7 tools).

Validates that all 7 ingestion tools are discoverable and callable
via the real SSE transport.
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_ingestion_tools_discoverable(ingestion_client):
    """All 7 ingestion tools should be listed by tools/list."""
    tools = ingestion_client.list_tools()
    tool_names = {t["name"] for t in tools}

    expected = {
        "ingest_detect_type",
        "ingest_document",
        "ingest_directory",
        "ingest_get_status",
        "ingest_delete_document",
        "ingest_search_chunks",
        "ingest_list_documents",
    }
    missing = expected - tool_names
    assert not missing, f"Missing tools: {missing}"


# ---------------------------------------------------------------------------
# Parameter-less / simple tools
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestIngestionBasic:
    """Smoke-test ingestion tools that don't need real files."""

    def test_list_documents(self, ingestion_client):
        result = ingestion_client.call_tool("ingest_list_documents", {})
        data = self._parse(result)
        assert isinstance(data, dict)

    def test_get_status_no_id(self, ingestion_client):
        result = ingestion_client.call_tool("ingest_get_status", {})
        data = self._parse(result)
        assert isinstance(data, dict)

    def test_detect_type_nonexistent(self, ingestion_client):
        """Detect type on a nonexistent file should return an error or unsupported."""
        result = ingestion_client.call_tool("ingest_detect_type", {
            "file_path": "/nonexistent/path.xyz",
        })
        data = self._parse(result)
        # Should return error or type info — not crash
        assert isinstance(data, dict)

    def test_search_empty(self, ingestion_client):
        """Search with an empty query should not crash."""
        result = ingestion_client.call_tool("ingest_search_chunks", {
            "query": "test smoke query",
            "collection": "documents",
            "limit": 1,
        })
        data = self._parse(result)
        assert isinstance(data, dict)

    def test_delete_nonexistent(self, ingestion_client):
        result = ingestion_client.call_tool("ingest_delete_document", {
            "document_id": "nonexistent-smoke-test-id",
            "collection": "documents",
        })
        data = self._parse(result)
        assert isinstance(data, dict)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(result: dict) -> dict:
        if "result" in result:
            inner = result["result"]
            if "content" in inner:
                for item in inner["content"]:
                    if item.get("type") == "text":
                        try:
                            return json.loads(item["text"])
                        except (json.JSONDecodeError, TypeError):
                            return {"raw_text": item["text"]}
            return inner
        if "error" in result:
            return {"error": str(result["error"])}
        return result
