# Multi-MCP Setup

Configure Cursor IDE to connect to all 4 MCP servers in the v3 ecosystem.

## Cursor Configuration

Add to your Cursor `mcp.json`:

```json
{
  "mcpServers": {
    "wiki-js": {
      "url": "http://localhost:8000/sse"
    },
    "qdrant": {
      "url": "http://localhost:8001/sse"
    },
    "tesseract": {
      "url": "http://localhost:8003/sse"
    },
    "ingestion": {
      "url": "http://localhost:8002/sse"
    }
  }
}
```

## Prerequisites

The full 8-container stack must be running:

```bash
docker compose up -d
```

## Verify Connections

```bash
# Check all containers are healthy
docker compose ps

# Test MCP server SSE endpoints
curl http://localhost:8000/sse   # Wiki.js MCP (~43 tools)
curl http://localhost:8001/sse   # Qdrant MCP (8 tools)
curl http://localhost:8002/sse   # Ingestion Pipeline (7 tools)
curl http://localhost:8003/sse   # Tesseract MCP (7 tools)
```

## Tool Discovery

After configuring Cursor, the LLM agent can discover all ~65 tools across 4 servers:

| Server | Port | Tools | Primary Capability |
|--------|------|-------|-------------------|
| wiki-js | 8000 | ~43 | Wiki.js CRUD, search, graph, health |
| qdrant | 8001 | 8 | Vector search, collection management |
| ingestion | 8002 | 7 | Document processing, OCR, chunking |
| tesseract | 8003 | 7 | On-demand OCR, document classification |

## Using Tools Together

The agent can chain tools across servers:

```
1. ingest_document (ingestion :8002)  -- process report.pdf into Qdrant
2. qdrant_search (qdrant :8001)      -- find relevant chunks
3. wikijs_create_page (wiki-js :8000) -- create wiki page from chunks
4. wikijs_smart_query (wiki-js :8000) -- find related wiki pages
```

## Troubleshooting

### Server not responding

```bash
# Check container health
docker compose ps

# View server logs
docker compose logs wiki-js-mcp
docker compose logs qdrant-mcp
docker compose logs ingestion-pipeline
docker compose logs tesseract-mcp

# Restart a specific server
docker compose restart qdrant-mcp
```

### Connection refused in Cursor

1. Verify the Docker stack is running: `docker compose ps`
2. Verify the port is not blocked: `curl http://localhost:8000/sse`
3. Check the URL in `mcp.json` matches the `MCP_PORT` in `.env` (default 8000)

### Multiple Cursor instances

Each Cursor instance connects independently to the SSE endpoints. The MCP servers handle concurrent connections. No special configuration needed.
