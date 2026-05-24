# wikijs_get_recent_changes

---

- **Status**: `completed`
- **Priority**: P3

## Why

For incremental wiki maintenance, the agent needs to know what changed recently. This enables:

- **Ingest**: after processing a batch of sources, review what pages were touched
- **Lint**: focus lint checks on recently modified pages (most likely to have new inconsistencies)
- **log.md population**: generate chronological entries for the wiki log
- **Trip planning**: "show me what I've been working on this week"

The LLM Wiki pattern's `log.md` serves this purpose, but the agent needs a tool to populate and verify it against actual wiki state.

## What

```python
wikijs_get_recent_changes(limit: int = 20, since_days: int = None, since_date: str = None) -> str
```

- `limit`: max number of pages to return
- `since_days`: return pages modified in the last N days (e.g., 7)
- `since_date`: return pages modified since a specific ISO date (e.g., "2026-05-15") — overrides `since_days`

Returns a list of pages, each with: `{pageId, title, path, updatedAt, description}`. Sorted by `updatedAt` descending.

## Design questions

- **Does Wiki.js GraphQL support date filtering on `pages.list`?**
  - Need to research the GraphQL schema. Possible approaches:
    - Option A: Native filter in GraphQL query (if `pages.list` has date filters)
    - Option B: Fetch all pages, filter client-side by `updatedAt`
    - Option B is simpler but less efficient at scale
- **What's the `updatedAt` field format?** Wiki.js returns ISO 8601 strings. Need to parse and compare.
- **Should this also support filtering by creation date?**
  - Not initially. Focus on modification date, which is the primary use case.
- **Interaction with log.md**: this tool provides the raw data; the agent writes to log.md. Don't couple them.

## Dependencies

- None. Uses existing Wiki.js GraphQL `pages.list` with `updatedAt` field.

## Implementation plan

To be created in a dedicated plan. The plan should cover:

1. Research Wiki.js GraphQL schema for date filtering support
2. Implement client-side date filtering as fallback
3. Handle timezone considerations (UTC vs local)
4. Add tool to `tools_pages.py` (or `tools_system.py`)
5. Update documentation
6. Verify by modifying pages and checking recent changes

## Acceptance criteria

- Returns pages modified within the specified time window
- Results are sorted by `updatedAt` descending (most recent first)
- `limit` parameter respects the cap
- Works with both `since_days` and `since_date`
- Returns empty list (not error) when no pages match
- Fails gracefully if Wiki.js returns unexpected date formats

---

## Implementation notes (2026-05-23)

- Client-side ISO 8601 date parsing from pages.list updatedAt
- `since_date` overrides `since_days` when both provided
- Wiki.js GraphQL has NO native date filter — filtering is Python-side
- No SQLite usage — pure metadata from pages.list
