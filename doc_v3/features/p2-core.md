# P2 — Core Workflow

P2 features enable the core LLM Wiki operations: ingestion (append, tags), query (smart_query), and navigation (link graph).

---

## `wikijs_append_to_page`

**Priority**: P2 | **File**: [`tools_pages.py` line 1127](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Append (or prepend) content to a page without fetching and rewriting the entire content manually. Uses optimistic locking with post-write verification.

### Why

The LLM Wiki `log.md` is append-only. Without append, updating the log requires fetch → modify → write, which is wasteful and prone to race conditions.

### Signature

```python
wikijs_append_to_page(page_id: int, content: str, position: str = "end") -> str
```

### Design

- Fetches current content, appends/prepends, writes back, verifies
- Retries up to 3 times if a concurrent writer modified the page
- Returns `{pageId, title, status: "appended", newContentLength, attempts}`

---

## Tag Management (4 tools)

**Priority**: P2 | **File**: [`tools_pages.py` line 1260](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

### Why

Tags are the simplest categorization mechanism. At scale, the agent needs hierarchical tags (`tech/python/async`) and multi-facet filtering.

### Design

- **No SQLite cache**: `pages.list` with tags → client-side filtering. Sufficient at 200+ pages (~500ms)
- **Hierarchical tags as convention**: `/` as separator, `startswith` prefix matching for subtags
- **`pages.list` tags format**: flat string array from Wiki.js GraphQL

### Tools

| Tool | Signature | Line |
|------|-----------|------|
| `wikijs_search_by_tag` | `(tag, include_subtags=False)` | 1260 |
| `wikijs_list_all_tags` | `(hierarchical=False)` | 1325 |
| `wikijs_set_page_tags` | `(page_id, tags)` | 1402 |
| `wikijs_filter_pages` | `(filters)` | 1491 |

**`wikijs_search_by_tag`**: Fetches all pages, filters by exact or prefix match (subtags). Returns `{results, total, tag, includeSubtags}`.

**`wikijs_list_all_tags`**: Deduplicates tags, counts occurrences. Hierarchical mode builds a tree from `/`-separated tags.

**`wikijs_set_page_tags`**: Fetch current page, update only tags field, preserve content/title/path.

**`wikijs_filter_pages`**: Multi-facet AND filtering (`tag`, `locale`, `isPublished`). Client-side from `pages.list`.

---

## `wikijs_smart_query`

**Priority**: P2 | **File**: [`tools_pages.py` line 1564](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Hybrid search combining semantic (Qdrant) and keyword results via Reciprocal Rank Fusion (RRF).

### Why

At scale, the agent needs a single tool that finds the most relevant pages by meaning (not just keywords), ranks them, returns snippets, and includes link context.

### Signature

```python
wikijs_smart_query(query: str, limit: int = 10, include_summaries: bool = True, include_link_context: bool = True) -> str
```

### Pipeline (v3)

1. **Parallel**: semantic search (Qdrant `wiki_pages` collection via `QdrantClient.query_points`) + keyword search (`wikijs_search_pages`)
2. **Embedding**: `SentenceTransformer("all-MiniLM-L6-v2")` computed in-process for the query vector
3. **RRF merge**: `RRF(d) = sum( 1 / (k + rank_in_source) )`, k=60
4. Enrich: summaries (first 500 chars), link context (BacklinkIndex)

### Fallback modes

| Mode | Condition |
|------|-----------|
| `full` | Both semantic (Qdrant populated) and keyword available |
| `semantic` | Wiki.js search failed, Qdrant OK |
| `keyword` | Qdrant collection missing/empty, Wiki.js search OK |

### v3 vs v2

v2 used embedded `PageVector` in SQLite. v3 queries the external Qdrant `wiki_pages` collection. Wiki page vectors must be populated separately via `qdrant_upsert_chunks` (Qdrant MCP) — there is no automatic upsert hook on page create/update in wiki-js-mcp.

### Dependencies

- `wikijs_search_pages` (existing)
- Qdrant `wiki_pages` collection (external)
- `wikijs_bulk_get_pages` (P1) — for summaries
- `BacklinkIndex` (P1) — for link context

See [P4 — Scale](p4-scale.md) for Qdrant indexing details.

---

## Link Graph (3 tools)

**Priority**: P2 | **File**: [`tools_graph.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_graph.py)

Graph awareness for navigation, ingestion, and lint.

### Tools

| Tool | Signature | Line |
|------|-----------|------|
| `wikijs_extract_page_links` | `(page_id, link_type="all")` | 60 |
| `wikijs_get_page_graph` | `(page_id, depth=1, direction="both", max_nodes=50)` | 151 |
| `wikijs_find_shortest_path` | `(from_page_id, to_page_id, max_depth=5)` | 267 |

**`wikijs_extract_page_links`**: Internal links via `_extract_links`, external via separate regex. Resolves internal paths to IDs. Flags broken links.

**`wikijs_get_page_graph`**: BFS traversal using BacklinkIndex. Direction modes: outgoing, incoming, both. Cycle detection via visited set. Truncation flag when `max_nodes` hit.

**`wikijs_find_shortest_path`**: Bidirectional BFS. Forward from source (outgoing), backward from target (incoming). Reconstructs path on meeting point.

### Design

- **No new SQLite tables**: All graph data from existing `BacklinkIndex`
- **Bidirectional BFS**: O(b^(d/2)) vs O(b^d) for shortest path
- **max_nodes cap**: 50 default, prevents graph explosion at depth > 1

### Dependencies

- `BacklinkIndex` (P1) — for all link queries
- `_extract_links`, `_resolve_paths_to_ids` (P1) — for link extraction
- `wikijs_bulk_get_pages` (P1) — for title resolution
