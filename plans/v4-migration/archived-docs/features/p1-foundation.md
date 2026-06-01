# P1 — Foundation

Foundation features are blockers: without batch read, backlinks, and stats, the agent cannot operate efficiently on a wiki of any size beyond a handful of pages.

---

## `wikijs_bulk_get_pages`

**Priority**: P1 | **File**: [`tools_pages.py` line 631](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Read multiple pages (full content) in a single MCP tool call via parallel `asyncio.gather`.

### Why

In the LLM Wiki pattern, the agent must read the index, then read multiple pages to answer a query or perform ingestion. Without batch read, 10 pages = 10 round trips. At 200+ pages, every operation would be painfully slow.

### Signature

```python
wikijs_bulk_get_pages(page_ids: List[int], include_content: bool = True) -> str
```

### Return

```json
{
  "results": [{"pageId": 7, "title": "Auth", "path": "docs/auth", "content": "..."}],
  "errors": [{"pageId": 99, "error": "Page not found"}],
  "summary": {"requested": 5, "returned": 4, "failed": 1}
}
```

### Code

- Parallel GraphQL via `asyncio.gather(*tasks, return_exceptions=True)`
- Cap: `BULK_GET_MAX_PAGES = 50` (line 26)
- Deduplicates IDs preserving order
- Reuses `_GET_PAGE_BY_ID_QUERY` constant (line 28)
- Partial success: valid pages returned alongside errors

### Dependencies

None. Standalone tool.

---

## Backlinks (2 tools)

**Priority**: P1 | **File**: [`tools_pages.py` line 735](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Foundation for link graph, health, and affected pages. Powered by SQLite `BacklinkIndex`.

### `wikijs_get_backlinks`

Given a page ID, returns all pages that link to it.

```python
wikijs_get_backlinks(page_id: int) -> str
```

**Return**: `{pageId, title, backlinks: [{sourcePageId, sourceTitle, sourcePath, linkText}], count}`

**Flow**:
1. Query `BacklinkIndex` filtered by `target_page_id == page_id`
2. Collect unique source page IDs
3. Batch-resolve source page titles via `wikijs_bulk_get_pages`

### `wikijs_rebuild_backlink_index`

Full index rebuild from scratch. Call after bulk imports.

```python
wikijs_rebuild_backlink_index() -> str
```

**Flow**:
1. List all page IDs via `pages.list`
2. Bulk-read all content via `wikijs_bulk_get_pages`
3. Clear existing index
4. Extract markdown links via `_extract_links()`
5. Resolve paths to IDs via `_resolve_paths_to_ids()`
6. Insert rows, skip broken/self-links

### Link extraction

`_extract_links(content)` ([line 82](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)):
- Regex: `\[([^\]]+)\]\(([^)]+)\)` matches standard markdown links
- Filters: image links `![alt](url)`, self-links `#anchor`, external `http(s)://`
- Normalizes paths: strips leading `/`, strips `#fragment`

### Incremental maintenance

`_sync_backlinks_for_page(page_id, content)` ([line 140](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)):
- Called after `wikijs_create_page` and `wikijs_update_page`
- Full replace strategy: delete old entries, insert new ones
- Fire-and-forget: failures logged, not propagated

### Code links

| Function | Line | Purpose |
|----------|------|---------|
| `wikijs_get_backlinks` | 735 | Query backlinks for a page |
| `wikijs_rebuild_backlink_index` | 850 | Full index rebuild |
| `_extract_links` | 82 | Markdown link extraction |
| `_resolve_paths_to_ids` | 113 | Path-to-ID resolution (parallel) |
| `_sync_backlinks_for_page` | 140 | Incremental index update |

---

## Page Stats (2 tools)

**Priority**: P1 | **File**: [`tools_pages.py` line 964](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Return metadata about pages WITHOUT full content. Enables metadata-first triage at scale.

### `wikijs_get_page_stats`

```python
wikijs_get_page_stats(page_id: int) -> str
```

**Return**: `{pageId, title, path, contentLength, wordCount, outboundLinkCount, inboundLinkCount, lastModified, createdAt, tags, isPublished, description}`

**Signals provided**:
- **Size**: `contentLength`, `wordCount`
- **Links**: `outboundLinkCount` (from `_extract_links`), `inboundLinkCount` (from SQLite)
- **Freshness**: `lastModified`, `createdAt`
- **Metadata**: `tags`, `isPublished`, `description`

### `wikijs_bulk_get_page_stats`

```python
wikijs_bulk_get_page_stats(page_ids: List[int]) -> str
```

**Two-phase batch**:
1. Bulk-fetch content via `wikijs_bulk_get_pages`
2. Single GROUP BY query for all inbound counts from BacklinkIndex

### Code links

| Function | Line |
|----------|------|
| `wikijs_get_page_stats` | 964 |
| `wikijs_bulk_get_page_stats` | 1032 |

### Dependencies

- `wikijs_bulk_get_pages` (P1) — for content reading
- `BacklinkIndex` (SQLite) — for inbound link count
