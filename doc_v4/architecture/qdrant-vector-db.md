# Qdrant Vector Database

v3 replaces the v2 embedded vector engine (sentence-transformers + SQLite PageVector) with a dedicated Qdrant vector database. Qdrant provides native KNN search, payload filtering, and multi-collection support.

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

### `wiki_pages`

Used by Wiki.js MCP for semantic search via `wikijs_smart_query`.

| Parameter | Value |
|-----------|-------|
| Vector size | 384 (all-MiniLM-L6-v2) |
| Distance | Cosine |
| On-disk payload | True |

**Payload per point:**

| Field | Type | Description |
|-------|------|-------------|
| `page_id` | integer | Wiki.js page ID |
| `title` | string | Page title |
| `path` | string | Wiki path (e.g. `docs/auth/overview`) |
| `locale` | string | Language code (`en`) |

### `documents`

Used by Ingestion Pipeline for ingested document chunks.

| Parameter | Value |
|-----------|-------|
| Vector size | 384 (all-MiniLM-L6-v2) |
| Distance | Cosine |
| On-disk payload | True |

**Payload per point:**

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | string | Unique document identifier |
| `chunk_index` | integer | Position within the document |
| `file_type` | string | Source file type (`pdf`, `docx`, `md`, etc.) |
| `source_path` | string | Original file path |
| `text` | string | Chunk text content |

## HNSW Configuration

Qdrant uses HNSW (Hierarchical Navigable Small World) for approximate nearest neighbor search:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `m` | 16 | Number of edges per node in the graph |
| `ef_construct` | 100 | Size of the dynamic candidate list during construction |
| `ef` | 100 | Size of the dynamic candidate list during search |

Default values work well for the current scale. Tune `ef` higher for more accurate results at the cost of search latency.

## Payload Indexes

Create payload indexes for filter performance before bulk ingestion:

```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://qdrant-db:6334")

client.create_payload_index(
    collection_name="documents",
    field_name="document_id",
    field_schema="keyword",
)
client.create_payload_index(
    collection_name="documents",
    field_name="file_type",
    field_schema="keyword",
)
```

## Backup and Restore

```bash
# Create snapshot
curl -X POST http://localhost:6334/collections/wiki_pages/snapshots

# List snapshots
curl http://localhost:6334/collections/wiki_pages/snapshots

# Snapshots are stored in the qdrant_snapshots volume
```

## Embedding Model

All services use `all-MiniLM-L6-v2` (SentenceTransformers):

- **Dimensions:** 384
- **Model size:** ~80 MB
- **Loading:** Lazy singleton in each service (Qdrant MCP, Ingestion Pipeline)
- **Consistency:** Same model across all services ensures consistent vector space

## Why External Qdrant

| v2 (Embedded) | v3 (External Qdrant) |
|---------------|---------------------|
| SQLite `PageVector` table | Dedicated vector database |
| Brute-force cosine similarity in Python | Native HNSW KNN search |
| Single collection (`page_vectors`) | Multi-collection (`wiki_pages`, `documents`) |
| No payload filtering | Rich payload filtering (keyword, range, geo) |
| 1 MCP server (wiki-mcp) | 3 services access Qdrant (wiki-mcp, qdrant-mcp, ingestion) |
| No snapshots/backup | Native snapshot API |
