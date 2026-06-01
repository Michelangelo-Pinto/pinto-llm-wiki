# Qdrant Vector Database

v4 uses Qdrant as the vector database for semantic search. Qdrant provides native KNN search, payload filtering, and multi-collection support. The embedded vector engine from v2 (sentence-transformers + SQLite PageVector) has been replaced.

## Container

```yaml
qdrant-db:
  image: qdrant/qdrant:v1.17.1
  container_name: wikijs_qdrant
  ports:
    - "6333:6333"   # gRPC
    - "6334:6334"   # REST
  environment:
    QDRANT__SERVICE__GRPC_PORT: 6333
    QDRANT__SERVICE__HTTP_PORT: 6334
    QDRANT__STORAGE__ON_DISK_PAYLOAD: "true"
  volumes:
    - qdrant_data:/qdrant/storage
    - qdrant_snapshots:/qdrant/snapshots
```

**Note:** All MCP servers and the test-runner connect to Qdrant via the REST API at `http://qdrant-db:6334`. The gRPC port (`:6333`) is used only for the Docker healthcheck.

## Collections

### `documents`

Used by Ingestion Pipeline for ingested document chunks. This is the primary collection for semantic search in v4.

| Parameter | Value |
|-----------|-------|
| Vector size | 384 (all-MiniLM-L6-v2) |
| Distance | Cosine |
| On-disk payload | True |

**Payload per point:**

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | string | Unique document identifier |
| `chunk_index` | integer | Position within document |
| `source_file` | string | Original file path |
| `file_type` | string | Detected file type (pdf, docx, md, etc.) |
| `text` | string | Full chunk text |
| `content_hash` | string | SHA-256 of document content (idempotency) |

## Embedding Model

**all-MiniLM-L6-v2** from SentenceTransformers.

| Property | Value |
|----------|-------|
| Dimensions | 384 |
| Model size | ~80 MB |
| Normalization | L2 (cosine distance) |
| Pre-loaded | Yes (Docker build time) |
| Used by | Qdrant MCP, Ingestion Pipeline |

## HNSW Configuration

Qdrant uses HNSW (Hierarchical Navigable Small World) index for approximate KNN:

- `m`: 16 (number of edges per node)
- `ef_construct`: 100 (build-time search width)
- `ef`: 128 (query-time search width)

These are Qdrant defaults and perform well for the current scale. Tuning may be needed for 1M+ vectors.

## Backup

Qdrant supports snapshot backups:

```bash
# Create a snapshot
curl -X POST http://localhost:6334/collections/documents/snapshots

# List snapshots
curl http://localhost:6334/collections/documents/snapshots

# Download a snapshot
curl http://localhost:6334/collections/documents/snapshots/<snapshot_name> -o backup.snapshot
```

Docker volume: `qdrant_snapshots` is mounted at `/qdrant/snapshots` for snapshot storage.

## v3 vs v4 Changes

| Aspect | v3 | v4 |
|--------|----|----|
| Collections | `wiki_pages` + `documents` | `documents` only |
| Embedding model | all-MiniLM-L6-v2 | all-MiniLM-L6-v2 (unchanged) |
| Vector dimensions | 384 | 384 (unchanged) |
| Distance | Cosine | Cosine (unchanged) |
| Services accessing Qdrant | wiki-mcp, qdrant-mcp, ingestion | qdrant-mcp, ingestion |
| `wiki_pages` collection | Used by Wiki.js MCP for page semantic search | Removed in v4 |

## Related Documents

- [Database](database.md) — Full storage overview (Qdrant + SQLite)
- [Ingestion Pipeline Design](ingestion-pipeline-design.md) — How documents are chunked and embedded
- [System Overview](system-overview.md) — Container topology
