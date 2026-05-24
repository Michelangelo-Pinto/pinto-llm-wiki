# Task 02: SQLite Indexes on BacklinkIndex

| Field | Value |
|-------|-------|
| Status | completed |
| Priority | P2 |
| Effort | Small |
| Depends on | none |
| Blocks | none |

## Objective

Add explicit SQLite indexes on `BacklinkIndex.source_page_id` and `BacklinkIndex.target_page_id` to improve BFS graph traversal and backlink lookup performance at 1000+ pages.

## Background

The v3 `BacklinkIndex` table currently has no explicit indexes beyond the implicit primary key index. At current scale (~200 pages, ~1000 edges), full table scans are fast enough. At larger scale, indexes become important.

This was documented as a known optimization in `doc_v3/architecture/database.md`:

```python
Index('idx_backlinks_source', BacklinkIndex.source_page_id)
Index('idx_backlinks_target', BacklinkIndex.target_page_id)
```

## Implementation Plan

1. Read the current `BacklinkIndex` model in `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/db.py`

2. Add the two SQLAlchemy Index definitions to the `BacklinkIndex` model's `__table_args__`

3. The indexes will be auto-created on next startup via `Base.metadata.create_all(engine)` (already called at import time)

4. Verify indexes exist:

```bash
docker compose exec wiki-js-mcp sqlite3 /data/wikijs_mappings.db ".indices backlinks"
```

5. Run existing tests to confirm no regressions:

```bash
docker compose --profile integration run --rm test-runner pytest tests/regression/ -v
```

## Decisions

### 2026-05-24 — Task 02: Index placement

**Decision:** Added both indexes via `__table_args__` on the `BacklinkIndex` model, using `Index()` imported from SQLAlchemy. Indexes will auto-create on next startup via existing `Base.metadata.create_all(engine)`.

**Rationale:** Using `__table_args__` is the standard SQLAlchemy declarative pattern for table-level constraints. The indexes are lightweight (B-tree on integer columns) and will improve BFS graph traversal performance at scale.

## Documentation Updates

- [ ] `doc_v3/improvements/index.md` — mark "SQLite indexes on BacklinkIndex" as completed
- [ ] `doc_v3/architecture/database.md` — update the "SQLite Performance" section to note indexes are now applied

## Completion Criteria

- [ ] `idx_backlinks_source` index exists on `backlinks` table
- [ ] `idx_backlinks_target` index exists on `backlinks` table
- [ ] All existing tests pass (no regressions)
- [ ] Wiki.js MCP rebuilds and starts successfully

## Notes

- Added `Index` to the import from `sqlalchemy` in `db.py`
- Added `idx_backlinks_source` (on `source_page_id`) and `idx_backlinks_target` (on `target_page_id`)
- No migration needed — SQLAlchemy `create_all` is called at module import time
