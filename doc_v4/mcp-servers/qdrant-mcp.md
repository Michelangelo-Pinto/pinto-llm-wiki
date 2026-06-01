# Qdrant MCP Server

*Container: `pinto_llm_qdrant_mcp` | Port: `8001` | Transport: SSE | Tools: 8*

MCP server wrapping Qdrant vector database REST API. Replaces the v2 embedded vector engine (sentence-transformers + SQLite PageVector).

## Container

```yaml
qdrant-mcp:
  build: ./mcp-servers/qdrant-mcp
  image: pinto-llm-qdrant-mcp:latest
  ports: ["8001:8001"]
  depends_on: [qdrant-db:healthy]
  environment:
    QDRANT_URL: http://qdrant-db:6334
```

## Tool Catalog

| # | Tool | Purpose |
|---|------|---------|
| 1 | `qdrant_create_collection` | Create a new vector collection |
| 2 | `qdrant_list_collections` | List all collections |
| 3 | `qdrant_collection_info` | Get collection details and stats |
| 4 | `qdrant_delete_collection` | Delete an entire collection |
| 5 | `qdrant_search` | Semantic search with optional payload filters |
| 6 | `qdrant_upsert_chunks` | Insert or update vector points with payload |
| 7 | `qdrant_delete_by_filter` | Delete points matching payload filters |
| 8 | `qdrant_scroll` | Paginate through all points |

## Collection Schema

See [Qdrant Vector DB Architecture](../architecture/qdrant-vector-db.md) for full schema details (vector size, distance, HNSW, backup).

### Payload Indexes

Create before bulk ingestion for filter performance:

```python
client.create_payload_index("documents", "document_id", "keyword")
client.create_payload_index("documents", "file_type", "keyword")
client.create_payload_index("documents", "source_file", "keyword")
client.create_payload_index("documents", "chunk_index", "integer")
```

## Cross-References

- [Qdrant Vector DB Architecture](../architecture/qdrant-vector-db.md)
- [MCP Server Registry](../architecture/mcp-server-registry.md)
- [Config Reference](../reference/config.md)
