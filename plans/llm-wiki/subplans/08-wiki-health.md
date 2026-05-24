# wikijs_wiki_health

---

- **Status**: `completed`
- **Priority**: P3

## Why

The LLM Wiki lint operation explicitly checks for multiple health issues:

> Look for: orphan pages with no inbound links, stale claims that newer sources have superseded, contradictions between pages, pages that reference concepts without a dedicated page, missing cross-references.

The original roadmap had three separate tools for this (orphan detection, stale detection, recent changes). At scale, running them separately is wasteful — each call fetches all pages and computes overlapping data. A single unified health check avoids redundant work and gives the agent a complete picture in one call.

This tool **merges** the old `find_orphan_pages` (P3-06) and `find_stale_pages` (P4-10) subplans and adds new checks (link density, contradictions, disconnected clusters, untagged pages).

## What

```python
wikijs_wiki_health(include_checks: List[str] = None) -> str
```

- `include_checks`: optional list of specific checks to run. If None, runs all checks. Valid values: `"orphans"`, `"stale"`, `"link_density"`, `"untagged"`, `"most_connected"`, `"contradictions"`, `"disconnected_clusters"`.

Returns:
```json
{
  "checks_run": ["orphans", "stale", "link_density", "untagged", "most_connected"],
  "orphans": [
    {"pageId": 45, "title": "Old Auth Method", "path": "auth/legacy", "lastModified": "2025-01-01", "outboundLinkCount": 3}
  ],
  "stale": [
    {"pageId": 23, "title": "API v1 Docs", "path": "api/v1", "daysStale": 180, "lastModified": "2025-11-20"}
  ],
  "link_density": {
    "average_links_per_page": 4.2,
    "distribution": {
      "zero_links": 5,
      "one_to_three": 45,
      "four_to_ten": 120,
      "eleven_plus": 30
    }
  },
  "untagged_pages": [
    {"pageId": 89, "title": "Random Notes", "path": "notes", "lastModified": "2026-04-01"}
  ],
  "most_connected": [
    {"pageId": 7, "title": "Authentication", "inboundLinks": 34, "outboundLinks": 22}
  ],
  "disconnected_clusters": [
    {"clusterId": 1, "pages": [{"pageId": 45, "title": "Old Auth"}, {"pageId": 46, "title": "Old DB"}], "size": 2, "bridgeableTo": true}
  ],
  "summary": {
    "total_checks": 5,
    "issues_found": 23,
    "critical": 2,
    "warnings": 21
  }
}
```

### Health checks explained

| Check | What it finds | Severity |
|-------|--------------|----------|
| `orphans` | Pages with zero inbound links | Warning (except structural pages) |
| `stale` | Pages not updated in N days (configurable, default 90) | Warning |
| `link_density` | Distribution of links per page. Pages with zero outbound links are critical | Varies |
| `untagged` | Pages with no tags | Warning |
| `most_connected` | Top 10 pages by inbound links (hub pages) | Info |
| `contradictions` | Placeholder for future NLP-based contradiction detection | Info (requires LLM) |
| `disconnected_clusters` | Groups of pages that only link to each other, not to the rest of the wiki | Critical if unbridgeable |

## Design questions

- **What counts as orphan?** A page with zero inbound links. Exclude structural pages (index, log, pages with path depth 0) by default. Configurable exclude list.
- **Stale threshold**: default 90 days, configurable via `wikipedia_stale_threshold_days` env var or a config page.
- **Disconnected clusters**: a connected component in the link graph that has no edges to the rest of the wiki. Important at scale when sub-sections might become isolated.
- **Contradictions**: this is the hardest check. Start as a placeholder. Future: compare pages with high TF-IDF similarity but opposing claims. Requires LLM — too expensive to run on every health check. Maybe a lightweight pre-filter (shared topic + conflicting keywords) then flag for agent review.
- **Excluding specific pages**: allow `exclude_paths` parameter (list of path prefixes) and `exclude_page_ids`.
- **Caching**: health check results for a given point in time could be cached for 5 minutes. Invalidated on any page create/update/delete.

## Dependencies

- `wikijs_get_backlinks` (P1) — for orphan detection, link density, connected components
- `wikijs_get_page_stats` (P1) — for per-page metadata
- `wikijs_get_recent_changes` (P3) — for staleness calculation (or compute directly from updatedAt)
- Feeds from: link graph (P2) for disconnected clusters

## Scale considerations

- Running all 7 checks on 200 pages requires scanning every page. With a SQLite backlink index and stats cache, this is a single SQL query per check, not O(N^2).
- Disconnected clusters: Tarjan's algorithm or BFS on the link graph. O(V+E). At 200 nodes with average degree 5, this is ~1000 edges — trivial.
- Stale check: simple date comparison on cached stats. No content reading.
- Report compression: health results for 200 pages could be large. Use `include_checks` to scope down. Return summaries with counts, not full arrays when not needed.

## Implementation plan

1. Implement orphan check (query backlink index for pages with inbound count = 0)
2. Implement stale check (query page stats for updatedAt, compare to threshold)
3. Implement link density distribution (aggregate from page stats)
4. Implement untagged pages check (filter pages with empty tags array)
5. Implement most-connected pages (rank by inbound link count from backlink index)
6. Implement disconnected clusters (BFS/connected components on link graph)
7. Implement placeholder contradiction check (TF-IDF similarity pre-filter)
8. Design `include_checks` scoping logic
9. Add tool to `tools_pages.py` or new `tools_health.py`
10. Update documentation
11. Verify by creating pages with known issues (orphans, stale, etc.)

## Acceptance criteria

- Running all checks returns a complete health dashboard
- `include_checks` correctly scopes which checks run
- Orphan detection excludes structural pages by default
- Stale detection respects configurable threshold
- Works correctly on a healthy wiki (all checks return no issues, not errors)
- At 200+ pages, full health check completes in < 5 seconds
- Each check result includes actionable data (page IDs, titles, paths)
- Summary provides accurate issue counts at a glance

---

## Implementation notes (2026-05-23)

- All 7 checks implemented (contradictions = placeholder, needs LLM)
- BFS for disconnected clusters on BacklinkIndex (O(V+E))
- `include_checks` scoping: specific checks or all 7
- `exclude_page_ids` and `exclude_paths` for structural pages
- No separate module — added to tools_pages.py
- Tested 14/14 across all P3+P4 tools
