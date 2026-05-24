# wikijs_get_backlinks — Full Implementation Plan

---

- **Status**: `completed`
- **Priority**: P1 — Foundation for graph, health, and affected_pages
- **Dependencies**: `wikijs_bulk_get_pages` (P1, completed) — used by rebuild tool for bulk content scanning

## Purpose

Given a page ID, return all pages that link to it. This is the foundational capability for the LLM Wiki pattern's cross-reference system. Every ingestion workflow depends on knowing which pages link to affected concepts.

## Design decisions

### Storage: SQLite `BacklinkIndex` table

**Chosen**: SQLite table in `db.py` alongside existing `FileMapping` and `RepositoryContext`.

**Why**: The project already uses SQLite. Reads are instant (microseconds for `SELECT WHERE target_page_id = X`). The write overhead — regex-scanning markdown content on every create/update — is proportional to content length, which is negligible.

**Rejected alternatives**:
- **Live scanning (scan all pages per call)**: O(N) per query. At 200+ pages, every `get_backlinks` call would require 200 GraphQL round trips. Unacceptable at scale.
- **Wiki.js API**: Wiki.js has no built-in "what links here" query.

### Link extraction: regex on markdown

**Chosen**: Regex `\[([^\]]+)\]\(([^)]+)\)` against raw markdown content.

**Filtered out**:
- Self-links: `[text](#anchor)` — no meaningful cross-reference
- External links: `[text](https://...)` — beyond wiki scope
- Image links: `![alt](path)` — not navigational

**Kept**: Wiki-internal links: `[text](/path)` and `[text](/path#anchor)`. The anchor fragment is stripped to the base path.

### Path-to-ID resolution: parallel GraphQL `pages.singleByPath`

**Chosen**: `asyncio.gather` of `pages.singleByPath` queries, same pattern as `bulk_get_pages`.

**Why**: Markdown stores links as paths (e.g., `[Architecture](/docs/architecture)`). To store as page IDs in the index, paths must be resolved. For a page with 10 links, this is 10 parallel GraphQL calls — fast.

Paths that fail to resolve (deleted pages, typos) are stored with `target_page_id=NULL` and excluded from backlink results but logged at WARNING level.

### Hooks: inline into existing tools

**Chosen**: Hook backlink maintenance into `wikijs_create_page`, `wikijs_update_page`, and `wikijs_delete_page`.

**Why**: Backlinks are invisible infrastructure. The agent should never have to manually maintain the index. Every page mutation must automatically update the backlink index. This is the key difference between `backlinks` and `affected_pages` (P4): backlinks are now/proactive, affected_pages is future/analytical.

**Risk**: hooks make existing tools more complex. **Mitigation**: backlink sync logic is extracted into standalone helper functions, keeping tool code clean.

### Schema

```python
class BacklinkIndex(Base):
    __tablename__ = "backlinks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_page_id = Column(Integer, nullable=False)      # page that contains the link
    target_page_id = Column(Integer, nullable=True)        # page being linked to (NULL if unresolved)
    target_path = Column(String, nullable=False)            # raw path from markdown link
    link_text = Column(String, default="")                  # display text of the link
    position = Column(Integer, default=0)                   # character position in source (for dedup)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)
```

Unique constraint: `(source_page_id, target_path, position)` prevents duplicates on re-index.

## Implementation steps

### 1. Add `BacklinkIndex` model to `db.py`

File: `mcp-server/src/wiki_mcp_server/db.py`

Add the SQLAlchemy model after existing `RepositoryContext`. The `Base.metadata.create_all(engine)` call auto-creates the new table on next server start.

### 2. Add utility functions

File: `mcp-server/src/wiki_mcp_server/tools_pages.py`

Three internal helper functions:

- **`_extract_links(content: str) -> List[dict]`**: regex scan for markdown links. Filters self-links and external links. Returns `[{link_text, target_path, position}]`.
- **`_resolve_paths_to_ids(paths: List[str]) -> Dict[str, Optional[int]]`**: parallel `pages.singleByPath` via `asyncio.gather`. Returns `{path: page_id or None}`.
- **`_sync_backlinks_for_page(source_page_id: int, content: str) -> None`**: orchestrates extraction, resolution, and DB upsert. Deletes old entries for this source first, then inserts new ones.

All three are module-level functions (not decorated with `@mcp.tool()`).

SingleByPath query to add as constant:

```python
_RESOLVE_PATH_QUERY = """
query($path: String!) {
    pages {
        singleByPath(path: $path, locale: "en") {
            id
        }
    }
}
"""
```

### 3. Hook into existing tools

- **`wikijs_create_page`**: after `response_result.get("succeeded")`, call `await _sync_backlinks_for_page(new_page_id, content)`.
- **`wikijs_update_page`**: after successful update (if content was provided and differs), call `await _sync_backlinks_for_page(page_id, new_content)`.
- **`wikijs_delete_page`**: after successful deletion, delete backlink rows where `source_page_id == deleted_id OR target_page_id == deleted_id`.

**Important**: backlink sync runs after the GraphQL mutation succeeds. If sync fails (e.g., DB error), the page creation still succeeded — log the error but don't roll back. The index can be repaired via `wikijs_rebuild_backlink_index`.

### 4. Implement `wikijs_get_backlinks`

```python
@mcp.tool()
async def wikijs_get_backlinks(page_id: int) -> str:
```

Logic:
1. Authenticate with Wiki.js
2. Open DB session
3. Query `BacklinkIndex` for `target_page_id == page_id`
4. If no results: return `{pageId, title, backlinks: [], count: 0}`
5. Collect unique `source_page_id` values from results
6. If 1 source: call `wikijs_get_page(source_id)` for title/path. If multiple: call `wikijs_bulk_get_pages(source_ids, include_content=False)`.
7. Build response with `linkText` from the DB row

### 5. Implement `wikijs_rebuild_backlink_index`

```python
@mcp.tool()
async def wikijs_rebuild_backlink_index() -> str:
```

Logic:
1. Authenticate with Wiki.js
2. Get ALL page IDs via GraphQL `pages.list` (returning only `id`)
3. Call `wikijs_bulk_get_pages(all_ids)` to get content for all pages
4. Open DB session, `db.query(BacklinkIndex).delete()`
5. For each page, call `_sync_backlinks_for_page(page_id, content)` — but skip the delete-old-entries step since we already cleared the table
6. Log and return summary: `{status: "completed", total_pages_scanned: N, total_links_found: M}`

**Variant**: provide a `_sync_backlinks_internal` that doesn't call `pages.singleByPath` for every page individually — instead batch all extracted paths across all pages and resolve them in one pass for efficiency.

### 6. Update documentation

- `MCP_TOOL_CATALOG.md`: add `wikijs_get_backlinks` and `wikijs_rebuild_backlink_index` to Page management (count 7 -> 9)
- `DATABASE_LAYER.md`: add `BacklinkIndex` table documentation
- `AGENTS.md`: add backlinks to ingest workflow
- `STATUS.md`: status -> `completed`

## Logging specification

| Event | Level | Message format |
|-------|-------|---------------|
| Backlink sync started | `DEBUG` | `_sync_backlinks_for_page page {id}: {N} links extracted` |
| Path not resolved | `WARNING` | `_resolve_paths_to_ids path not found: {path}` |
| Backlink sync done | `DEBUG` | `_sync_backlinks_for_page page {id}: {M} backlinks stored` |
| Get backlinks called | `INFO` | `get_backlinks for page {id}: {N} backlinks found` |
| Rebuild started | `INFO` | `rebuild_backlink_index: scanning {N} pages` |
| Rebuild done | `INFO` | `rebuild_backlink_index: completed, {N} pages, {M} links` |

## Scale considerations

### Handles 200+ pages

- **Index size**: 200 pages x ~5 links/page = ~1000 rows. SQLite handles this in microseconds.
- **Rebuild time**: ~200 GraphQL calls for content + ~2000 path resolutions. Even with graph resolution, should complete in seconds.
- **Write overhead**: each create/update adds 1 regex + N parallel GraphQL calls (where N = link count in the page). Negligible.
- **Query performance**: single SELECT with WHERE clause returns in microseconds.

### Degradation behavior

| Scenario | Behavior |
|----------|----------|
| Page with 0 links | No backlink entries created, clean |
| Page with 50+ links | 50+ parallel singleByPath calls, still fast |
| 100 pages linking to same target | 100 rows returned, bulk_get for source titles |
| Index not yet built | Return empty backlinks, agent can call rebuild |
| DB corruption | Rebuild tool repairs from scratch |

## Test results (2026-05-22)

All 7 tests pass after fixing the `WikiJSClient.authenticate()` race condition (`asyncio.Lock` + `self.authenticated` early-return in `client.py`).

| Test | Result | Notes |
|------|--------|-------|
| Rebuild index | PASS | 129 links, 0 unresolved paths |
| Create pages with cross-refs | PASS | Pages A and B created, backlinks auto-synced |
| Backlinks for Architecture (id=9) | PASS | A and B both appear, count=11 |
| Update removes backlink | PASS | Removing link from A removes its backlink |
| Empty backlinks | PASS | Non-existent page returns count=0 |
| Rebuild preserves state | PASS | Rebuild after update preserves correct index |

## Known issue resolved

The `WikiJSClient` had a race condition where concurrent `authenticate()` calls both tried the login mutation simultaneously. Fixed with `asyncio.Lock` and a `self.authenticated` early-return check.

## Acceptance criteria

- [x] Given page A links to page B, `wikijs_get_backlinks(B)` returns page A with correct `linkText`
- [x] Multiple pages linking to the same target are all returned
- [x] Backlinks are updated when a page's content changes (link added or removed)
- [x] Backlinks for a linking page are removed when the linking page is deleted
- [x] Backlinks to a deleted page are cleaned up when the target page is deleted
- [x] `wikijs_rebuild_backlink_index` reconstructs the index from scratch
- [x] Self-links and external links are not stored as backlinks
- [x] Duplicate links (same source, same path, same position) are not stored
- [x] Unresolved paths are stored with NULL target_page_id and logged at WARNING
- [x] `MCP_TOOL_CATALOG.md` and `DATABASE_LAYER.md` updated

## Verification plan

1. Rebuild Docker image and restart container
2. Create cross-reference test pages:
   - Page X: "For more details, see [Architecture](/docs/architecture)."
   - Page Y: "Read about [Architecture](/docs/architecture) and the [Overview](/docs/overview)."
3. Call `wikijs_get_backlinks(architecture_page_id)` -> verify X and Y returned
4. Update Page X to remove the link -> call `get_backlinks` -> verify X is gone
5. Delete Page Y -> call `get_backlinks` -> verify Y's backlinks are gone
6. Call `wikijs_rebuild_backlink_index` -> verify all backlinks reconstructed
7. Verify via Browser DevTools MCP that linked pages are navigable
