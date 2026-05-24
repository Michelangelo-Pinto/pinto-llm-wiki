# Link graph tools

---

- **Status**: `completed`
- **Priority**: P2 (promoted from P3 in scale-first redesign)

## Why

The LLM Wiki pattern is built around interlinked pages. The agent needs graph awareness for:

- **Navigation**: understanding the local neighborhood around any page
- **Ingestion**: finding all pages connected to a topic (transitive backlinks)
- **Lint**: detecting disconnected clusters, finding paths between related concepts
- **Query**: exploring the wiki graph to discover related content

At scale (200+ pages), reading every page to understand the graph is impossible. Dedicated graph tools with a pre-built link index are essential. This was promoted from P3 to P2 because graph awareness is a core LLM Wiki capability, not a maintenance nice-to-have.

This includes link extraction (what a page links to), local graph exploration (neighbors at N hops), and shortest-path finding (how two concepts are connected).

## What

### 1. `wikijs_extract_page_links`

```python
wikijs_extract_page_links(page_id: int, link_type: str = "all") -> str
```

- `link_type`: `"all"`, `"internal"` (wiki links only), or `"external"` (HTTP links only)

Returns:
```json
{
  "pageId": 7,
  "title": "Authentication",
  "internalLinks": [{"targetPath": "auth/oauth", "targetTitle": "OAuth", "linkText": "OAuth flow", "section": "## Security", "targetPageId": 12}],
  "externalLinks": [{"url": "https://example.com", "linkText": "documentation"}],
  "totalInternal": 12,
  "totalExternal": 3
}
```

### 2. `wikijs_get_page_graph`

```python
wikijs_get_page_graph(page_id: int, depth: int = 1, direction: str = "both", max_nodes: int = 50) -> str
```

- `depth`: how many hops from the root page (default 1, max 2)
- `direction`: `"outgoing"` (pages this page links to), `"incoming"` (pages that link to this page), `"both"`
- `max_nodes`: safety cap to prevent explosion at depth > 1

Returns a graph structure:
```json
{
  "root": {"pageId": 7, "title": "Authentication"},
  "nodes": [{"pageId": 8, "title": "OAuth", "path": "auth/oauth", "direction": "outgoing", "depth": 1}],
  "edges": [{"source": 7, "target": 8, "linkText": "OAuth flow"}],
  "stats": {"totalNodes": 15, "density": 0.3, "maxDepth": 2}
}
```

### 3. `wikijs_find_shortest_path` (NEW — scale addition)

```python
wikijs_find_shortest_path(from_page_id: int, to_page_id: int, max_depth: int = 5) -> str
```

Finds the shortest path between two pages through the link graph. Useful for understanding how two concepts are connected.

Returns:
```json
{
  "pathFound": true,
  "length": 3,
  "path": [
    {"pageId": 1, "title": "Index", "step": 0},
    {"pageId": 7, "title": "Authentication", "step": 1},
    {"pageId": 12, "title": "OAuth 2.0", "step": 2},
    {"pageId": 15, "title": "Bearer Tokens", "step": 3}
  ]
}
```

## Design questions

- **How to detect wiki links in markdown content?**
  - Standard markdown: `[text](path)` patterns
  - Wiki.js internal link format: check if Wiki.js has a special link syntax
  - Regex-based extraction from page content
- **How to resolve link targets to page IDs?**
  - Parse the link path, look up by path → page ID via GraphQL `singleByPath`
  - With a backlink index (P1), the mapping already exists — use that
  - Cache path→ID mappings in SQLite `LinkTargetCache` table
- **For `get_page_graph`**: BFS traversal using the backlink index. Track visited page IDs to handle cycles. Stop at `max_nodes` or `depth` limit.
- **For `find_shortest_path`**: Bidirectional BFS from both source and target. Uses the backlink index for "what links to X" and the outbound link index for "what does X link to".
- **Performance at depth > 1**: graph can explode. `max_nodes=50` default cap. Warn in response if truncated.
- **Broken links**: links to non-existent pages should be flagged with `broken: true`.

## Dependencies

- `wikijs_get_backlinks` (P1) — required for `incoming` direction and `find_shortest_path`
- `wikijs_extract_page_links` is also the link extraction logic used by `wikijs_get_backlinks` (P1) for index building
- Feeds into: `smart_query` (P2), `wiki_health` (P3), `affected_pages` (P4)

## Scale considerations

- Link extraction at scale: cache extracted links per page in SQLite. Re-extract only when page content changes.
- Path finding on 200+ nodes: BFS is O(V+E). With bidirectional BFS, complexity is O(b^(d/2)) instead of O(b^d). At depth 5 with average degree 5, that's 5^3 = 125 nodes explored vs 5^5 = 3125.
- Graph traversal capping: `max_nodes` prevents runaway queries. Default 50 is generous for immediate neighborhood.
- Link index building: the initial link index for 200 pages can be built once (via `rebuild_backlink_index`) and maintained incrementally.

## Implementation plan

1. Implement link extraction from markdown content (regex-based)
2. Design and implement SQLite `LinkTargetCache` for path→ID mapping
3. Implement path-to-page-ID resolution (optimized with caching)
4. Implement `wikijs_extract_page_links`
5. Implement `wikijs_get_page_graph` with BFS, cycle detection, depth limits
6. Implement `wikijs_find_shortest_path` with bidirectional BFS
7. Add tools to a new `tools_graph.py` module
8. Update documentation
9. Verify by creating pages with intentional cross-references and exploring the graph

## Acceptance criteria

- `extract_page_links` correctly identifies all `[text](path)` links in a page
- `extract_page_links` separates internal wiki links from external HTTP links
- `get_page_graph` at depth=1 returns the root page's immediate neighbors (both directions)
- `get_page_graph` handles cycles without infinite loops
- `get_page_graph` respects `max_nodes` cap and reports truncation
- `find_shortest_path` finds correct path between connected pages
- `find_shortest_path` returns `pathFound: false` for disconnected pages
- Broken links (pointing to non-existent pages) are flagged with `broken: true`
- All tools fail gracefully on pages with no links
- At 200+ pages, `get_page_graph(depth=2)` completes in < 2 seconds

---

## Implementation notes (2026-05-23)

### Design decisions

| Aspect | Planned | Implemented | Why |
|--------|---------|-------------|-----|
| Module | New `tools_graph.py` | same | Separate from page tools for conceptual clarity |
| Data source | BacklinkIndex | same | Single SQLite table, bidirectional via source_page_id/target_page_id |
| BFS | Standard BFS | BFS with visited set | Simple, correct, handles cycles |
| Shortest path | Bidirectional BFS | same | O(b^(d/2)) vs O(b^d), critical for depth > 3 |
| External links | Separate regex | `_extract_external_links` | Regex for `[text](https?://...)` in markdown |
| Title resolution | Bulk resolve | `_batch_resolve_titles` via wikijs_bulk_get_pages | Avoids N+1 GraphQL calls |

### Key deviations from original plan

- **No new SQLite tables**: The original plan suggested `LinkTargetCache` for path→ID mapping. Not implemented — `_resolve_paths_to_ids` (from tools_pages) handles path resolution efficiently via parallel GraphQL.
- **No section tracking**: `_extract_links` doesn't track markdown section context (e.g., "## Security"). The subplan's `section` field in results is not implemented.
- **max_depth capped at 2**: The subplan mentions support up to depth 2 for `get_page_graph`. Implemented as hard cap (depth 1 or 2) to prevent graph explosion.
- **Title resolution**: Uses `_batch_resolve_titles` (bulk_get_pages) instead of individual GraphQL calls.

### Test results

8/8 tests passed inside Docker container:
- extract_page_links separates internal/external
- link_type filter works (internal/external/all)
- get_page_graph with outgoing, incoming, both directions
- max_nodes cap enforced with truncation flag
- find_shortest_path bidirectional BFS works
- Disconnected pages return pathFound: false
- Broken links flagged
