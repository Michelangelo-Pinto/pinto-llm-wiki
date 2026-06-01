# Quickstart

Get wiki-js-mcp v4 running in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- 4 GB RAM (for all 4 containers)
- ~3 GB disk space (images + models)

## 1. Clone and Configure

```bash
git clone https://github.com/mikep/wiki-js-mcp.git
cd wiki-js-mcp
cp .env.example .env
```

Optional: customize ports. See [Configuration Reference](../reference/config.md) for all environment variables.

## 2. Start the Stack

```bash
docker compose up -d
```

This starts 4 containers:
- `wikijs_qdrant` — Qdrant vector DB (REST :6334, gRPC :6333)
- `wikijs_qdrant_mcp` — Qdrant MCP server (:8001)
- `wikijs_ingestion` — Ingestion Pipeline (:8002)
- `wikijs_tesseract_mcp` — Tesseract OCR MCP (:8003)

First startup takes 5-10 minutes (image build with pre-downloaded models). Subsequent starts are fast.

## 3. Verify

```bash
# Check all containers are healthy
docker compose ps

# Test MCP server endpoints (HTTP status check)
curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/sse && echo " OK"  # Qdrant MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:8002/sse && echo " OK"  # Ingestion Pipeline
curl -s -o /dev/null -w '%{http_code}' http://localhost:8003/sse && echo " OK"  # Tesseract MCP
```

## 4. Configure Cursor

Add to your Cursor `mcp.json`:

```json
{
  "mcpServers": {
    "qdrant":     { "type": "sse", "url": "http://localhost:8001/sse" },
    "ingestion":  { "type": "sse", "url": "http://localhost:8002/sse" },
    "tesseract":  { "type": "sse", "url": "http://localhost:8003/sse" }
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
  pytest tests/integration/stack/ -v -m integration_stack
```

## Next Steps

- [LLM Wiki Workflows](llm-wiki-workflows.md) — Core operating workflows for agents
- [Agent Orientation](agent-orientation.md) — How to instruct the LLM agent
- [Stack Lifecycle Guide](stack-lifecycle.md) — Build, start, stop, rebuild
- [File Paths and Volumes](file-paths-and-volumes.md) — Where files go
