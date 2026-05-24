# wikijs_get_page_stats — Full Implementation Plan

---

- **Status**: `completed`
- **Priority**: P1 — Metadata-first triage essential at scale
- **Dependencies**: `wikijs_get_backlinks` (P1, completed) — for `inboundLinkCount`

## Purpose

Return key metadata about a page without its full content. The agent uses this to decide WHICH pages to read before calling `bulk_get_pages`. At 200+ pages, reading every page to triage is not viable.

## Design decisions

### No caching layer for v1

The original subplan suggested a `PageStatsCache` SQLite table. **Skipped.** Each call is O(1):
- 1 GraphQL query (for content + metadata from `_GET_PAGE_BY_ID_QUERY`)
- 1 SQLite query (BacklinkIndex for inbound count)

Content stats (word count, outbound links) are computed on the fly — `len()`, `split()`, and `_extract_links()` are cheaper than maintaining cache invalidation hooks on every write. The BacklinkIndex already acts as a write-through cache for inbound links.

### Data sources

| Field | Source |
|-------|--------|
| `pageId`, `title`, `path`, `description`, `isPublished`, `createdAt`, `updatedAt`, `tags` | Wiki.js GraphQL via `_GET_PAGE_BY_ID_QUERY` |
| `contentLength` | `len(content)` |
| `wordCount` | `len(content.split())` — simple whitespace split, sufficient for agent triage |
| `outboundLinkCount` | `len(_extract_links(content))` — reuses existing helper |
| `inboundLinkCount` | `SELECT COUNT(*) FROM BacklinkIndex WHERE target_page_id = X` — live since backlinks is done |

### Batch variant: two-phase approach

`wikijs_bulk_get_page_stats(page_ids)`:

1. `wikijs_bulk_get_pages(page_ids, include_content=True)` — 1 round trip for all content
2. `SELECT target_page_id, COUNT(*) FROM BacklinkIndex WHERE target_page_id IN (...)` — 1 SQL query
3. Compute stats client-side, assemble response

O(1) round trips. Same 50-ID cap as `bulk_get_pages`.

### Output format

```json
{
  "pageId": 7,
  "title": "Architecture",
  "path": "docs/architecture",
  "contentLength": 4532,
  "wordCount": 680,
  "outboundLinkCount": 12,
  "inboundLinkCount": 5,
  "lastModified": "2026-05-20T14:30:00.000Z",
  "createdAt": "2026-01-15T09:00:00.000Z",
  "tags": ["docs", "reference"],
  "isPublished": true,
  "description": "System components and data flows"
}
```

Single: returns the object directly. Batch: returns `{results: [...], summary: {requested, returned, failed}}`.

## Implementation steps

### 1. `wikijs_get_page_stats` in `tools_pages.py`

```python
@mcp.tool()
async def wikijs_get_page_stats(page_id: int) -> str:
```

Logic: authenticate -> GraphQL `pages.single(id: page_id)` -> compute stats -> query BacklinkIndex for inbound count -> return JSON.

### 2. `wikijs_bulk_get_page_stats` in `tools_pages.py`

```python
@mcp.tool()
async def wikijs_bulk_get_page_stats(page_ids: List[int]) -> str:
```

Logic: validate input -> authenticate -> `wikijs_bulk_get_pages` -> compute stats per page -> batch query BacklinkIndex -> return `{results, summary}`.

### 3. Update documentation

- `MCP_TOOL_CATALOG.md`: count 24 -> 26, 2 new entries
- `STATUS.md`: status -> `completed`

## Logging

| Event | Level | Message |
|-------|-------|---------|
| Stats called | `INFO` | `page_stats for page {id}: wordCount={N}, links={out}/{in}` |
| Batch stats called | `INFO` | `bulk_page_stats: requested={N}, returned={M}, failed={K}` |

## Test results (2026-05-22)

6/6 tests pass. Single-page stats work, bulk stats use bulk_get_pages + BacklinkIndex batch query.

| Test | Result | Notes |
|------|--------|-------|
| Single page stats | PASS | wordCount=202, outbound=3, inbound=10 for Architecture |
| inboundCount matches backlinks | PASS | stats count (10) == backlinks count (10) |
| No content returned | PASS | content key absent from response |
| Non-existent page | PASS | Returns error JSON |
| Bulk 5 pages | PASS | All 5 returned with stats |
| Bulk partial failure | PASS | 2 valid + 2 invalid -> 2 results + 2 errors |

## Acceptance criteria

- [x] Returns all listed fields for a valid page ID
- [x] `wordCount` and `outboundLinkCount` are accurate
- [x] `inboundLinkCount` is accurate (backlinks completed)
- [x] Does NOT return full page content
- [x] `bulk_get_page_stats` on 5 pages completes correctly
- [x] Fails gracefully with clear error for non-existent page ID
- [x] Partial failure in batch: valid stats returned alongside errors

## Verification

1. Rebuild Docker
2. `wikijs_get_page_stats(9)` — verify architecture page stats, all fields populated
3. `wikijs_get_page_stats(99999)` — error message
4. `wikijs_bulk_get_page_stats([7,8,9,10,11])` — 5 pages with stats
5. Compare `inboundLinkCount` with `wikijs_get_backlinks(9).count`
6. Spot-check `wordCount` against known content
