# P4 — Scale Optimizations

P4 features provide infrastructure and proactive tooling essential above 200 pages. In v3, semantic search is powered by **external Qdrant** instead of the v2 embedded vector engine.

---

## Qdrant Integration (v3)

**Priority**: P4 | **Replaces**: v2 `wikijs_vector_search`, `wikijs_rebuild_vector_index`, `PageVector`

v3 externalizes vector search to Qdrant. The Wiki.js MCP reads vectors at query time; indexing is a separate operation via Qdrant MCP.

### Architecture

```
LLM Agent
  │
  ├── wikijs_smart_query (P2) ──→ QdrantClient.query_points (wiki_pages)
  ├── wikijs_get_affected_pages (P4) ──→ QdrantClient.query_points (semantic signal)
  │
  └── Indexing (separate step):
        qdrant_upsert_chunks (Qdrant MCP) ──→ wiki_pages collection
        ingest_document (Ingestion Pipeline) ──→ documents collection
```

### Design decisions

| Decision | Rationale |
|----------|-----------|
| **External Qdrant** | Native KNN, payload filtering, multi-collection, no torch in wiki-js-mcp image |
| **all-MiniLM-L6-v2** | 384-dim, consistent across Qdrant MCP and Ingestion Pipeline |
| **No auto-index hook** | wiki-js-mcp does not upsert to Qdrant on page create/update; index via `qdrant_upsert_chunks` or batch scripts |
| **Lazy model in smart_query** | SentenceTransformer loaded on first semantic query (~2s cold start) |

### Indexing wiki pages

Use Qdrant MCP to populate the `wiki_pages` collection:

```python
qdrant_upsert_chunks(
    collection="wiki_pages",
    chunks=[{
        "id": "page-7",
        "vector": embedding,  # 384-dim from all-MiniLM-L6-v2
        "payload": {"page_id": 7, "title": "Auth", "path": "docs/auth", "locale": "en"}
    }]
)
```

Collection schema: see [Qdrant Vector DB](../architecture/qdrant-vector-db.md).

### Removed v2 tools

| v2 Tool | v3 Replacement |
|---------|----------------|
| `wikijs_vector_search` | `wikijs_smart_query` (semantic path) or `qdrant_search` |
| `wikijs_rebuild_vector_index` | `qdrant_upsert_chunks` batch indexing |
| `PageVector` SQLite model | Qdrant `wiki_pages` collection |

---

## `wikijs_get_affected_pages`

**Priority**: P4 | **File**: [`tools_pages.py` line 2313](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Proactive impact analysis: given a page, discovers which other pages might need updating. Combines 4 complementary signals.

### Why

When ingesting a new source, the agent must discover which existing wiki pages need updating. This is the single most expensive part of the ingestion workflow. `affected_pages` automates this discovery.

### Signature

```python
wikijs_get_affected_pages(page_id: int, max_results: int = 20, include_reasoning: bool = True) -> str
```

### Four signals (mode: "full" — all available)

| Signal | Weight | Source | Detection |
|--------|--------|--------|-----------|
| `backlink` | 1.0 | `BacklinkIndex` | Pages explicitly linking to source |
| `graph_neighbor` | 0.8 | `BacklinkIndex` | Pages within 1 hop (both directions) |
| `semantic_similarity` | 0.6 | Qdrant `wiki_pages` | Cosine similarity > 0.7 to source content |
| `shared_tags` | 0.3-0.5 | `pages.list` | 1-2 shared = 0.3, 3+ shared = 0.5 |

### Ranking

Weighted sum of participating signals. Same page from multiple signals gets highest score. Results deduplicated by page ID with accumulated `reasons` array.

### Return

```json
{
  "source": {"pageId": 7, "title": "Authentication", "path": "auth/overview"},
  "affected_pages": [{
    "pageId": 12, "title": "OAuth 2.0", "path": "auth/oauth",
    "relevance_score": 0.85, "reasons": ["backlink", "shared_tags", "graph_neighbor"]
  }],
  "signal_breakdown": {"backlinks": 5, "graph_neighbors": 6, "semantic_matches": 12, "shared_tags": 8},
  "mode": "full"
}
```

### Dependencies

- `BacklinkIndex` (P1) — backlinks + graph neighbors
- Qdrant `wiki_pages` collection — semantic similarity (signal 3)
- `_LIST_ALL_PAGES_WITH_TAGS_QUERY` (P2) — shared tags
- `wikijs_bulk_get_pages` (P1) — title resolution

---

## `wikijs_wiki_stats`

**Priority**: P4 | **File**: [`tools_pages.py` line 1862](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

Aggregate statistics dashboard for the entire wiki. Lightweight: no content reading.

### Why

At scale, the agent needs a quick "at a glance" overview: total pages, link density, orphan rate, tag counts. Informs high-level decisions before running detailed health checks.

### Signature

```python
wikijs_wiki_stats() -> str
```

### Design

- **60-second cache**: module-level `_stats_cache` dict with timestamp (line 1852)
- **Cache invalidation**: `_invalidate_stats_cache()` called on page create/update/delete
- **No content reading**: All data from BacklinkIndex + pages.list metadata

### Return

```json
{
  "total_pages": 234, "total_links": 1204,
  "orphan_count": 12, "orphan_rate": 0.051,
  "stale_count": 45, "avg_staleness_days": 23,
  "total_tags": 87, "unique_tags": 52, "pages_without_tags": 8,
  "most_linked": [{"pageId": 7, "title": "Auth", "inbound_links": 34}],
  "most_linking": [{"pageId": 1, "title": "Index", "outbound_links": 45}],
  "avg_links_per_page": 5.1
}
```

### wiki_stats vs wiki_health

| Aspect | wiki_stats (P4) | wiki_health (P3) |
|--------|----------------|-----------------|
| Purpose | Aggregate numbers | Actionable lists |
| Content reading | None | None |
| Output | "234 pages, 5% orphans" | "Here are the 12 orphan pages" |
| Caching | 60 seconds | None |
| Use case | Monitoring | Triage |

### Dependencies

- `BacklinkIndex` (P1) — for link counts, orphan count
- `_LIST_ALL_PAGES_WITH_TAGS_QUERY` — for metadata
