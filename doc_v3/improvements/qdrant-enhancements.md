# Qdrant Enhancements — Features to Revisit

The v3 Qdrant vector database replaces the v2 embedded vector engine (`PageVector`, `wikijs_vector_search`). This document tracks which existing features can be enhanced with semantic search via Qdrant.

## Already integrated

| Feature | Integration |
|---------|------------|
| `wikijs_smart_query` (P2) | RRF merge of Qdrant semantic + Wiki.js keyword. `fallback_mode: "full"` when collection populated |
| `wikijs_get_affected_pages` (P4) | Semantic similarity signal (weight 0.6, threshold > 0.7) via `QdrantClient.query_points` |

## Features to revisit

| Feature | Enhancement | Priority |
|---------|-------------|----------|
| **`wikijs_wiki_health` (P3)** | Add `near_duplicates` check: pairs of pages with Qdrant similarity > 0.9. Potential duplicates or redundant content | Medium |
| **`wikijs_search_pages` (existing)** | Add `include_semantic` parameter for RRF merge, mirroring `smart_query` | Low |
| **`wikijs_get_page_stats` (P1)** | Add `semantic_cluster`: top-3 most similar pages via Qdrant | Low |

## How to enhance

1. Use `QdrantClient` with `settings.QDRANT_URL` and `settings.QDRANT_COLLECTION_WIKI_PAGES`
2. Embed text with `SentenceTransformer("all-MiniLM-L6-v2")` (same model as smart_query)
3. Query via `client.query_points()` with `score_threshold` for filtering
4. For batch comparisons (near_duplicates), use `qdrant_scroll` to iterate all points or maintain a similarity matrix for small wikis

### Example: near_duplicates check for `wiki_health`

```python
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

client = QdrantClient(url=settings.QDRANT_URL)
collection = settings.QDRANT_COLLECTION_WIKI_PAGES

# Scroll all wiki page vectors
points, _ = client.scroll(collection_name=collection, limit=500, with_vectors=True)

duplicates = []
for i, point_a in enumerate(points):
    for point_b in points[i + 1:]:
        sim = cosine_similarity(point_a.vector, point_b.vector)
        if sim > 0.9:
            duplicates.append({
                "pageA": point_a.payload.get("page_id"),
                "pageB": point_b.payload.get("page_id"),
                "similarity": round(sim, 4),
            })
```

Alternatively, use `qdrant_search` MCP tool with each page's content as query and filter results above 0.9 (excluding self-match).

## Technical context (v3)

- **Embedding model**: `all-MiniLM-L6-v2` (384 dimensions)
- **Vector storage**: Qdrant `wiki_pages` collection (not SQLite)
- **Similarity metric**: Cosine (Qdrant default for normalized embeddings)
- **Indexing**: Explicit via `qdrant_upsert_chunks` — not automatic on page write
- **Document vectors**: Separate `documents` collection via Ingestion Pipeline

## v2 tools removed

| v2 Tool | v3 Replacement |
|---------|----------------|
| `wikijs_vector_search` | `wikijs_smart_query` or `qdrant_search` |
| `wikijs_rebuild_vector_index` | `qdrant_upsert_chunks` batch indexing |
| `PageVector` SQLite model | Qdrant collection |

See [P4 — Scale](../features/p4-scale.md) and [Qdrant Vector DB](../architecture/qdrant-vector-db.md).
