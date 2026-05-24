# Quickstart

Get wiki-js-mcp v3 running in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- 8 GB RAM (for all 8 containers)
- ~5 GB disk space (images + models)

## 1. Clone and Configure

```bash
git clone <repo-url> && cd wiki-js-mcp
cp .env.example .env
```

Edit `.env` and set at minimum:
```ini
POSTGRES_PASSWORD=your_secure_password
```

Optional: customize ports and credentials.

## 2. Start the Stack

```bash
docker compose up -d
```

This starts 8 containers:
- `wikijs_db` — PostgreSQL 15 (alpine)
- `wikijs_app` — Wiki.js v2
- `wikijs_setup` — One-shot initial setup (runs once)
- `wikijs_mcp` — Wiki.js MCP server (:8000)
- `wikijs_qdrant` — Qdrant vector DB (REST :6334)
- `wikijs_qdrant_mcp` — Qdrant MCP server (:8001)
- `wikijs_ingestion` — Ingestion Pipeline (:8002)
- `wikijs_tesseract_mcp` — Tesseract OCR MCP (:8003)

First startup takes 5-10 minutes (model download). Subsequent starts are fast.

## 3. Verify

```bash
# Check all containers are healthy
docker compose ps

# Test MCP server endpoints
curl http://localhost:8000/sse   # Wiki.js MCP
curl http://localhost:8001/sse   # Qdrant MCP
curl http://localhost:8002/sse   # Ingestion Pipeline
curl http://localhost:8003/sse   # Tesseract MCP
```

## 4. Configure Cursor

Add to your Cursor `mcp.json`:

```json
{
  "mcpServers": {
    "wiki-js":     { "url": "http://localhost:8000/sse" },
    "qdrant":      { "url": "http://localhost:8001/sse" },
    "tesseract":   { "url": "http://localhost:8003/sse" },
    "ingestion":   { "url": "http://localhost:8002/sse" }
  }
}
```

## 5. Run Tests

```bash
# Fast tests (Qdrant only)
docker compose --profile test run --rm test-runner

# Full-stack tests
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/regression/ -v
```

## Next Steps

- [Docker Operations](docker-operations.md) — Build, debug, seed data
- [Multi-MCP Architecture](../architecture/multi-mcp-architecture.md) — Service design
- [Testing Guide](../reference/testing.md) — Full test documentation
- [MCP Servers](../mcp-servers/index.md) — Tool catalogs per server
