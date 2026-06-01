# Multi-MCP Setup

Configure Cursor IDE to connect to all 3 MCP servers in the v4 ecosystem.

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
    }
  }
}
```

## Prerequisites

The full 4-container stack must be running:

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
```

## Tool Discovery

After configuring Cursor, the LLM agent can discover all 22 tools across 3 servers:

| Server | Port | Tools | Primary Capability |
|--------|------|-------|-------------------|
| qdrant | 8001 | 8 | Vector search, collection management |
| ingestion | 8002 | 7 | Document processing, OCR, chunking |
| tesseract | 8003 | 7 | OCR, text extraction, preprocessing |

## Troubleshooting

If Cursor doesn't discover the servers:

1. Verify containers are running: `docker compose ps`
2. Test SSE endpoints directly (see curl commands above)
3. Check `mcp.json` URLs match exactly
4. Restart Cursor after any config change
5. Check Cursor Developer Tools Console for MCP errors

## Related Documents

- [Quickstart](quickstart.md) — First-time setup
- [Stack Lifecycle Guide](stack-lifecycle.md) — Start/stop/rebuild
- [Troubleshooting](troubleshooting.md) — Connection issues
