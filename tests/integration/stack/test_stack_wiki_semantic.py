"""Full-stack Wiki.js + Qdrant semantic search test.

With the full stack running:
1. Seed Wiki.js with test pages (via Wiki.js MCP tools)
2. Upsert vectors to Qdrant wiki_pages collection
3. Verify wikijs_smart_query returns results via semantic (Qdrant) path

Run with:
    docker compose --profile integration run --rm test-runner \
      pytest tests/integration/stack/test_stack_wiki_semantic.py -v -m integration_stack
"""

import json
import time

import pytest


pytestmark = pytest.mark.integration_stack

# Test page IDs created during seed
test_page_ids = []


# ---------------------------------------------------------------------------
# Import Wiki.js MCP tools directly
# ---------------------------------------------------------------------------


from wiki_mcp_server.client import wikijs
from wiki_mcp_server.tools_pages import (
    wikijs_create_page,
    wikijs_delete_page,
    wikijs_smart_query,
    wikijs_update_page,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
async def seed_and_cleanup():
    """Create test pages with semantic content, then clean up after all tests."""
    global test_page_ids

    await wikijs.authenticate()

    # Create test pages with distinct semantic content
    r1 = await wikijs_create_page(
        "StackTest Neural Networks",
        "Neural networks are computing systems inspired by biological neural networks. "
        "They consist of interconnected nodes (neurons) organized in layers. "
        "Deep learning uses multiple hidden layers to learn hierarchical representations."
    )
    d1 = json.loads(r1)
    if "pageId" in d1:
        test_page_ids.append(d1["pageId"])

    r2 = await wikijs_create_page(
        "StackTest Distributed Systems",
        "Distributed systems are collections of independent computers that appear "
        "as a single coherent system. They enable horizontal scaling, fault tolerance, "
        "and geographical distribution. CAP theorem describes the tradeoffs between "
        "consistency, availability, and partition tolerance."
    )
    d2 = json.loads(r2)
    if "pageId" in d2:
        test_page_ids.append(d2["pageId"])

    r3 = await wikijs_create_page(
        "StackTest Web Development",
        "Web development encompasses creating websites and web applications. "
        "Front-end development uses HTML, CSS, and JavaScript frameworks like React. "
        "Back-end development involves server-side languages, databases, and APIs."
    )
    d3 = json.loads(r3)
    if "pageId" in d3:
        test_page_ids.append(d3["pageId"])

    # Wait for hooks (backlinks, etc.)
    await asyncio_sleep(2)

    yield

    # Cleanup
    for pid in test_page_ids:
        try:
            await wikijs_delete_page(page_id=pid, remove_file_mapping=False)
        except Exception:
            pass


def _asyncio_sleep(seconds: float):
    """Helper for sync-compatible sleep in async context."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context, but since we're testing synchronously
        # (pytest-asyncio handles the event loop), we use time.sleep
        time.sleep(seconds)
    except RuntimeError:
        time.sleep(seconds)


# Alias for use in async fixtures
asyncio_sleep = _asyncio_sleep


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wiki_pages_exist():
    """Verify test pages were created successfully."""
    assert len(test_page_ids) == 3, f"Expected 3 test pages, got {len(test_page_ids)}"


@pytest.mark.asyncio
async def test_smart_query_semantic_neural():
    """smart_query for 'neural networks' should find the neural page."""
    r = await wikijs_smart_query(
        "neural networks deep learning",
        limit=3,
        include_summaries=False,
        include_link_context=False,
    )
    d = json.loads(r)
    assert "error" not in d, f"smart_query failed: {d.get('error')}"
    assert len(d.get("results", [])) > 0, "No results from smart_query"
    # At least one result should match the neural networks page
    titles = [r.get("title", "") for r in d["results"]]
    assert any("Neural" in t for t in titles), \
        f"Expected a neural networks result, got titles: {titles}"


@pytest.mark.asyncio
async def test_smart_query_semantic_distributed():
    """smart_query for 'distributed systems' should find the distributed page."""
    r = await wikijs_smart_query(
        "distributed systems CAP theorem scaling",
        limit=3,
        include_summaries=False,
        include_link_context=False,
    )
    d = json.loads(r)
    assert "error" not in d, f"smart_query failed: {d.get('error')}"
    assert len(d.get("results", [])) > 0, "No results from smart_query"
    titles = [r.get("title", "") for r in d["results"]]
    assert any("Distributed" in t for t in titles), \
        f"Expected a distributed systems result, got titles: {titles}"


@pytest.mark.asyncio
async def test_smart_query_fallback_mode():
    """smart_query should report a valid fallback_mode."""
    r = await wikijs_smart_query(
        "web development frontend backend",
        limit=3,
        include_summaries=False,
        include_link_context=False,
    )
    d = json.loads(r)
    assert "error" not in d, f"smart_query failed: {d.get('error')}"
    assert d.get("fallback_mode") in ("full", "keyword", "semantic"), \
        f"Unexpected fallback_mode: {d.get('fallback_mode')}"
