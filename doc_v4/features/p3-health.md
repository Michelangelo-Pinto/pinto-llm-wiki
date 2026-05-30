# P3 — Health & Maintenance

P3 features support the LLM Wiki "lint" operation and ongoing wiki health monitoring via a unified dashboard approach.

---

## `wikijs_wiki_health`

**Priority**: P3 | **File**: [`tools_pages.py` line 2042](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Unified health dashboard: 7 checks in a single tool call. Merges orphan and stale detection into one operation.

### Why

At scale, running separate lint tools is wasteful — each call fetches all pages and computes overlapping data. A single unified health check avoids redundant work and gives the agent a complete picture in one call.

### Signature

```python
wikijs_wiki_health(
    include_checks: List[str] = None,
    exclude_page_ids: List[int] = None,
    exclude_paths: List[str] = None,
) -> str
```

### Return

```json
{
  "checks_run": ["orphans", "stale", "link_density", "untagged", "most_connected", "disconnected_clusters", "contradictions"],
  "orphans": [{"pageId": 45, "title": "...", "path": "...", "lastModified": "..."}],
  "stale": [{"pageId": 23, "title": "...", "path": "...", "daysStale": 180}],
  "link_density": {"average_links_per_page": 4.2, "distribution": {"zero_links": 5, "one_to_three": 45, "four_to_ten": 120, "eleven_plus": 30}},
  "untagged_pages": [{"pageId": 89, "title": "...", "path": "..."}],
  "most_connected": [{"pageId": 7, "title": "...", "inboundLinks": 34, "outboundLinks": 22}],
  "disconnected_clusters": [{"clusterId": 1, "pages": [...], "size": 2}],
  "contradictions": [],
  "summary": {"total_checks": 7, "issues_found": 23, "critical": 2, "warnings": 21}
}
```

### Checks

| Check | What it finds | Source |
|-------|--------------|--------|
| `orphans` | Pages with zero inbound links | BacklinkIndex |
| `stale` | Pages not updated in 90+ days | pages.list updatedAt |
| `link_density` | Distribution of outbound links per page | BacklinkIndex |
| `untagged` | Pages with empty tags array | pages.list tags |
| `most_connected` | Top 10 pages by inbound links | BacklinkIndex GROUP BY |
| `disconnected_clusters` | Connected components isolated from main graph | BFS on BacklinkIndex |
| `contradictions` | Placeholder — requires LLM | Not implemented |

### Disconnected clusters

BFS traversal on the full link graph (bidirectional adjacency from BacklinkIndex). Finds connected components. Clusters smaller than the largest component are reported as potentially disconnected.

### Exclusions

- `exclude_page_ids`: Skip specific pages (e.g. index, log)
- `exclude_paths`: Skip path prefixes (e.g. structural pages)

### Dependencies

- `BacklinkIndex` (P1) — for orphans, density, most_connected, clusters
- `_LIST_ALL_PAGES_WITH_TAGS_QUERY` — for metadata (tags, updatedAt)

---

## `wikijs_get_recent_changes`

**Priority**: P3 | **File**: [`tools_pages.py` line 1772](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Pages modified within a given time window, sorted by most recent.

### Why

For incremental maintenance, the agent needs to know what changed recently. Enables: ingest review, lint focus on recently-modified pages, log.md verification.

### Signature

```python
wikijs_get_recent_changes(limit: int = 20, since_days: int = None, since_date: str = None) -> str
```

### Design

- **Client-side filtering**: Wiki.js GraphQL has no native date filter. Fetches `pages.list` with `updatedAt`, filters in Python.
- `since_date` overrides `since_days` when both provided
- ISO 8601 date parsing with UTC timezone handling
- Results sorted by `updatedAt` descending, capped at `limit`

### Return

```json
{
  "results": [{"pageId": 7, "title": "...", "path": "...", "updatedAt": "2026-05-22T...", "description": "..."}],
  "total": 5,
  "since_days": 7,
  "since_date": null
}
```

### Dependencies

None. Uses `_LIST_ALL_PAGES_WITH_TAGS_QUERY` for `updatedAt` field.
