# Configuration Reference

Environment variables and Docker profiles for wiki-js-mcp v3.

## Environment Variables

### PostgreSQL (Wiki.js backend)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `wikijs` | PostgreSQL database name |
| `POSTGRES_USER` | `wikijs` | PostgreSQL user |
| `POSTGRES_PASSWORD` | *(required)* | PostgreSQL password |

### Ports

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKIJS_PORT` | `3000` | Wiki.js web UI |
| `MCP_PORT` | `8000` | Wiki.js MCP server |
| `QDRANT_GRPC_PORT` | `6333` | Qdrant gRPC API |
| `QDRANT_REST_PORT` | `6334` | Qdrant REST API |
| `QDRANT_MCP_PORT` | `8001` | Qdrant MCP server |
| `INGESTION_MCP_PORT` | `8002` | Ingestion Pipeline MCP |
| `TESSERACT_MCP_PORT` | `8003` | Tesseract MCP server |

### Qdrant

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant-db:6334` | Qdrant REST endpoint (used by wiki-js-mcp, qdrant-mcp, ingestion-pipeline; NOT by tesseract-mcp) |
| `QDRANT_COLLECTION_WIKI_PAGES` | `wiki_pages` | Collection for wiki page vectors |
| `QDRANT_COLLECTION_DOCUMENTS` | `documents` | Collection for ingested documents |

### Wiki.js Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKIJS_SITE_URL` | `http://localhost:3000` | Wiki.js site URL (auto-setup) |
| `WIKIJS_API_URL` | `http://wiki:3000` | Wiki.js API URL (inside compose network) |
| `WIKIJS_USERNAME` | *(empty)* | Admin username (set in `.env` for MCP authentication) |
| `WIKIJS_PASSWORD` | *(empty)* | Admin password (set in `.env` for MCP authentication) |
| `WIKIJS_API_KEY` | *(empty)* | Wiki.js API key (alternative to username/password) |
| `WIKIJS_TOKEN` | *(empty)* | JWT token (auto-generated after authentication) |

### MCP Server (internal)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | MCP server bind address |
| `MCP_TRANSPORT` | `sse` | Transport protocol (SSE) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `/logs/wikijs_mcp.log` | Log file path (wiki-js-mcp) |
| `WIKIJS_MCP_DB` | `/data/wikijs_mappings.db` | SQLite database path (wiki-js-mcp) |
| `INGESTION_DB` | `/data/ingestion.db` | SQLite database path (ingestion-pipeline) |
| `TESSDATA_PREFIX` | `/usr/share/tesseract-ocr/5/tessdata` | Tesseract language data path |

### Test Runner (set in docker-compose service)

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant-db:6334` | Qdrant REST endpoint |
| `QDRANT_MCP_URL` | `http://qdrant-mcp:8001` | Qdrant MCP server URL |
| `INGESTION_MCP_URL` | `http://ingestion-pipeline:8002` | Ingestion MCP URL |
| `TESSERACT_MCP_URL` | `http://tesseract-mcp:8003` | Tesseract MCP URL |
| `WIKIJS_MCP_URL` | `http://wiki-js-mcp:8000` | Wiki.js MCP URL |
| `WIKIJS_API_URL` | `http://wiki:3000` | Wiki.js API URL |

## Docker Compose Profiles

### Default services (always running)

```
db → wiki → setup → wiki-js-mcp
                      qdrant-db → qdrant-mcp
                                → ingestion-pipeline
                      tesseract-mcp
```

### `test` profile

Adds `test-runner` with only `qdrant-db` dependency. Used for fast Qdrant/E2E/performance tests.

```bash
docker compose --profile test run --rm test-runner pytest tests/ -v
```

### `integration` profile

Same `test-runner` service, but intended to run against the full stack (start `docker compose up -d` first).

```bash
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/regression/ -v
```
