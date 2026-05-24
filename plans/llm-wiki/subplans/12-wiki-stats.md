# wikijs_wiki_stats

---

- **Status**: `completed`
- **Priority**: P4

## Why

At scale (200+ pages), the agent needs a quick "at a glance" overview of the entire wiki. This informs high-level decisions:

- **Before ingestion**: "How big is the wiki now? What's the link density? Any obvious problems?"
- **After bulk operations**: "What changed? Did growth rate spike? Did orphan count drop?"
- **Monitoring**: "Is the wiki growing healthily or accumulating issues?"

This is a lightweight aggregation tool — it does NOT run health checks (that's `wiki_health`, P3). It provides aggregate numbers and distributions that the agent can use to decide whether to run a full health check.

## What

```python
wikijs_wiki_stats() -> str
```

Returns:
```json
{
  "total_pages": 234,
  "total_links": 1204,
  "internal_links": 1100,
  "external_links": 104,
  "avg_links_per_page": 5.1,
  "orphan_count": 12,
  "orphan_rate": 0.051,
  "stale_count": 45,
  "avg_staleness_days": 23,
  "total_tags": 87,
  "unique_tags": 52,
  "pages_without_tags": 8,
  "growth_last_30d": 18,
  "growth_last_7d": 4,
  "most_linked": [
    {"pageId": 7, "title": "Authentication", "inbound_links": 34},
    {"pageId": 1, "title": "Index", "inbound_links": 28},
    {"pageId": 15, "title": "Bearer Tokens", "inbound_links": 22}
  ],
  "most_linking": [
    {"pageId": 1, "title": "Index", "outbound_links": 45},
    {"pageId": 7, "title": "Authentication", "outbound_links": 22}
  ],
  "newest_page": {"pageId": 234, "title": "OIDC Discovery", "createdAt": "2026-05-20", "path": "auth/oidc"},
  "oldest_page": {"pageId": 1, "title": "Index", "createdAt": "2026-01-01", "path": "index"},
  "content_stats": {
    "total_words": 124500,
    "avg_words_per_page": 532,
    "largest_page": {"pageId": 45, "title": "Database Architecture", "wordCount": 4523},
    "smallest_page": {"pageId": 200, "title": "Quick Note", "wordCount": 12}
  },
  "update_frequency": {
    "updated_last_24h": 3,
    "updated_last_7d": 12,
    "never_updated": 45,
    "avg_updates_per_page": 2.3
  }
}
```

## Design questions

- **Granularity**: all stats are computed from cached or indexed data. No content reading. This keeps it fast at scale.
- **What's the difference from `wiki_health` (P3)?**
  - `wiki_stats`: aggregate numbers. "The wiki has 234 pages, 5% are orphans."
  - `wiki_health`: actionable lists. "Here are the 12 orphan pages you should link."
  - Use `wiki_stats` for monitoring, `wiki_health` for triage.
- **Growth calculation**: `growth_last_30d` = pages created in last 30 days. `growth_last_7d` for short-term.
- **Update frequency**: computed from `updatedAt` vs `createdAt`. Pages with equal dates are "never updated".
- **Should this be cached?** Yes — stats are stale-tolerant. Cache for 60 seconds, invalidate on any page change.

## Dependencies

- `wikijs_get_backlinks` (P1) — for link counts, orphan count
- `wikijs_get_page_stats` (P1) — for per-page word counts, dates, link counts
- No hard dependencies: can return partial data (null for unavailable fields) until dependencies are implemented.

Feeds into: high-level monitoring and decision-making.

## Scale considerations

- Computing all stats for 200+ pages from cached indexes (not content): a few SQL aggregate queries. Sub-second.
- Caching: results are stale for 60 seconds. At 200 pages with moderate activity, this is acceptable.
- No content reading: this tool never fetches page content. All data comes from `page_stats` cache and backlink index.
- Progressive enhancement: start with basic stats (total pages, newest/oldest). Add link stats when backlinks are ready. Add growth stats when history is tracked.

## Implementation plan

1. Design SQL aggregate queries for each stat from `PageStatsCache` and `BacklinkIndex`
2. Implement caching with 60-second TTL and change-based invalidation
3. Implement content stats from page_stats cache
4. Implement link stats from backlink index
5. Implement growth calculation from `createdAt` dates
6. Implement update frequency from `updatedAt` vs `createdAt`
7. Handle partial results mode (null for unavailable fields)
8. Add tool to `tools_pages.py` or `tools_system.py`
9. Update documentation
10. Verify by creating pages with varying ages, sizes, and link counts

## Acceptance criteria

- Returns aggregate stats for the entire wiki in one call
- Orphan count, stale count, and link stats are accurate (when dependencies available)
- Growth calculations correctly reflect page creation dates
- Most-linked/most-linking pages are correctly identified
- Stats complete in < 1 second on 200+ pages
- Returns partial results gracefully when dependencies aren't ready
- Caching correctly invalidates after page changes

---

## Implementation notes (2026-05-23)

- 60-second cache via module-level `_stats_cache` dict with timestamp
- Cache invalidated on page create/update via `_invalidate_stats_cache()` hook
- All data from BacklinkIndex + pages.list — NO content reading
- `createdAt` not available in pages.list → growth stats null
- Most linked/linking resolved via bulk_get_pages batch title lookup
