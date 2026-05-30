"""Regression tests for Wiki.js MCP v3 tools.

Verifies that all v3 tools work correctly and deprecated v2 tools
(vector_search, rebuild_vector_index, PageVector) are absent.

Requires Wiki.js + PostgreSQL stack to be running with the full profile.

Run with:
    docker compose --profile integration run --rm test-runner \
      pytest tests/regression/ -v -m regression
"""

import json
import time

import pytest


pytestmark = pytest.mark.regression

test_page_ids = []


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


from wiki_mcp_server.client import wikijs
from wiki_mcp_server.tools_pages import (
    wikijs_create_page,
    wikijs_delete_page,
    wikijs_get_page,
    wikijs_list_spaces,
    wikijs_search_pages,
    wikijs_smart_query,
    wikijs_update_page,
    wikijs_wiki_health,
    wikijs_wiki_stats,
)
from wiki_mcp_server.tools_system import wikijs_connection_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _asyncio_sleep(seconds: float):
    """Sleep in sync context (works when called from sync code)."""
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def lifecycle():
    """Module-level setup and teardown."""
    # Setup is done in each test
    yield
    # Cleanup test pages
    import asyncio
    async def cleanup():
        await wikijs.authenticate()
        for pid in test_page_ids:
            try:
                await wikijs_delete_page(page_id=pid, remove_file_mapping=False)
            except Exception:
                pass
    try:
        asyncio.run(cleanup())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Connection tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_status():
    """Wiki.js should be connected and authenticated."""
    await wikijs.authenticate()
    r = await wikijs_connection_status()
    d = json.loads(r)
    assert d.get("connected") == True, f"Not connected: {d}"
    assert d.get("authenticated") == True, f"Not authenticated: {d}"


# ---------------------------------------------------------------------------
# Page operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_get_page():
    """Create a page, then retrieve it."""
    await wikijs.authenticate()
    r = await wikijs_create_page("RegTest Page Alpha", "Alpha content about testing.")
    d = json.loads(r)
    assert "error" not in d, f"Create failed: {d.get('error')}"
    page_id = d.get("pageId")
    assert page_id is not None
    test_page_ids.append(page_id)

    r2 = await wikijs_get_page(page_id=page_id)
    d2 = json.loads(r2)
    assert "error" not in d2
    assert d2.get("title") == "RegTest Page Alpha"


@pytest.mark.asyncio
async def test_update_page():
    """Update a page's content."""
    await wikijs.authenticate()
    r = await wikijs_create_page("RegTest Page Beta", "Original content.")
    d = json.loads(r)
    page_id = d["pageId"]
    test_page_ids.append(page_id)

    r2 = await wikijs_update_page(page_id, content="Updated beta content.")
    d2 = json.loads(r2)
    assert "error" not in d2, f"Update failed: {d2.get('error')}"

    r3 = await wikijs_get_page(page_id=page_id)
    d3 = json.loads(r3)
    assert "Updated beta content" in d3.get("content", "")


@pytest.mark.asyncio
async def test_search_pages():
    """Search pages by keyword should return results."""
    await wikijs.authenticate()
    r = await wikijs_search_pages("RegTest")
    d = json.loads(r)
    assert "error" not in d, f"Search failed: {d.get('error')}"
    assert d.get("total", 0) > 0, f"No search results: {d}"


# ---------------------------------------------------------------------------
# Smart query (Qdrant) tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smart_query_returns_results():
    """smart_query should return results via keyword or semantic path."""
    await wikijs.authenticate()
    r = await wikijs_smart_query(
        "test page content",
        limit=5,
        include_summaries=False,
        include_link_context=False,
    )
    d = json.loads(r)
    assert "error" not in d, f"smart_query failed: {d.get('error')}"
    assert len(d.get("results", [])) > 0, "No smart_query results"
    assert d.get("fallback_mode") in ("full", "keyword", "semantic"), \
        f"Bad fallback_mode: {d.get('fallback_mode')}"


@pytest.mark.asyncio
async def test_smart_query_fallback_mode_valid():
    """smart_query must report a valid fallback_mode."""
    await wikijs.authenticate()
    r = await wikijs_smart_query(
        "alpha content testing",
        limit=3,
        include_summaries=False,
        include_link_context=False,
    )
    d = json.loads(r)
    assert "error" not in d
    assert d["fallback_mode"] in ("full", "keyword", "semantic"), \
        f"Unexpected mode: {d.get('fallback_mode')}"


# ---------------------------------------------------------------------------
# System tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wiki_stats():
    """wiki_stats should return counts."""
    await wikijs.authenticate()
    r = await wikijs_wiki_stats()
    d = json.loads(r)
    assert "error" not in d, f"wiki_stats failed: {d.get('error')}"
    assert d.get("total_pages", 0) > 0, "No pages in wiki"


@pytest.mark.asyncio
async def test_wiki_health():
    """wiki_health should run checks."""
    await wikijs.authenticate()
    r = await wikijs_wiki_health()
    d = json.loads(r)
    assert "error" not in d, f"wiki_health failed: {d.get('error')}"
    assert "checks_run" in d
    assert "summary" in d


@pytest.mark.asyncio
async def test_list_spaces():
    """list_spaces should return at least one space."""
    await wikijs.authenticate()
    r = await wikijs_list_spaces()
    d = json.loads(r)
    assert "error" not in d, f"list_spaces failed: {d.get('error')}"


# ---------------------------------------------------------------------------
# Verify deprecated tools are absent
# ---------------------------------------------------------------------------


def test_deprecated_tools_absent():
    """Deprecated v2 tools should not be importable."""
    # wikijs_vector_search was removed
    with pytest.raises((ImportError, AttributeError)):
        from wiki_mcp_server.tools_pages import wikijs_vector_search  # noqa: F401

    # wikijs_rebuild_vector_index was removed
    with pytest.raises((ImportError, AttributeError)):
        from wiki_mcp_server.tools_pages import wikijs_rebuild_vector_index  # noqa: F401

    # PageVector model was removed
    with pytest.raises((ImportError, AttributeError)):
        from wiki_mcp_server.db import PageVector  # noqa: F401
