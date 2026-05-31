# Configuration Reference

Environment variables and Docker profiles for wiki-js-mcp v4.

## Environment Variables

### Ports

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_GRPC_PORT` | `6333` | Qdrant gRPC API |
| `QDRANT_REST_PORT` | `6334` | Qdrant REST API |
| `QDRANT_MCP_PORT` | `8001` | Qdrant MCP server |
| `INGESTION_MCP_PORT` | `8002` | Ingestion Pipeline MCP |
| `TESSERACT_MCP_PORT` | `8003` | Tesseract MCP server |
| `ENRICHMENT_MCP_PORT` | `8004` | Enrichment Pipeline MCP |

### Qdrant

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant-db:6334` | Qdrant REST endpoint (used by qdrant-mcp, ingestion-pipeline, enrichment-pipeline) |
| `QDRANT_COLLECTION_DOCUMENTS` | `documents` | Collection for ingested documents |

### MCP Server (internal)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | MCP server bind address |
| `MCP_TRANSPORT` | `sse` | Transport protocol (SSE) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `INGESTION_DB` | `/data/ingestion.db` | SQLite database path (ingestion-pipeline) |
| `ENRICHMENT_DB` | `/data/enrichment.db` | SQLite database path (enrichment-pipeline) |
| `ENRICHMENT_CONFIG_PATH` | `/app/knowledge/enrichment-config.md` | Enrichment config file path |
| `TESSDATA_PREFIX` | `/usr/share/tesseract-ocr/5/tessdata` | Tesseract language data path |

### Enrichment Pipeline

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(optional)* | OpenAI API key for LLM classification and reference extraction. Without it, enrichment uses heuristic fallbacks |

### Test Runner (set in docker-compose service)

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant-db:6334` | Qdrant REST endpoint |
| `QDRANT_MCP_URL` | `http://qdrant-mcp:8001` | Qdrant MCP server URL |
| `INGESTION_MCP_URL` | `http://ingestion-pipeline:8002` | Ingestion MCP URL |
| `TESSERACT_MCP_URL` | `http://tesseract-mcp:8003` | Tesseract MCP URL |
| `ENRICHMENT_MCP_URL` | `http://enrichment-pipeline:8004` | Enrichment MCP URL |

## Docker Compose Profiles

### Default services (always running)

```
qdrant-db → qdrant-mcp
          → ingestion-pipeline
          → enrichment-pipeline
tesseract-mcp (independent)
```

### `test` profile

Adds `test-runner` container. Runs fast tests (Qdrant integration + E2E + performance) against only `qdrant-db`:

```bash
docker compose --profile test run --rm test-runner
```

### `integration` profile

Adds `test-runner` container. Runs full-stack integration tests against all 5 containers:

```bash
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ -v
```

## Related Documents

- [Quickstart](../guides/quickstart.md) — First-time setup
- [Stack Lifecycle](../guides/stack-lifecycle.md) — Build, start, stop commands
- [Enrichment Config](../../knowledge/enrichment-config.md) — Enrichment toggle and LLM parameters
- [Tool Catalog](tool-catalog.md) — All 26 tools with signatures
