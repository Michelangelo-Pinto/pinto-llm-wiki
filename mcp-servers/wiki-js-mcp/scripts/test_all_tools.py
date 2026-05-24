#!/usr/bin/env python3
"""
Wiki.js MCP — Comprehensive Test Suite (v3)

Tests all MCP tools. Self-contained: creates test data, runs tests, cleans up.
For pytest-based regression tests, see: tests/regression/test_wiki_tools.py

Run inside Docker:
    docker compose exec -T wiki-js-mcp python3 /app/scripts/test_all_tools.py

Or with pytest:
    docker compose --profile integration run --rm test-runner \
      pytest tests/regression/ -v -m regression
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

# Ensure the MCP server source is on the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from wiki_mcp_server.client import wikijs
from wiki_mcp_server.db import get_db, BacklinkIndex
from wiki_mcp_server.tools_pages import (
    wikijs_append_to_page,
    wikijs_bulk_get_page_stats,
    wikijs_bulk_get_pages,
    wikijs_create_page,
    wikijs_create_space,
    wikijs_filter_pages,
    wikijs_get_affected_pages,
    wikijs_get_backlinks,
    wikijs_get_page,
    wikijs_get_page_stats,
    wikijs_get_recent_changes,
    wikijs_list_all_tags,
    wikijs_list_spaces,
    wikijs_rebuild_backlink_index,
    wikijs_search_by_tag,
    wikijs_search_pages,
    wikijs_set_page_tags,
    wikijs_smart_query,
    wikijs_update_page,
    wikijs_wiki_health,
    wikijs_wiki_stats,
    wikijs_export_wiki,
    wikijs_export_page,
    wikijs_import_page,
    wikijs_import_directory,
)
from wiki_mcp_server.tools_graph import (
    wikijs_extract_page_links,
    wikijs_find_shortest_path,
    wikijs_get_page_graph,
)
from wiki_mcp_server.tools_hierarchy import (
    wikijs_create_documentation_hierarchy,
    wikijs_create_nested_page,
    wikijs_create_repo_structure,
    wikijs_get_page_children,
)
from wiki_mcp_server.tools_files import (
    wikijs_bulk_update_project_docs,
    wikijs_generate_file_overview,
    wikijs_link_file_to_page,
    wikijs_sync_file_docs,
)
from wiki_mcp_server.tools_deletion import (
    wikijs_batch_delete_pages,
    wikijs_cleanup_orphaned_mappings,
    wikijs_delete_hierarchy,
    wikijs_delete_page,
)
from wiki_mcp_server.tools_system import (
    wikijs_connection_status,
    wikijs_manage_collections,
    wikijs_repository_context,
)

passed = 0
failed = 0
test_num = 0
start_time = 0.0

test_ids = []          # IDs of test pages created
test_results = []      # List of (num, name, passed, detail)


def check(test_name: str, condition: bool, detail: str = ""):
    """Assert a test condition and record the result."""
    global passed, failed, test_num
    test_num += 1
    if condition:
        passed += 1
        msg = f"  PASS: {test_name}"
        if detail:
            msg += f" ({detail})"
        print(msg)
    else:
        failed += 1
        msg = f"  FAIL: {test_name}"
        if detail:
            msg += f" — {detail}"
        print(msg)
    test_results.append((test_num, test_name, condition, detail))


def assert_no_error(d: dict, test_name: str):
    """Verify the response has no error key."""
    if "error" in d:
        check(test_name, False, d["error"])
        return False
    return True


async def setup_test_data() -> int:
    """Create test pages with tags, links, and content. Returns the wiki page count before tests."""
    await wikijs.authenticate()

    # Get initial page count
    resp = await wikijs.graphql_request("""
    query { pages { list { id } } }
    """)
    initial_pages = resp.get("data", {}).get("pages", {}).get("list", [])
    initial_count = len(initial_pages)

    # Create test pages with hierarchical tags and cross-links
    r1 = await wikijs_create_page("Test Alpha", "This is alpha content about databases and SQL queries.")
    d1 = json.loads(r1)
    assert_no_error(d1, "create Test Alpha")
    test_ids.append(d1.get("pageId"))
    await wikijs_set_page_tags(d1["pageId"], ["tech", "tech/database"])
    await wikijs_update_page(d1["pageId"], content="This is alpha content about databases and SQL queries. See [Test Beta](test-beta) for more.")

    r2 = await wikijs_create_page("Test Beta", "This is beta content about API design and REST endpoints.")
    d2 = json.loads(r2)
    assert_no_error(d2, "create Test Beta")
    test_ids.append(d2.get("pageId"))
    await wikijs_set_page_tags(d2["pageId"], ["tech", "tech/api"])
    await wikijs_update_page(d2["pageId"], content="This is beta content about API design and REST endpoints. See [Test Alpha](test-alpha) and [https://example.com](https://example.com) for external docs.")

    r3 = await wikijs_create_page("Test Gamma", "This is gamma content with no tags and no links.")
    d3 = json.loads(r3)
    assert_no_error(d3, "create Test Gamma")
    test_ids.append(d3.get("pageId"))

    r4 = await wikijs_create_page("Test Delta", "This is delta content about semantic search and vector embeddings.")
    d4 = json.loads(r4)
    assert_no_error(d4, "create Test Delta")
    test_ids.append(d4.get("pageId"))
    await wikijs_set_page_tags(d4["pageId"], ["science", "tech/ai"])

    # Wait briefly for hooks (backlinks, vectors)
    await asyncio.sleep(1)

    print(f"\n  Setup: {initial_count} existing pages, {len(test_ids)} test pages created\n")
    return initial_count


async def cleanup_test_data():
    """Delete all test pages."""
    for pid in test_ids:
        try:
            r = await wikijs_delete_page(page_id=pid, remove_file_mapping=False)
        except Exception:
            pass
    print(f"\n  Cleanup: {len(test_ids)} test pages deleted")


async def test_page_tools(initial_count: int):
    """Test 22 page management tools."""
    print("\n--- Page Tools (22) ---")

    # 1. wikijs_get_page
    r = await wikijs_get_page(page_id=test_ids[0])
    d = json.loads(r)
    if assert_no_error(d, "get_page"):
        check("get_page returns title", d.get("title") == "Test Alpha")
        check("get_page returns content", "databases" in d.get("content", ""))

    # 2. wikijs_update_page
    r = await wikijs_update_page(test_ids[2], content="Updated gamma content.")
    d = json.loads(r)
    check("update_page", assert_no_error(d, "update_page"))

    # 3. wikijs_search_pages
    r = await wikijs_search_pages("database")
    d = json.loads(r)
    if assert_no_error(d, "search_pages"):
        check("search_pages finds results", d.get("total", 0) > 0, f"total={d.get('total')}")

    # 4. wikijs_list_spaces
    r = await wikijs_list_spaces()
    d = json.loads(r)
    check("list_spaces", assert_no_error(d, "list_spaces"))

    # 5. wikijs_create_space
    ts = int(time.time())
    r = await wikijs_create_space(f"TestSpace{ts}", "Test space description")
    d = json.loads(r)
    space_created = assert_no_error(d, "create_space")
    check("create_space", space_created)

    # 6. wikijs_bulk_get_pages
    r = await wikijs_bulk_get_pages(test_ids[:3])
    d = json.loads(r)
    if assert_no_error(d, "bulk_get_pages"):
        check("bulk_get_pages returns results", d["summary"]["returned"] >= 3, str(d["summary"]))

    # 7. wikijs_bulk_get_pages with dedup
    r = await wikijs_bulk_get_pages([test_ids[0], test_ids[0], test_ids[1]])
    d = json.loads(r)
    if assert_no_error(d, "bulk_get_pages dedup"):
        check("bulk_get_pages deduplicates", d["summary"]["returned"] == 2, str(d["summary"]))

    # 8. wikijs_bulk_get_pages without content
    r = await wikijs_bulk_get_pages(test_ids[:2], include_content=False)
    d = json.loads(r)
    if assert_no_error(d, "bulk_get_pages no_content"):
        has_content = "content" in d["results"][0] if d["results"] else False
        check("bulk_get_pages omits content", not has_content)

    # 9. wikijs_get_backlinks
    r = await wikijs_get_backlinks(test_ids[0])
    d = json.loads(r)
    check("get_backlinks", assert_no_error(d, "get_backlinks"))

    # 10. wikijs_rebuild_backlink_index
    r = await wikijs_rebuild_backlink_index()
    d = json.loads(r)
    if assert_no_error(d, "rebuild_backlink_index"):
        check("rebuild_backlink_index completed", d.get("status") == "completed")

    # 11. wikijs_get_page_stats
    r = await wikijs_get_page_stats(test_ids[0])
    d = json.loads(r)
    if assert_no_error(d, "get_page_stats"):
        check("get_page_stats has wordCount", "wordCount" in d)
        check("get_page_stats has tags", "tags" in d)

    # 12. wikijs_bulk_get_page_stats
    r = await wikijs_bulk_get_page_stats(test_ids[:2])
    d = json.loads(r)
    if assert_no_error(d, "bulk_get_page_stats"):
        check("bulk_get_page_stats returns results", d["summary"]["returned"] >= 2, str(d["summary"]))

    # 13. wikijs_append_to_page — append
    r = await wikijs_append_to_page(test_ids[2], "\n\nAppended content for testing.")
    d = json.loads(r)
    if assert_no_error(d, "append_to_page end"):
        check("append_to_page status=appended", d.get("status") == "appended")

    # 14. wikijs_append_to_page — prepend
    r = await wikijs_append_to_page(test_ids[2], "Prepended header.\n\n", position="start")
    d = json.loads(r)
    check("append_to_page start", assert_no_error(d, "append_to_page start"))

    # 15. wikijs_append_to_page — invalid position
    r = await wikijs_append_to_page(test_ids[0], "x", position="middle")
    d = json.loads(r)
    check("append_to_page bad position", "error" in d)

    # 16. wikijs_search_by_tag — exact
    r = await wikijs_search_by_tag("tech")
    d = json.loads(r)
    if assert_no_error(d, "search_by_tag exact"):
        check("search_by_tag exact finds results", d.get("total", 0) > 0, f"total={d.get('total')}")

    # 17. wikijs_search_by_tag — subtags
    r = await wikijs_search_by_tag("tech", include_subtags=True)
    d = json.loads(r)
    if assert_no_error(d, "search_by_tag subtags"):
        check("search_by_tag subtags >= exact", d.get("total", 0) >= 2, f"total={d.get('total')}")

    # 18. wikijs_search_by_tag — non-existent
    r = await wikijs_search_by_tag("nonexistent_tag_xyz")
    d = json.loads(r)
    if assert_no_error(d, "search_by_tag non-existent"):
        check("search_by_tag non-existent yields 0", d.get("total") == 0)

    # 19. wikijs_list_all_tags — flat
    r = await wikijs_list_all_tags()
    d = json.loads(r)
    if assert_no_error(d, "list_all_tags flat"):
        check("list_all_tags flat has tags", d.get("totalUniqueTags", 0) > 0)

    # 20. wikijs_list_all_tags — hierarchical
    r = await wikijs_list_all_tags(hierarchical=True)
    d = json.loads(r)
    if assert_no_error(d, "list_all_tags hierarchical"):
        check("list_all_tags tree has branches", len(d.get("tree", [])) > 0)

    # 21. wikijs_set_page_tags
    r = await wikijs_set_page_tags(test_ids[0], ["updated-tag"])
    d = json.loads(r)
    if assert_no_error(d, "set_page_tags"):
        check("set_page_tags applied", d.get("tags") == ["updated-tag"])
    # Restore
    await wikijs_set_page_tags(test_ids[0], ["tech", "tech/database"])

    # 22. wikijs_filter_pages
    r = await wikijs_filter_pages({"tag": "tech"})
    d = json.loads(r)
    if assert_no_error(d, "filter_pages tag"):
        check("filter_pages finds pages", d.get("total", 0) > 0, f"total={d.get('total')}")

    # 23. wikijs_filter_pages multi-facet
    r = await wikijs_filter_pages({"tag": "science", "isPublished": True})
    d = json.loads(r)
    check("filter_pages multi-facet", assert_no_error(d, "filter_pages multi"))

    # 24. wikijs_filter_pages empty filters
    r = await wikijs_filter_pages({})
    d = json.loads(r)
    check("filter_pages empty -> error", "error" in d)

    # 25. wikijs_smart_query — basic semantic search via Qdrant
    r = await wikijs_smart_query("database queries", limit=3, include_summaries=False, include_link_context=False)
    d = json.loads(r)
    if assert_no_error(d, "smart_query"):
        check("smart_query returns results", len(d.get("results", [])) > 0, f"mode={d.get('fallback_mode')}")
        check("smart_query fallback_mode", d.get("fallback_mode") in ("full", "keyword", "semantic"))

    # 26. wikijs_smart_query — semantic path (Qdrant populated)
    r = await wikijs_smart_query("vector embeddings semantic search", limit=3, include_summaries=False, include_link_context=False)
    d = json.loads(r)
    if assert_no_error(d, "smart_query semantic"):
        check("smart_query semantic has results", len(d.get("results", [])) > 0, f"count={len(d.get('results',[]))}")

    # 27. wikijs_smart_query — empty query
    r = await wikijs_smart_query("")
    d = json.loads(r)
    check("smart_query empty -> error", "error" in d)

    # 28. wikijs_smart_query summaries
    r = await wikijs_smart_query("api", limit=2, include_summaries=True, include_link_context=False)
    d = json.loads(r)
    if assert_no_error(d, "smart_query summaries"):
        has_snippet = any(r.get("snippet") for r in d.get("results", []))
        check("smart_query has snippets", has_snippet)

    # 29. wikijs_smart_query link context
    r = await wikijs_smart_query("test", limit=2, include_summaries=False, include_link_context=True)
    d = json.loads(r)
    if assert_no_error(d, "smart_query link context"):
        has_inbound = any("inbound_link_count" in r for r in d.get("results", []))
        check("smart_query has link context", has_inbound)

    # 30. wikijs_get_recent_changes
    r = await wikijs_get_recent_changes(since_days=365, limit=5)
    d = json.loads(r)
    if assert_no_error(d, "get_recent_changes"):
        check("get_recent_changes returns results", len(d.get("results", [])) > 0)

    # 31. wikijs_get_recent_changes since_date
    r = await wikijs_get_recent_changes(since_date="2024-01-01", limit=3)
    d = json.loads(r)
    check("get_recent_changes since_date", assert_no_error(d, "get_recent_changes date"))

    # 32. wikijs_get_recent_changes limit
    r = await wikijs_get_recent_changes(since_days=365, limit=2)
    d = json.loads(r)
    if assert_no_error(d, "get_recent_changes limit"):
        check("get_recent_changes limit respected", len(d.get("results", [])) <= 2)

    # 33. wikijs_wiki_stats
    r = await wikijs_wiki_stats()
    d = json.loads(r)
    if assert_no_error(d, "wiki_stats"):
        check("wiki_stats has total_pages", d.get("total_pages", 0) > 0)
        check("wiki_stats has most_linked", "most_linked" in d)

    # 34. wikijs_wiki_health — full
    r = await wikijs_wiki_health()
    d = json.loads(r)
    if assert_no_error(d, "wiki_health full"):
        check("wiki_health runs all checks", len(d.get("checks_run", [])) == 7)
        check("wiki_health has summary", "summary" in d)

    # 35. wikijs_wiki_health — scoped
    r = await wikijs_wiki_health(include_checks=["orphans", "untagged"])
    d = json.loads(r)
    if assert_no_error(d, "wiki_health scoped"):
        check("wiki_health scoped checks", d.get("checks_run") == ["orphans", "untagged"])

    # 36. wikijs_wiki_health — exclude pages
    r = await wikijs_wiki_health(include_checks=["orphans"], exclude_page_ids=test_ids)
    d = json.loads(r)
    check("wiki_health exclude", assert_no_error(d, "wiki_health exclude"))

    # 37. wikijs_get_affected_pages
    r = await wikijs_get_affected_pages(test_ids[0], max_results=10)
    d = json.loads(r)
    if assert_no_error(d, "get_affected_pages"):
        check("get_affected_pages mode=full", d.get("mode") == "full")
        check("get_affected_pages has signal_breakdown", "signal_breakdown" in d)

    # 38. wikijs_get_affected_pages non-existent
    r = await wikijs_get_affected_pages(99999, max_results=5)
    d = json.loads(r)
    check("get_affected_pages bad page", "error" in d)


async def test_import_export_tools():
    """Test 4 import/export tools."""
    print("\n--- Import/Export Tools (4) ---")

    import tempfile
    import os
    import shutil

    # Create a temporary directory for export
    export_dir = tempfile.mkdtemp(prefix="wikijs_test_export_")

    # Test 1: wikijs_export_page — export single page
    r = await wikijs_export_page(test_ids[0], os.path.join(export_dir, "test_export_single.md"), include_frontmatter=True)
    d = json.loads(r)
    if assert_no_error(d, "export_page"):
        check("export_page creates file", os.path.exists(d.get("file_path", "")), f"path={d.get('file_path')}")
        # Verify content
        with open(d["file_path"], 'r') as f:
            content = f.read()
        check("export_page has frontmatter", content.startswith("---"), "file starts with ---")
        check("export_page has title in frontmatter", "title:" in content)

    # Test 2: wikijs_export_page — without frontmatter
    r = await wikijs_export_page(test_ids[0], os.path.join(export_dir, "test_export_no_fm.md"), include_frontmatter=False)
    d = json.loads(r)
    if assert_no_error(d, "export_page no frontmatter"):
        with open(d["file_path"], 'r') as f:
            content = f.read()
        check("export_page no frontmatter omits ---", not content.startswith("---"), "file should not start with ---")

    # Test 3: wikijs_export_wiki — export all pages
    bulk_export_dir = os.path.join(export_dir, "bulk_export")
    r = await wikijs_export_wiki(bulk_export_dir, include_frontmatter=True)
    d = json.loads(r)
    if assert_no_error(d, "export_wiki"):
        check("export_wiki exported pages", d.get("exported_count", 0) > 0, f"count={d.get('exported_count')}")
        check("export_wiki output_dir matches", d.get("output_dir") == bulk_export_dir)

    # Test 4: wikijs_import_page — import with frontmatter
    import_path = os.path.join(export_dir, "test_import.md")
    fm_content = """---
title: Import Test Page
tags: [test-import, demo]
---

# Import Test Page

This page was imported from a markdown file.

It has **multiple** paragraphs and a list:

- Item 1
- Item 2

End of test content.
"""
    with open(import_path, 'w') as f:
        f.write(fm_content)

    r = await wikijs_import_page(import_path, update_existing=True)
    d = json.loads(r)
    if assert_no_error(d, "import_page with frontmatter"):
        check("import_page action is created or updated", d.get("action") in ("created", "updated"), f"action={d.get('action')}")
        imported_page_id = d.get("page_id")
        if imported_page_id:
            # Read back to verify content
            r2 = await wikijs_get_page(page_id=imported_page_id)
            d2 = json.loads(r2)
            if assert_no_error(d2, "import_page verify content"):
                check("import_page content preserved", "multiple paragraphs" in d2.get("content", ""))
            # Cleanup the imported page
            test_ids.append(imported_page_id)

    # Test 5: wikijs_import_page — import without frontmatter
    nofm_path = os.path.join(export_dir, "test_import_nofm.md")
    with open(nofm_path, 'w') as f:
        f.write("# No Frontmatter Page\n\nThis file has no YAML frontmatter.")

    r = await wikijs_import_page(nofm_path, update_existing=True)
    d = json.loads(r)
    if assert_no_error(d, "import_page no frontmatter"):
        check("import_page nofm succeeded", d.get("action") in ("created", "updated"))
        nofm_page_id = d.get("page_id")
        if nofm_page_id:
            test_ids.append(nofm_page_id)

    # Test 6: wikijs_import_directory — import directory structure
    import_dir = os.path.join(export_dir, "import_tree")
    os.makedirs(os.path.join(import_dir, "subdir"), exist_ok=True)

    with open(os.path.join(import_dir, "root_page.md"), 'w') as f:
        f.write("""---
title: Root Page
tags: [import-test]
---

# Root Page

This is a root-level page.
""")

    with open(os.path.join(import_dir, "subdir", "child_page.md"), 'w') as f:
        f.write("""---
title: Child Page
tags: [import-test]
---

# Child Page

This is a child page in a subdirectory.
""")

    r = await wikijs_import_directory(import_dir, base_parent_path=f"import-test-{int(time.time())}", update_existing=True)
    d = json.loads(r)
    if assert_no_error(d, "import_directory"):
        check("import_directory imported pages", d.get("imported", 0) > 0, f"imported={d.get('imported')}")
        check("import_directory no errors", len(d.get("errors", [])) == 0, f"errors={d.get('errors')}")

    # Test 7: wikijs_export_wiki — roundtrip check
    roundtrip_dir = os.path.join(export_dir, "roundtrip")
    r = await wikijs_export_wiki(roundtrip_dir, include_frontmatter=True)
    d = json.loads(r)
    check("roundtrip export succeeds", assert_no_error(d, "roundtrip export"))

    # Cleanup temp directory
    shutil.rmtree(export_dir, ignore_errors=True)


async def test_graph_tools():
    """Test 3 graph tools."""
    print("\n--- Graph Tools (3) ---")

    pid = test_ids[1]  # Test Beta has links

    # 39. wikijs_extract_page_links
    r = await wikijs_extract_page_links(pid)
    d = json.loads(r)
    if assert_no_error(d, "extract_page_links"):
        check("extract_page_links has internalLinks", "internalLinks" in d)
        check("extract_page_links has externalLinks", "externalLinks" in d)

    # 40. wikijs_extract_page_links — internal only
    r = await wikijs_extract_page_links(pid, link_type="internal")
    d = json.loads(r)
    if assert_no_error(d, "extract_page_links internal"):
        check("extract_page_links internal only", d.get("totalExternal", 0) == 0)

    # 41. wikijs_extract_page_links — invalid type
    r = await wikijs_extract_page_links(pid, link_type="invalid")
    d = json.loads(r)
    check("extract_page_links bad type -> error", "error" in d)

    # 42. wikijs_get_page_graph
    r = await wikijs_get_page_graph(pid, depth=1, direction="both")
    d = json.loads(r)
    if assert_no_error(d, "get_page_graph"):
        check("get_page_graph has nodes", "nodes" in d)
        check("get_page_graph has stats", "stats" in d)

    # 43. wikijs_get_page_graph — outgoing
    r = await wikijs_get_page_graph(pid, depth=1, direction="outgoing")
    d = json.loads(r)
    check("get_page_graph outgoing", assert_no_error(d, "get_page_graph outgoing"))

    # 44. wikijs_get_page_graph — max_nodes cap
    r = await wikijs_get_page_graph(pid, depth=2, max_nodes=3)
    d = json.loads(r)
    if assert_no_error(d, "get_page_graph max_nodes"):
        check("get_page_graph respects cap", len(d.get("nodes", [])) <= 3 or d.get("stats", {}).get("truncated"))

    # 45. wikijs_find_shortest_path
    r = await wikijs_find_shortest_path(test_ids[0], test_ids[1])
    d = json.loads(r)
    if assert_no_error(d, "find_shortest_path"):
        check("find_shortest_path returns result", d.get("pathFound") in (True, False))

    # 46. wikijs_find_shortest_path — disconnected
    r = await wikijs_find_shortest_path(test_ids[0], test_ids[2])
    d = json.loads(r)
    if assert_no_error(d, "find_shortest_path disconnected"):
        check("find_shortest_path not found", d.get("pathFound") == False)

    # 47. wikijs_find_shortest_path — same page
    r = await wikijs_find_shortest_path(test_ids[0], test_ids[0])
    d = json.loads(r)
    check("find_shortest_path same -> error", "error" in d)


async def test_hierarchy_tools():
    """Test 4 hierarchy tools."""
    print("\n--- Hierarchy Tools (4) ---")

    # 48. wikijs_create_repo_structure
    ts = int(time.time())
    repo_name = f"TestRepo{ts}"
    r = await wikijs_create_repo_structure(repo_name, "Test repo description", ["docs", "api"])
    d = json.loads(r)
    check("create_repo_structure", assert_no_error(d, "create_repo_structure"))

    # 49. wikijs_create_nested_page
    slug = repo_name.lower().replace(" ", "-")
    r = await wikijs_create_nested_page("Nested Child", "Child content", f"{slug}/docs", create_parent_if_missing=False)
    d = json.loads(r)
    check("create_nested_page", assert_no_error(d, "create_nested_page"))

    # 50. wikijs_get_page_children — from path
    r = await wikijs_get_page_children(page_path=slug)
    d = json.loads(r)
    check("get_page_children", assert_no_error(d, "get_page_children"))

    # 51. wikijs_create_documentation_hierarchy
    r = await wikijs_create_documentation_hierarchy(f"TestProject{ts}", [{"file_path": "/tmp/test.py", "page_id": test_ids[0]}], auto_organize=False)
    d = json.loads(r)
    check("create_documentation_hierarchy", assert_no_error(d, "create_doc_hierarchy"))


async def test_file_tools():
    """Test 4 file integration tools."""
    print("\n--- File Integration Tools (4) ---")

    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("# Test file\n\ndef hello():\n    return 'world'\n")
        tmp_path = f.name

    # 52. wikijs_link_file_to_page
    r = await wikijs_link_file_to_page(tmp_path, test_ids[0], "test")
    d = json.loads(r)
    check("link_file_to_page", assert_no_error(d, "link_file_to_page"))

    # 53. wikijs_sync_file_docs
    r = await wikijs_sync_file_docs(tmp_path, "Test change summary", "# Test snippet")
    d = json.loads(r)
    check("sync_file_docs", assert_no_error(d, "sync_file_docs"))

    # 54. wikijs_generate_file_overview
    r = await wikijs_generate_file_overview(tmp_path, include_functions=True)
    d = json.loads(r)
    check("generate_file_overview", assert_no_error(d, "generate_file_overview"))

    # 55. wikijs_bulk_update_project_docs
    r = await wikijs_bulk_update_project_docs("Bulk update summary", [tmp_path], "Test context")
    d = json.loads(r)
    check("bulk_update_project_docs", assert_no_error(d, "bulk_update_project_docs"))

    os.unlink(tmp_path)


async def test_deletion_tools():
    """Test 4 deletion tools (on temporary test pages)."""
    print("\n--- Deletion Tools (4) ---")

    # Create temp pages for deletion tests
    r = await wikijs_create_page("TempDelete1", "Temp content 1")
    d1 = json.loads(r)
    r = await wikijs_create_page("TempDelete2", "Temp content 2")
    d2 = json.loads(r)
    r = await wikijs_create_page("TempDelete3", "Temp content 3")
    d3 = json.loads(r)
    del_ids = [d1.get("pageId"), d2.get("pageId"), d3.get("pageId")]

    # Create a hierarchy for delete hierarchy test
    await wikijs_create_repo_structure(f"DeleteRepo{int(time.time())}", "Delete test", ["docs"])

    # 56. wikijs_delete_page
    r = await wikijs_delete_page(page_id=del_ids[0], remove_file_mapping=False)
    d = json.loads(r)
    check("delete_page", assert_no_error(d, "delete_page"))

    # 57. wikijs_batch_delete_pages
    r = await wikijs_batch_delete_pages(page_ids=del_ids[1:], confirm_deletion=True, remove_file_mappings=False)
    d = json.loads(r)
    check("batch_delete_pages", assert_no_error(d, "batch_delete_pages"))

    # 58. wikijs_delete_hierarchy
    r = await wikijs_delete_hierarchy(f"deleterepo{int(time.time())}", "children_only", confirm_deletion=True, remove_file_mappings=False)
    d = json.loads(r)
    check("delete_hierarchy", assert_no_error(d, "delete_hierarchy"))

    # 59. wikijs_cleanup_orphaned_mappings
    r = await wikijs_cleanup_orphaned_mappings()
    d = json.loads(r)
    check("cleanup_orphaned_mappings", assert_no_error(d, "cleanup_orphaned_mappings"))


async def test_system_tools():
    """Test 3 system tools."""
    print("\n--- System Tools (3) ---")

    # 60. wikijs_connection_status
    r = await wikijs_connection_status()
    d = json.loads(r)
    if assert_no_error(d, "connection_status"):
        check("connection_status connected", d.get("connected") == True)

    # 61. wikijs_repository_context
    r = await wikijs_repository_context()
    d = json.loads(r)
    check("repository_context", assert_no_error(d, "repository_context"))

    # 62. wikijs_manage_collections
    r = await wikijs_manage_collections("test-collection", "Test collection")
    d = json.loads(r)
    check("manage_collections", assert_no_error(d, "manage_collections"))


async def main():
    global start_time
    start_time = time.time()

    print("=" * 60)
    print("Wiki.js MCP — Comprehensive Test Suite")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    await wikijs.authenticate()

    # Check connection first
    r = await wikijs_connection_status()
    d = json.loads(r)
    if not d.get("connected"):
        print("\nFAIL: Cannot connect to Wiki.js. Is the stack running?")
        print(f"  {d}")
        sys.exit(1)
    print(f"\nConnected: authenticated={d.get('authenticated')}")

    # Setup
    initial_count = await setup_test_data()

    # Run tests
    await test_page_tools(initial_count)
    await test_import_export_tools()
    await test_graph_tools()
    await test_hierarchy_tools()
    await test_file_tools()
    await test_deletion_tools()
    await test_system_tools()

    # Cleanup
    await cleanup_test_data()

    # Report
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"Test Suite Complete in {elapsed:.1f}s")
    print(f"Total: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    if failed == 0:
        print(f"Result: ALL TESTS PASSED")
    else:
        print(f"Result: {failed} FAILURES")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
