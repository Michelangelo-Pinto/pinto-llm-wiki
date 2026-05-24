# Tag management tools (hierarchical)

---

- **Status**: `completed`
- **Priority**: P2

## Why

The LLM Wiki pattern uses tags for categorization:

> If your LLM adds YAML frontmatter to wiki pages (tags, dates, source counts), Dataview can generate dynamic tables and lists.

At scale (200+ pages), flat tags are insufficient. The agent needs:
- **Hierarchical tags**: `tech/python/async` structure for organizing large numbers of pages
- **Facet filtering**: filter by combinations of tag + category + status, not just one tag at a time
- **Tag-aware navigation**: find all pages in a tag subtree, not just exact matches

The current MCP server can set tags when creating/updating a page but cannot list or search by them. This gap blocks both navigation and organization at scale.

## What

Four new tools:

### 1. `wikijs_search_by_tag`

```python
wikijs_search_by_tag(tag: str, include_subtags: bool = False) -> str
```

Returns all pages that have the given tag. If `include_subtags=True` and tag is hierarchical (e.g., `tech`), also returns pages tagged `tech/python`, `tech/python/async`, etc.

Each result: `{pageId, title, path, description, tags, lastModified}`.

### 2. `wikijs_list_all_tags`

```python
wikijs_list_all_tags(hierarchical: bool = False) -> str
```

If `hierarchical=False`: flat deduplicated list of all tags with `{tag, pageCount}`.
If `hierarchical=True`: tree structure with `{tag, pageCount, children: [...]}`.

### 3. `wikijs_set_page_tags`

```python
wikijs_set_page_tags(page_id: int, tags: List[str]) -> str
```

Replaces the tag list for a page. Returns `{pageId, title, tags: [...]}`.

### 4. `wikijs_filter_pages` (NEW — facet filter)

```python
wikijs_filter_pages(filters: Dict[str, str]) -> str
```

Multi-facet filtering. Example filters: `{"tag": "tech", "status": "draft", "category": "docs"}`. Returns pages matching ALL filters (AND logic). Each result: `{pageId, title, path, tags, lastModified}`.

## Design questions

- **How does Wiki.js expose tags in its GraphQL API?**
  - `pages.list` returns tags as `[{tag: "..."}, {tag: "..."}]`
  - Verify if there's a direct `tags` query or filter in the GraphQL schema
- **Hierarchical tags**: Wiki.js tags are flat strings. Hierarchy is a convention (e.g., `tech/python/async`). The MCP server interprets `/` as hierarchy separator. Subtag queries use prefix matching: `tag LIKE 'tech/%'`.
- **For `search_by_tag`**: if Wiki.js has no native tag filter, fall back to client-side filtering from `pages.list`. At 200+ pages this is fine with a single query.
- **For `list_all_tags`**: same — client-side deduplication from `pages.list`. Cache results for 60 seconds at scale.
- **For `filter_pages`**: this is purely client-side filtering on the MCP server. Fetch all pages once, apply intersection of filters. At 200-500 pages this is fast enough.
- **For `set_page_tags`**: must use `pages.update` with full page data. Fetch page first, update only tags, preserve content/title/etc.

## Dependencies

- None. Uses existing Wiki.js GraphQL queries.
- Feeds into: `smart_query` (P2), `affected_pages` (P4), `wiki_health` (P3).

## Scale considerations

- Tag list caching: `list_all_tags` results should be cached for 60 seconds. On page create/update/tag change, invalidate cache.
- Hierarchical tag queries use SQL `LIKE 'prefix/%'` pattern. Efficient on indexed columns.
- `filter_pages` with many facets on 500+ pages: consider adding a `limit` parameter.
- Tag count tracking in SQLite: pre-compute `tag -> [page_ids]` mapping for O(1) lookup.

## Implementation plan

1. Research Wiki.js GraphQL schema for tag-related queries
2. Implement `search_by_tag` with subtag support
3. Implement `list_all_tags` with hierarchical option
4. Implement `set_page_tags` (fetch + update pattern)
5. Implement `filter_pages` with AND logic
6. Add tag cache in SQLite for scale
7. Add tools to `tools_pages.py`
8. Update documentation
9. Verify by creating pages with hierarchical tags, searching subtags, and facet filtering

## Acceptance criteria

- `list_all_tags` returns all unique tags with page counts
- `list_all_tags(hierarchical=True)` returns tree structure with correct parent-child relationships
- `search_by_tag("tech", include_subtags=True)` returns pages tagged `tech`, `tech/python`, `tech/python/async`
- `filter_pages` with multiple facets returns pages matching ALL conditions
- `set_page_tags` replaces a page's tags without affecting content
- All tools work correctly on an empty wiki (no tags)
- At 200+ pages, `list_all_tags` completes in < 1 second (cached)

---

## Implementation notes (2026-05-22)

### Actual design decisions vs planned

| Aspect | Planned | Implemented | Why |
|--------|---------|-------------|-----|
| SQLite cache | TagIndex model for O(1) lookup | Not implemented | Single `pages.list` call suffices at 200+ pages (~500ms). Add later if needed. |
| `list_all_tags` cache | 60s in-memory cache | Not implemented | Same reason — fast enough without caching at current scale. |
| `pages.list` tags format | Assumed `tags { tag }` | `tags` (plain `[String]`) | Wiki.js `pages.list` returns tags as `[String]`, unlike `pages.single` which returns `[{tag: "..."}]`. Important finding for future implementors. |

### Design rationale

**No SQLite, no caching**: The tag tools share a single `pages.list` GraphQL call per invocation. At 200+ pages, this returns in ~500ms and the client-side filtering adds negligible overhead. This keeps the implementation simple and avoids the complexity of cache invalidation hooks (which `BacklinkIndex` requires). If performance degrades at 500+ pages, adding a `TagIndex` model with hooks on create/update/delete is straightforward and follows the existing `BacklinkIndex` pattern.

**Hierarchical tags as convention**: Wiki.js has no native hierarchical tag support. Using "/" as a separator keeps tags human-readable and tooling simple. Prefix matching (`tag.startswith("tech/")`) correctly identifies all subtags without false positives.

**Client-side filtering**: Wiki.js GraphQL API has no native `filterByTag` argument on `pages.list`. Client-side filtering is the only viable approach without modifying the Wiki.js server.

### Test results

12/12 tests passed inside Docker container:
- `search_by_tag` exact match and prefix matching
- `list_all_tags` flat and hierarchical tree
- `set_page_tags` content preservation
- `filter_pages` single and multi-facet AND logic
- Edge cases: empty tag, empty filters, non-existent tag, empty wiki
