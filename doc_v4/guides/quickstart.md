# Quickstart

Get wiki-js-mcp v4 running in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- 4 GB RAM (for all 5 containers)
- ~3 GB disk space (images + models)
- (Optional) `OPENAI_API_KEY` for enrichment pipeline LLM features

## 1. Clone and Configure

```bash
git clone https://github.com/mikep/wiki-js-mcp.git
cd wiki-js-mcp
cp .env.example .env
```

Edit `.env` and set at minimum:
```ini
OPENAI_API_KEY=sk-...        # Required for enrichment LLM classification
```

Optional: customize ports. See [Configuration Reference](../reference/config.md) for all environment variables.

## 2. Start the Stack

```bash
docker compose up -d
```

This starts 5 containers:
- `wikijs_qdrant` — Qdrant vector DB (REST :6334, gRPC :6333)
- `wikijs_qdrant_mcp` — Qdrant MCP server (:8001)
- `wikijs_ingestion` — Ingestion Pipeline (:8002)
- `wikijs_tesseract_mcp` — Tesseract OCR MCP (:8003)
- `wikijs_enrichment` — Enrichment Pipeline (:8004)

First startup takes 5-10 minutes (image build with pre-downloaded models). Subsequent starts are fast.

## 3. Verify

```bash
# Check all containers are healthy
docker compose ps

# Test MCP server endpoints (HTTP status check)
curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/sse && echo " OK"  # Qdrant MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:8002/sse && echo " OK"  # Ingestion Pipeline
curl -s -o /dev/null -w '%{http_code}' http://localhost:8003/sse && echo " OK"  # Tesseract MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:8004/sse && echo " OK"  # Enrichment Pipeline
```

## 4. Configure Cursor

Add to your Cursor `mcp.json`:

```json
{
  "mcpServers": {
    "qdrant":     { "type": "sse", "url": "http://localhost:8001/sse" },
    "ingestion":  { "type": "sse", "url": "http://localhost:8002/sse" },
    "tesseract":  { "type": "sse", "url": "http://localhost:8003/sse" },
    "enrichment": { "type": "sse", "url": "http://localhost:8004/sse" }
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

- [Stack Lifecycle Guide](stack-lifecycle.md) — Build, start, stop, rebuild
- [LLM Wiki Workflows](llm-wiki-workflows.md) — Core operating patterns
- [Agent Orientation](agent-orientation.md) — How to instruct the LLM agent
- [Tool Catalog](../reference/tool-catalog.md) — All 26 tools with signatures
- [System Overview](../architecture/system-overview.md) — Architecture and data flow

---

## 6. First End-to-End Flow

Once the stack is running and tests pass, try this complete workflow.

### Ingest a document

Copy a file into the shared volume and process it:

```bash
# Copy a file to the to_ingest/ directory (bind-mounted to /data/shared)
cp /path/to/your/document.pdf to_ingest/
```

Then tell the agent in Cursor:

```
1. ingest_detect_type("/data/shared/document.pdf") — check file type
2. ingest_document("/data/shared/document.pdf") — full pipeline
3. ingest_get_status(document_id) — verify completion
```

### Search ingested content

```
qdrant_search(collection="documents", query_text="your topic", limit=10)
```

### Create a knowledge page from ingested content

```
1. ingest_search_chunks(query="summary", limit=3)
2. Write knowledge/ingested/YYYY-MM-DD-slug/page.md with frontmatter
3. Update knowledge/ingested/index.md
```

### Run enrichment (optional)

```
enrich_get_config() — check if enrichment is enabled
enrich_document(document_id="...") — run enrichment manually
enrich_get_status(document_id="...") — check results
```

### Verify with tests

```bash
# Fast tests (no full stack needed beyond Qdrant)
docker compose --profile test run --rm test-runner

# Full stack tests
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/regression/ -v
```
