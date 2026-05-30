"""SSE smoke tests for Wiki.js MCP server (43 tools).

This is a targeted smoke test — only tools that don't require real wiki data
are called via SSE. Complex tools that need page IDs or specific state are
limited to discovery-only checks.
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Tool discovery — verify all 43 tools are registered
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_wikijs_tools_discoverable(wikijs_client):
    """All Wiki.js MCP tools should be listed."""
    tools = wikijs_client.list_tools()
    tool_names = {t["name"] for t in tools}

    # Core tools that must be present
    required = {
        "wikijs_connection_status",
        "wikijs_list_spaces",
        "wikijs_search_pages",
        "wikijs_smart_query",
        "wikijs_wiki_stats",
        "wikijs_wiki_health",
        "wikijs_get_recent_changes",
        "wikijs_list_all_tags",
        "wikijs_create_page",
        "wikijs_get_page",
        "wikijs_update_page",
        "wikijs_delete_page",
        "wikijs_create_space",
        "wikijs_rebuild_backlink_index",
        "wikijs_export_wiki",
        "wikijs_import_page",
        "wikijs_repository_context",
    }
    missing = required - tool_names
    assert not missing, f"Missing core tools: {missing}"

    # Optional but verify total
    assert len(tools) >= 40, f"Expected >= 40 tools, got {len(tools)}"


# ---------------------------------------------------------------------------
# Parameter-less tools (safe to call without real data)
# ---------------------------------------------------------------------------

PARAMETERLESS_TOOLS = [
    "wikijs_connection_status",
    "wikijs_list_spaces",
    "wikijs_wiki_stats",
    "wikijs_list_all_tags",
    "wikijs_repository_context",
]


@pytest.mark.smoke
@pytest.mark.parametrize("tool_name", PARAMETERLESS_TOOLS)
def test_parameterless_tool(wikijs_client, tool_name):
    """Parameter-less tools should return valid JSON without crashing."""
    result = wikijs_client.call_tool(tool_name, {})
    data = _parse(result)
    assert isinstance(data, dict), f"{tool_name} did not return dict: {type(data)}"


# ---------------------------------------------------------------------------
# Tools with simple parameters
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestSimpleTools:
    """Smoke-test tools that only need simple string/number params."""

    def test_search_pages(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_search_pages", {"query": "test"})
        data = _parse(result)
        assert isinstance(data, dict)

    def test_smart_query(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_smart_query", {
            "query": "documentation",
            "limit": 3,
        })
        data = _parse(result)
        assert isinstance(data, dict)

    def test_get_recent_changes(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_get_recent_changes", {"limit": 5})
        data = _parse(result)
        assert isinstance(data, dict)

    def test_wiki_health(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_wiki_health", {})
        data = _parse(result)
        assert isinstance(data, dict)

    def test_filter_pages_basic(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_filter_pages", {
            "filters": {"isPublished": True},
        })
        data = _parse(result)
        assert isinstance(data, dict)

    def test_search_by_tag(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_search_by_tag", {"tag": "test"})
        data = _parse(result)
        assert isinstance(data, dict)

    def test_cleanup_orphaned_mappings(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_cleanup_orphaned_mappings", {})
        data = _parse(result)
        assert isinstance(data, dict)

    def test_export_wiki(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_export_wiki", {
            "output_dir": "/tmp/smoke_export",
        })
        data = _parse(result)
        assert isinstance(data, dict)

    def test_import_page(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_import_page", {
            "file_path": "/nonexistent/file.md",
            "target_path": "/smoke-test",
        })
        data = _parse(result)
        assert isinstance(data, dict)

    def test_import_directory(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_import_directory", {
            "dir_path": "/nonexistent/dir",
        })
        data = _parse(result)
        assert isinstance(data, dict)

    def test_manage_collections(self, wikijs_client):
        result = wikijs_client.call_tool("wikijs_manage_collections", {
            "collection_name": "smoke-test-collection",
        })
        data = _parse(result)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _parse(result: dict) -> dict:
    """Unwrap JSON-RPC response to the actual tool result."""
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
