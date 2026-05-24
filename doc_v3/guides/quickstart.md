# Quickstart

Get wiki-js-mcp v3 running in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- 8 GB RAM (for all 8 containers)
- ~5 GB disk space (images + models)

## 1. Clone and Configure

```bash
git clone https://github.com/mikep/wiki-js-mcp.git
cd wiki-js-mcp
cp .env.example .env
```

Edit `.env` and set at minimum:
```ini
POSTGRES_PASSWORD=your_secure_password
```

Optional: customize ports and credentials. See [Configuration Reference](../reference/config.md) for all environment variables.

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

---

## 6. First End-to-End Flow

Once the stack is running and tests pass, try this complete workflow to verify everything works.

### Seed test data

Populate Wiki.js with sample pages (cross-referenced for backlinks and graph testing):

```bash
docker compose exec wiki-js-mcp python3 scripts/seed_wiki_docs.py
```

This creates ~20 wiki pages with tags, links, and a hierarchy.

### Ingest a document

Copy a PDF into the shared volume and process it:

```bash
# Copy a PDF to the container
docker compose cp /path/to/your/document.pdf ingestion-pipeline:/data/shared/doc.pdf

# Ingest it via the ingestion pipeline
curl -X POST http://localhost:8002/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ingest_document","arguments":{"file_path":"/data/shared/doc.pdf"}},"id":1}'
```

Expected response: `{"status": "completed", "chunks_created": N, "file_type": "...", "document_id": "..."}`

### Search the wiki

Use Cursor (the agent) or curl to run a smart query:

```
# Tell the agent in Cursor:
wikijs_smart_query("getting started")
```

Or via curl:

```bash
curl -X POST http://localhost:8000/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"wikijs_smart_query","arguments":{"query":"getting started","limit":5}},"id":1}'
```

### Create a page from ingested content

After ingestion, search the ingested chunks and create a wiki page:

```
# Tell the agent:
1. ingest_search_chunks(query="summary", limit=3)
2. wikijs_create_page(title="From: doc.pdf", content=<chunks concatenated>)
```

### Export the wiki

```bash
# The agent runs: wikijs_export_wiki("/data/shared/wiki-export")
# Extract to your host:
docker compose cp wiki-js-mcp:/data/shared/wiki-export ./wiki-export
ls ./wiki-export/
```

### Import edited pages back

```bash
# Edit files in ./wiki-export/ locally

# Copy back to container
docker compose cp ./wiki-export wiki-js-mcp:/data/shared/wiki-export

# The agent runs:
# wikijs_import_directory("/data/shared/wiki-export", update_existing=True)
```

### Verify with tests

```bash
# Fast tests (no full stack needed beyond Qdrant)
docker compose --profile test run --rm test-runner

# Full stack tests
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/regression/ -v

# SSE smoke tests
docker compose --profile integration run --rm test-runner \
  pytest tests/smoke/ -v -m smoke
```
