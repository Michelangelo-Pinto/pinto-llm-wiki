# Database

v4 uses a hybrid storage architecture: **Qdrant** for vector embeddings and **SQLite** for ingestion tracking. Wiki.js and its SQLite mappings were removed in v4.

## Storage Overview

| Store | Engine | Purpose | Models |
|-------|--------|---------|--------|
| Qdrant | Vector DB (v1.17) | Semantic search embeddings | `documents` collection |
| SQLite (Ingestion) | SQLAlchemy 2.x | Document tracking | `IngestedDocument`, `DocumentChunk`, `PageChunkReference` |

## Qdrant Collections

See [Qdrant Vector DB](qdrant-vector-db.md) for full schema details (vector size, distance, payload fields, HNSW config, backup).

### `documents`

Used by Ingestion Pipeline for document chunks. Payload: `document_id`, `chunk_index`, `file_type`, `source_path`, `text`.

## SQLite — Ingestion Pipeline

### IngestedDocument

[`mcp-servers/ingestion-pipeline/src/ingestion_pipeline/db.py`](../../mcp-servers/ingestion-pipeline/src/ingestion_pipeline/db.py)

Tracks each ingested file.

| Column | Type | Purpose |
|--------|------|---------|
| `document_id` | String, unique | UUID for the document |
| `source_path` | String | Original file path |
| `file_type` | String | Detected file type |
| `content_hash` | String | SHA-256 for idempotency |
| `chunk_count` | Integer | Number of chunks created |
| `status` | String | `completed`, `processing`, `failed` |

### DocumentChunk

Chunks within an ingested document.

| Column | Type | Purpose |
|--------|------|---------|
| `chunk_id` | String, unique | UUID for the chunk |
| `document_id` | String | Foreign key to IngestedDocument |
| `chunk_index` | Integer | Position within document |
| `text` | Text | Chunk content |
| `qpoint_id` | String | Corresponding Qdrant point ID |

### PageChunkReference

Tracks which knowledge files reference ingested chunks.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | Integer, PK | Auto-increment |
| `file_path` | String | Path to knowledge/ MD file |
| `chunk_id` | Integer FK | → `document_chunks.id` |
| `document_id` | String | Redundant FK for queries |
| `linked_at` | DateTime | Link timestamp |

## Session Pattern

All SQLite access follows the same pattern:

```python
db = get_db()
try:
    rows = db.query(Model).filter(...).all()
    db.commit()           # Only for writes
except Exception as e:
    logger.warning("...")
    db.rollback()
finally:
    db.close()            # ALWAYS present
```

- `autocommit=False`, `autoflush=False` — explicit transaction control
- Sessions are per-operation, NOT per-request
- `db.close()` in `finally` guarantees no connection leaks

## v3 vs v4 Changes

| Aspect | v3 | v4 |
|--------|----|----|
| Vector storage | Qdrant `wiki_pages` + `documents` | Qdrant `documents` only |
| Wiki.js MCP DB | SQLite `pinto_llm_mappings.db` (FileMapping, BacklinkIndex, RepositoryContext) | Removed |
| Ingestion DB | SQLite `ingestion.db` | SQLite `ingestion.db` (unchanged) |
| Knowledge store | Wiki.js + PostgreSQL | File-system `knowledge/` |
