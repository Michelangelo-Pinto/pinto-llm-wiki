# Vector search engine

---

- **Status**: `completed`
- **Priority**: P4

## Why

At scale (200+ pages), keyword search is insufficient. Pages about "authentication methods" that use words like "login", "OAuth", "SSO" won't match keyword queries for "authentication". The LLM Wiki pattern explicitly calls for concept-level search:

> [qmd](https://github.com/tobi/qmd) is a good option: it's a local search engine for markdown files with hybrid BM25/vector search and LLM re-ranking, all on-device.

The original design (old P4-09 semantic_search) considered external tools like qmd. For a **self-contained MCP server**, an embedded engine is simpler to deploy and maintain. It serves as infrastructure for higher-level tools (`smart_query` P2, `affected_pages` P4) rather than being a standalone search tool.

## What

### Architecture: embedded engine with SQLite

Instead of an external process, the vector engine runs within the MCP server using `sqlite-vec` (a SQLite extension for vector storage) or `sentence-transformers` (for embedding generation).

```
flowchart LR
  Agent["LLM Agent"]
  SmartQ["smart_query (P2)"]
  Affected["affected_pages (P4)"]
  VSearch["wikijs_vector_search"]
  Embed["Embedding Engine"]
  SQLite["SQLite + vec"]
  Agent --> SmartQ
  Agent --> Affected
  SmartQ --> VSearch
  Affected --> VSearch
  VSearch --> Embed
  VSearch --> SQLite
  Embed --> SQLite
```

### Tools

### 1. `wikijs_vector_search`

```python
wikijs_vector_search(query: str, limit: int = 10) -> str
```

Search by semantic meaning. Returns:
```json
{
  "query": "authentication methods",
  "results": [
    {"pageId": 7, "title": "Authentication", "path": "auth/overview", "similarity": 0.92},
    {"pageId": 12, "title": "OAuth 2.0", "path": "auth/oauth", "similarity": 0.87},
    {"pageId": 55, "title": "Session Management", "path": "web/sessions", "similarity": 0.81}
  ],
  "index_info": {"total_vectors": 234, "last_rebuilt": "2026-05-21T10:00:00Z"}
}
```

### 2. `wikijs_rebuild_vector_index`

```python
wikijs_rebuild_vector_index(force: bool = False) -> str
```

Rebuilds the embedding index for all wiki pages. Should be called after bulk imports or major content changes. With `force=True`, drops and recreates the entire index. Without `force`, only indexes pages modified since last rebuild.

Returns: `{status: "completed", pages_indexed: 234, duration_seconds: 45}`

## Design decisions

### Option A: sqlite-vec

- Pros: Runs inside the MCP server, no external process, simple SQL interface, supports cosine/kNN
- Cons: Requires embedding model separately, vec extension needs compilation/loading
- Dependencies: `sqlite-vec` Python package, `sentence-transformers` (or `all-MiniLM-L6-v2` model)

### Option B: ChromaDB

- Pros: Purpose-built for vector search, rich query API, metadata filtering
- Cons: External process, heavier dependency, overkill for 200-1000 pages

### Recommendation

**Option A (sqlite-vec)**. At 200-1000 pages, a lightweight SQLite-based solution is sufficient. It keeps the MCP server self-contained and avoids external service management. If scale grows beyond ~10,000 pages, revisit ChromaDB or qmd.

## Design questions

- **Which embedding model?**
  - `all-MiniLM-L6-v2` (384 dimensions, 80MB): good balance of quality and size. Works for 200-5000 pages.
  - `all-mpnet-base-v2` (768 dimensions, 420MB): higher quality, larger. Consider if quality is more important than size.
  - Recommendation: start with `all-MiniLM-L6-v2`. It's small enough to bundle and fast enough for real-time queries.
- **When to rebuild the index?**
  - On every page create/update/delete — update the vector for that page
  - `wikijs_rebuild_vector_index` for full rebuilds after bulk operations
  - Staleness tracking: store `vector_updated_at` per page in SQLite
- **Page chunking**: for very long pages (5000+ words), split into sections and embed each section separately. Query matches return the best-matching section.
  - For now, embed the entire page content. Chunking can be added later.
- **Integration with `smart_query` (P2)**: `smart_query` calls `vector_search` internally for the semantic component, then merges results with keyword search via RRF.

## Dependencies

- New Python dependencies: `sentence-transformers`, `torch` (or ONNX runtime for lighter weight)
- No tool dependencies. This is infrastructure, not a dependency consumer.
- Powers: `smart_query` (P2), `affected_pages` (P4)

## Scale considerations

- Embedding 200 pages with MiniLM-L6-v2: ~30-60 seconds for initial index build. Incremental updates are instant.
- Query time: < 100ms for 200 vectors, < 500ms for 2000 vectors.
- Storage: 384 floats × 4 bytes × 200 pages = ~300KB. Negligible.
- Memory: loading the model (~80MB) increases server memory. Acceptable for a dedicated MCP server.
- ONNX runtime option: faster inference, smaller dependency than full PyTorch. Consider for production.

## Implementation plan

1. Evaluate `sqlite-vec` availability and compatibility (Python package, SQLite extension loading)
2. Select embedding model (`all-MiniLM-L6-v2` initial choice)
3. Design SQLite `PageVectors` table schema
4. Implement embedding generation for page content
5. Implement `wikijs_vector_search` with cosine similarity ranking
6. Implement `wikijs_rebuild_vector_index` with incremental update support
7. Hook into page create/update/delete for automatic vector updates
8. Add tools to `tools_pages.py` or new `tools_search.py`
9. Update `docker-compose.yml` and `requirements.txt` for new dependencies
10. Add ONNX runtime option as lighter-weight alternative
11. Benchmark search quality against keyword-only `wikijs_search_pages`
12. Update documentation

## Acceptance criteria

- `vector_search` returns pages conceptually related to the query, not just keyword matches
- `vector_search` query completes in < 500ms on 200 pages
- `rebuild_vector_index` indexes all pages and reports count and duration
- Incremental updates work: editing a page updates its vector, not the entire index
- Search quality is measurably better than keyword-only for semantic queries (e.g., "how to handle user sessions" should find pages about cookies, tokens, timeouts)
- Graceful fallback: if the model fails to load, `vector_search` returns a clear error (doesn't crash server)
- Smart_query (P2) can use this as its semantic component via internal function call

---

## Implementation notes (2026-05-23)

### Design decisions

| Aspect | Planned | Implemented | Why |
|--------|---------|-------------|-----|
| Vector DB | sqlite-vec | Pure Python cosine similarity | sqlite-vec is pre-v1 alpha with arm64 Docker issues. At 200 pages × 384 dims, brute force < 1ms |
| Embedding model | all-MiniLM-L6-v2 | same | 384-dim, 80MB, good quality/size balance |
| Vector storage | SQLite BLOB | SQLite TEXT (JSON) | Debuggable, portable, no binary serialization overhead |
| Incremental updates | Hook on create/update/delete | same | Fire-and-forget pattern like _sync_backlinks_for_page |
| Chunking | Future consideration | Not implemented | Whole page content embedded. Sufficient for 200+ pages |

### Key deviations from original plan

- **No sqlite-vec**: The original design (Option A) recommended sqlite-vec. Research showed the library is pre-v1 alpha (v0.1.10-alpha.3) with open arm64 issues (#211). For 200 pages, brute force cosine similarity in Python is trivially fast (~0.003ms per comparison, < 1ms total).
- **No ONNX runtime**: torch is large (~1GB in Docker image) but simpler to set up than ONNX. Acceptable for a dedicated MCP server.
- **PageVector JSON**: Using TEXT column with JSON instead of BLOB. Makes debugging trivial (SELECT vector_json FROM page_vectors) and is portable across SQLite versions.

### Model loading

The `all-MiniLM-L6-v2` model is lazy-loaded on first use (~2s cold start, ~80MB memory). Downloaded from HuggingFace Hub at first Docker container start. Subsequent calls reuse the singleton.

### Integration with smart_query

`wikijs_smart_query` (P2-06) uses internal helper functions (`_get_model`, `_compute_embedding`, `_cosine_similarity`) to perform semantic search in parallel with keyword search. Results are merged via Reciprocal Rank Fusion (k=60).

### Test results

6/6 tests passed inside Docker container:
- Full rebuild (31 pages indexed in 0.65s)
- Semantic search returns conceptually relevant results
- Empty query returns error
- limit parameter respected
- Incremental update on page create
- Non-force rebuild skips existing vectors
