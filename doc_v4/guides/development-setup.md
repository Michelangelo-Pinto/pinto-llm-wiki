# Development Setup

Development environment setup and conventions for pinto-llm-wiki v4.

## Repository Structure

```
mcp-servers/                  # MCP server source code
  qdrant-mcp/                 # Qdrant MCP (8 tools)
  ingestion-pipeline/         # Ingestion Pipeline (7 tools)
  tesseract-mcp/              # Tesseract MCP (7 tools)
doc_v4/                       # Documentation
knowledge/                    # Knowledge base (file-system MD)
tests/                        # Test suites
```

## Prerequisites

- Docker and Docker Compose
- Python 3.12
- 4 GB RAM minimum

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/mikep/pinto-llm-wiki.git
cd pinto-llm-wiki
cp .env.example .env

# 2. Start the stack
docker compose up -d

# 3. Verify health
docker compose ps    # Expect 4 containers running + healthy

# 4. Run tests
docker compose --profile test run --rm test-runner
```

## Running Tests Locally

### Unit tests (no Docker)

```bash
PYTHONPATH="mcp-servers/qdrant-mcp/src:mcp-servers/ingestion-pipeline/src:mcp-servers/tesseract-mcp/src" \
pytest tests/unit/ -v -m unit
```

### Integration tests (Docker required)

```bash
# Fast (Qdrant only)
docker compose --profile test run --rm test-runner

# Full stack
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/smoke/ -v -m "integration_stack or smoke"
```

## Server Source Structure

Each MCP server follows the same pattern:

```
mcp-servers/<server>/
  Dockerfile          # Container build
  requirements.txt    # Python dependencies
  src/<package>/
    server.py         # FastMCP entry point, tool registration
    tools.py          # Tool function definitions
    <other modules>   # Domain-specific logic
```

## Code Conventions

- **Tool prefix**: `qdrant_*`, `ingest_*`, `ocr_*`
- **Return format**: `json.dumps(dict)` — always JSON string
- **Error format**: `json.dumps({"error": "message"})`
- **Transport**: SSE on path `/sse`
- **Embedding model**: `all-MiniLM-L6-v2` (384-dim, Cosine distance)

See [Patterns](../patterns/index.md) for detailed code patterns.
