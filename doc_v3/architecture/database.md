# Database

v3 uses a hybrid storage architecture: **Qdrant** for vector embeddings and **SQLite** for relational metadata (file mappings, backlinks, ingestion tracking). The v2 `PageVector` model has been removed.

## Storage Overview

| Store | Engine | Purpose | Models |
|-------|--------|---------|--------|
| Qdrant | Vector DB (v1.17) | Semantic search embeddings | `wiki_pages`, `documents` collections |
| SQLite (Wiki.js MCP) | SQLAlchemy 2.x | File mappings, backlinks | `FileMapping`, `BacklinkIndex`, `RepositoryContext` |
| SQLite (Ingestion) | SQLAlchemy 2.x | Document tracking | `IngestedDocument`, `DocumentChunk`, `PageChunkReference` |

## Qdrant Collections

See [Qdrant Vector DB](qdrant-vector-db.md) for full schema details.

### `wiki_pages`

Used by Wiki.js MCP for `wikijs_smart_query` semantic search. Payload: `page_id`, `title`, `path`, `locale`.

### `documents`

Used by Ingestion Pipeline for document chunks. Payload: `document_id`, `chunk_index`, `file_type`, `source_path`, `text`.

## SQLite — Wiki.js MCP

### FileMapping

[`mcp-servers/wiki-js-mcp/src/wiki_mcp_server/db.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/db.py)

Maps local file paths to Wiki.js page IDs. Used by file integration tools (`tools_files.py`).

| Column | Type | Purpose |
|--------|------|---------|
| `file_path` | String, unique | Absolute path to the source file |
| `page_id` | Integer | Wiki.js page ID |
| `relationship_type` | String | Type of relationship (e.g. "documents") |
| `file_hash` | String | SHA-256 of file content for change detection |
| `repository_root` | String | Git repo root path |
| `space_name` | String | Wiki.js space grouping |

### BacklinkIndex

Stores cross-reference links between wiki pages. Populated by extracting markdown `[text](path)` links from page content. Used by backlinks, link graph, health, and affected pages tools.

| Column | Type | Purpose |
|--------|------|---------|
| `source_page_id` | Integer | Page that contains the link |
| `target_page_id` | Integer, nullable | Page being linked to (resolved via GraphQL) |
| `target_path` | String | Raw path from markdown link |
| `link_text` | String | Display text from `[text](path)` |
| `position` | Integer | Character offset in source content |

**Maintenance:** Updated incrementally via `_sync_backlinks_for_page()` after page create/update. Full rebuild via `wikijs_rebuild_backlink_index()`.

### RepositoryContext

Tracks which Git repository maps to which wiki space.

| Column | Type | Purpose |
|--------|------|---------|
| `root_path` | String, unique | Repository root directory |
| `space_name` | String | Wiki.js space name |
| `space_id` | Integer | Wiki.js space identifier |

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

## v2 vs v3 Changes

| Aspect | v2 | v3 |
|--------|----|----|
| Vector storage | SQLite `PageVector` (JSON text column) | Qdrant `wiki_pages` collection (native vectors) |
| Vector search | Brute-force cosine similarity in Python | Qdrant HNSW KNN search |
| Embedding model | In-process (sentence-transformers in wiki-mcp) | In-process (Qdrant MCP + Ingestion Pipeline) |
| Backlinks | SQLite `BacklinkIndex` (unchanged) | SQLite `BacklinkIndex` (unchanged) |
| File mappings | SQLite `FileMapping` (unchanged) | SQLite `FileMapping` (unchanged) |

## Session Pattern

All SQLite access follows the same pattern (unchanged from v2):

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

- `autocommit=False`, `autoflush=False` -- explicit transaction control
- Sessions are per-operation, NOT per-request
- `db.close()` in `finally` guarantees no connection leaks

## SQLite Performance

BacklinkIndex now has explicit indexes on `source_page_id` and `target_page_id` to optimize BFS graph traversal and backlink lookups:

```python
Index('idx_backlinks_source', BacklinkIndex.source_page_id)
Index('idx_backlinks_target', BacklinkIndex.target_page_id)
```

These are defined via `__table_args__` on the `BacklinkIndex` model and auto-created on startup by `Base.metadata.create_all(engine)`. For the current scale (~200 pages, ~1000 edges), full table scans are fast enough, but these indexes become important at 1000+ pages.
