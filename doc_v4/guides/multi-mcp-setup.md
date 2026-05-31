# Multi-MCP Setup

Configure Cursor IDE to connect to all 4 MCP servers in the v4 ecosystem.

## Cursor Configuration

Add to your Cursor `mcp.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "type": "sse",
      "url": "http://localhost:8001/sse"
    },
    "ingestion": {
      "type": "sse",
      "url": "http://localhost:8002/sse"
    },
    "tesseract": {
      "type": "sse",
      "url": "http://localhost:8003/sse"
    },
    "enrichment": {
      "type": "sse",
      "url": "http://localhost:8004/sse"
    }
  }
}
```

## Prerequisites

The full 5-container stack must be running:

```bash
docker compose up -d
```

## Verify Connections

```bash
# Check all containers are healthy
docker compose ps

# Test MCP server SSE endpoints (HTTP status check)
curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/sse && echo " OK"  # Qdrant MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:8002/sse && echo " OK"  # Ingestion Pipeline
curl -s -o /dev/null -w '%{http_code}' http://localhost:8003/sse && echo " OK"  # Tesseract MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:8004/sse && echo " OK"  # Enrichment Pipeline
```

## Tool Discovery

After configuring Cursor, the LLM agent can discover all 26 tools across 4 servers:

| Server | Port | Tools | Primary Capability |
|--------|------|-------|-------------------|
| qdrant | 8001 | 8 | Vector search, collection management |
| ingestion | 8002 | 7 | Document processing, OCR, chunking |
| tesseract | 8003 | 7 | On-demand OCR, document classification |
| enrichment | 8004 | 4 | Post-ingestion enrichment via LangGraph |

## Using Tools Together

The agent can chain tools across servers:

```
1. ingest_document (ingestion :8002)     -- process report.pdf into Qdrant
2. qdrant_search (qdrant :8001)         -- find relevant chunks
3. enrich_document (enrichment :8004)    -- enrich payload with classification
4. qdrant_search with filters            -- filtered retrieval
```

## Troubleshooting

### Server not responding

```bash
# Check container health
docker compose ps

# View server logs
docker compose logs qdrant-mcp
docker compose logs ingestion-pipeline
docker compose logs tesseract-mcp
docker compose logs enrichment-pipeline

# Restart a specific server
docker compose restart qdrant-mcp
```

### Connection refused in Cursor

1. Verify the Docker stack is running: `docker compose ps`
2. Verify the port is not blocked: `curl http://localhost:8001/sse`
3. Check the URL in `mcp.json` matches the `MCP_PORT` in `.env` (default 8001-8004)

### Multiple Cursor instances

Each Cursor instance connects independently to the SSE endpoints. The MCP servers handle concurrent connections. No special configuration needed.
