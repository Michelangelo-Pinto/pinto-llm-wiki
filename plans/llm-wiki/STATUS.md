# Status — LLM Wiki Features (Scale-First)

Last updated: 2026-05-23 (ALL features completed)

## Legend

| Status | Meaning |
|--------|---------|
| `pending` | Not started |
| `in-research` | Investigating design options |
| `planned` | Full plan created, ready to implement |
| `in-progress` | Implementation underway |
| `completed` | Built, tested, and verified |
| `blocked` | Blocked by dependency or unresolved question |
| `merged` | Subsumed into another feature |

## Feature tracker

| Priority | Feature | Subplan | Status | Notes |
|----------|---------|---------|--------|-------|
| — | Plan system | `README.md` | `completed` | Scale-first redesign completed 2026-05-21 |
| P1 | `wikijs_bulk_get_pages` | `subplans/01-bulk-page-read.md` | `completed` | Tested: 6/6 pass. Rebuilt Docker image. Verified via browser. Ready for backlinks (P1). |
| P1 | `wikijs_get_backlinks` | `subplans/02-backlinks.md` | `completed` | 7/7 pass. Auth race fixed. SQLite BacklinkIndex, hooks + rebuild. |
| P1 | `wikijs_get_page_stats` | `subplans/03-page-stats.md` | `completed` | 6/6 pass. wordCount, link counts. Powered by BacklinkIndex. No caching needed. |
| P2 | `wikijs_append_to_page` | `subplans/04-page-append.md` | `completed` | Append content without rewriting full page |
| P2 | Tag management (hierarchical) | `subplans/05-tag-management.md` | `completed` | 4 tools: search_by_tag, list_all_tags, set_page_tags, filter_pages. Client-side filtering via pages.list — no SQLite cache needed at 200+ pages. Hierarchy via "/" convention with prefix matching. 12/12 tests passed. |
| P2 | `wikijs_smart_query` | `subplans/06-smart-query.md` | `completed` | Hybrid search (semantic + keyword) via RRF. Uses vector engine (P4-11) for semantic component. Falls back gracefully. |
| P2 | Link graph tools | `subplans/07-link-graph.md` | `completed` | 3 tools: extract_page_links, get_page_graph, find_shortest_path. BFS traversal via BacklinkIndex. New module: tools_graph.py. |
| P3 | `wikijs_wiki_health` | `subplans/08-wiki-health.md` | `completed` | Unified health dashboard: 7 checks (orphans, stale, density, untagged, connected, clusters, contradictions). BFS for disconnected clusters. |
| P3 | `wikijs_get_recent_changes` | `subplans/09-recent-changes.md` | `completed` | Pages modified in last N days. Client-side date filtering from pages.list updatedAt. |
| P4 | `wikijs_get_affected_pages` | `subplans/10-affected-pages.md` | `completed` | Proactive impact analysis: 4 signals (backlink, semantic, tags, graph), weighted ranking, dedup. mode: "full". |
| P4 | Vector search engine | `subplans/11-vector-search.md` | `completed` | Embedded engine: sentence-transformers/all-MiniLM-L6-v2 + brute force cosine similarity in Python. No sqlite-vec. |
| P4 | `wikijs_wiki_stats` | `subplans/12-wiki-stats.md` | `completed` | Aggregate wiki dashboard. 60s cache. No content reading. |

## Merged features (no longer standalone)

| Old priority | Old feature | Old subplan | Merged into | Notes |
|---|---|---|---|---|
| P3 | `wikijs_find_orphan_pages` | `subplans/06-orphan-detection.md` | `subplans/08-wiki-health.md` (P3) | Orphan check is now one component of the unified health dashboard |
| P4 | `wikijs_find_stale_pages` | `subplans/10-stale-detection.md` | `subplans/08-wiki-health.md` (P3) | Stale check is now one component of the unified health dashboard |
| P4 | `wikijs_semantic_search` | `subplans/09-semantic-search.md` | `subplans/11-vector-search.md` (P4) | Redesigned from external tool to embedded engine |

## Dependency graph

```
P1: bulk_get_pages  ←  no dependencies
P1: backlinks      ←  may depend on bulk_get_pages for scanning all pages
P1: page_stats     ←  may depend on backlinks (for inbound link count)
P2: append_to_page ←  no dependencies
P2: tag_mgmt       ←  no dependencies
P2: smart_query    ←  depends on backlinks (P1), bulk_get_pages (P1), vector_search (P4-11)
P2: link_graph     ←  depends on backlinks (P1)
P3: wiki_health    ←  depends on backlinks (P1), page_stats (P1)
P3: recent_changes ←  no hard dependencies
P4: affected_pages ←  depends on backlinks (P1), tag_mgmt (P2), link_graph (P2), vector_search (P4-11)
P4: vector_search  ←  no hard dependencies (new library)
P4: wiki_stats     ←  depends on backlinks (P1), page_stats (P1)
```

## Change log

| Date | Change |
|------|--------|
| 2026-05-21 | Scale-first redesign: promoted page_stats to P1, link_graph to P2. Added smart_query, wiki_health, affected_pages, vector_search, wiki_stats. Merged orphans + stale into wiki_health. Redesigned semantic_search as embedded vector engine. |
| 2026-05-21 | bulk_get_pages: full plan created, implemented, tested (6/6), Docker rebuilt, browser-verified. Status -> `completed`. |
| 2026-05-21 | backlinks: BacklinkIndex model, link extraction, hooks in create/update/delete, wikijs_get_backlinks + wikijs_rebuild_backlink_index. Auth race fixed (asyncio.Lock). Tested 7/7. Status -> `completed`. |
| 2026-05-22 | page_stats: wikijs_get_page_stats + wikijs_bulk_get_page_stats. Two-phase batch (bulk_get_pages + BacklinkIndex batch query). Tested 6/6. Status -> `completed`. |
| 2026-05-22 | AGENTS.md, STATUS.md, MCP_TOOL_CATALOG.md, DATABASE_LAYER.md synced with current state (26 tools, 3 P1 completed). |
| 2026-05-22 | Tag management: 4 tools (search_by_tag, list_all_tags, set_page_tags, filter_pages). Client-side filtering from pages.list. No SQLite cache — single GraphQL call sufficient at 200+ pages. Hierarchy via "/" prefix matching. Tested 12/12. Docker rebuilt. Tools: 27 -> 31. |
| 2026-05-23 | Vector engine (P4-11): sentence-transformers/all-MiniLM-L6-v2, brute force cosine similarity (no sqlite-vec). PageVector SQLite table. wikijs_vector_search + wikijs_rebuild_vector_index. Hooks on create/update/delete. Tested 6/6. |
| 2026-05-23 | Smart query (P2-06): hybrid search via RRF (semantic + keyword). fallback_mode support. Summaries and link context. Tested 6/6. |
| 2026-05-23 | Link graph (P2-07): wikijs_extract_page_links, wikijs_get_page_graph (BFS), wikijs_find_shortest_path (bidirectional BFS). New module tools_graph.py. Based on BacklinkIndex. Tested 8/8. Tools: 31 → 37. |
| 2026-05-23 | P3+P4 remaining: recent_changes (P3), wiki_stats (P4), wiki_health (P3), affected_pages (P4). All 12 roadmap features COMPLETED. 37 → 41 tools. 14/14 tests passed. |
