# Vector Engine Impact — Features to Revisit

Last updated: 2026-05-23

The vector search engine (P4-11) is now available: `wikijs_vector_search` and `wikijs_rebuild_vector_index`. This document tracks which existing and planned features can be enhanced now that semantic search is available.

## Already integrated

| Feature | Integration | Status |
|---------|------------|--------|
| `wikijs_smart_query` (P2) | Uses RRF to merge semantic + keyword results. `fallback_mode: "full"`. | Completed |

## Features to revisit

| Feature | Current state | Enhancement | Priority |
|---------|--------------|-------------|----------|
| `wikijs_get_affected_pages` (P4) | Planned — proactive impact analysis | Add `semantic_similar` field: pages with cosine similarity > 0.7 to the source page | High — core feature |
| `wikijs_wiki_health` (P3) | Planned — unified dashboard | Add `near_duplicates` check: pairs of pages with similarity > 0.9 (potential duplicates or redundant content) | Medium — quality improvement |
| `wikijs_search_pages` (existing) | Keyword-only via Wiki.js API | Consider adding `include_semantic` parameter for RRF merge, mirroring smart_query | Low — smart_query already covers this |
| `wikijs_get_page_stats` (P1) | Returns metadata | Add `semantic_cluster`: top-3 most similar pages | Low — nice-to-have |

## How to enhance a feature with vector search

1. Import helpers from `tools_pages`: `_get_model`, `_compute_embedding`, `_cosine_similarity`
2. Query `PageVector` table from `db.py`
3. Compute cosine similarity between the query/target vector and all indexed vectors
4. Filter/sort by similarity threshold

Example for `affected_pages`:
```python
# After finding direct backlinks, add semantic neighbors
db = get_db()
try:
    all_vectors = db.query(PageVector).all()
finally:
    db.close()

target_vec = json.loads(target_row.vector_json) if target_row else None
similar = []
if target_vec:
    for row in all_vectors:
        if row.page_id == source_id:
            continue
        vec = json.loads(row.vector_json)
        sim = _cosine_similarity(target_vec, vec)
        if sim > 0.7:
            similar.append({"pageId": row.page_id, "similarity": round(sim, 4)})
    similar.sort(key=lambda x: x["similarity"], reverse=True)
```

## Technical notes

- Embedding model: `all-MiniLM-L6-v2` (384 dimensions)
- Vector storage: `PageVector` table (SQLite, JSON text column)
- Similarity metric: Cosine similarity (pure Python, ~0.003ms per comparison)
- Model loading: Lazy singleton, ~80MB memory, ~2s cold start
- No sqlite-vec dependency (pre-v1 alpha, arm64 Docker issues)
