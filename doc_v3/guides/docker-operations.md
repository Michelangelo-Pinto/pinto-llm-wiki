# Docker Operations (v3)

For stack start/stop/rebuild, see [Stack Lifecycle Guide](stack-lifecycle.md).

Commands for building, testing, and managing the 8-container Docker stack.

## Quick Reference

```bash
# Start full stack
docker compose up -d

# View status
docker compose ps

# View logs for a service
docker compose logs wiki-js-mcp
docker compose logs qdrant-mcp

# Stop everything
docker compose down
```

## Rebuilding Services

```bash
# Rebuild a specific service
docker compose build qdrant-mcp
docker compose up -d qdrant-mcp

# Full rebuild (dependency changes)
docker compose build --no-cache
docker compose up -d
```

## Testing

### Fast tests (Qdrant only)

```bash
# Run Qdrant integration tests
docker compose --profile test run --rm test-runner pytest tests/integration/qdrant/ -v

# Run E2E ingestion tests
docker compose --profile test run --rm test-runner pytest tests/e2e/ -v

# Run performance benchmarks
docker compose --profile test run --rm test-runner pytest tests/performance/ -v --benchmark-only
```

### Full-stack tests

```bash
# Start the stack first
docker compose up -d

# Run stack integration tests
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ -v -m integration_stack

# Run wiki regression tests
docker compose --profile integration run --rm test-runner \
  pytest tests/regression/ -v -m regression
```

See [Testing Guide](../reference/testing.md) for detailed test documentation.

## Health Checks

```bash
# Check all containers
docker compose ps

# Check MCP server SSE endpoints
curl http://localhost:8000/sse   # Wiki.js MCP
curl http://localhost:8001/sse   # Qdrant MCP
curl http://localhost:8002/sse   # Ingestion Pipeline
curl http://localhost:8003/sse   # Tesseract MCP

# Wiki.js web UI
curl http://localhost:3000
```

## Logs

```bash
# Follow logs for a service
docker compose logs -f wiki-js-mcp

# Last 50 lines
docker compose logs --tail 50 qdrant-mcp

# All service logs
docker compose logs --tail 100
```

## Seed Test Data

```bash
# Seed structured docs pages into Wiki.js
docker compose exec wiki-js-mcp python3 scripts/seed_wiki_docs.py

# Generate E2E test fixtures
docker compose run --rm \
  -v ./tests/test-data:/data/test-data \
  ingestion-pipeline \
  python /data/test-data/generate_test_data.py
```

## Database Inspection

```bash
# SQLite mappings database (wiki-js-mcp)
docker compose exec wiki-js-mcp sqlite3 /data/wikijs_mappings.db

# Qdrant collections (via REST)
curl http://localhost:6334/collections
curl http://localhost:6334/collections/wiki_pages

# Ingestion database
docker compose exec ingestion-pipeline sqlite3 /data/ingestion.db
```

## Troubleshooting

### Container won't start

```bash
docker compose logs <service-name>
docker compose restart <service-name>
```

### Wiki.js setup fails

If the `setup` container exits with error, Wiki.js may already be initialized. Check:
```bash
docker compose logs setup
curl http://localhost:3000
```

### Qdrant connection issues

MCP servers connect to Qdrant at `http://qdrant-db:6334` (REST). Verify:
```bash
curl http://localhost:6334/collections
```

### Model download fails (first run)

The `all-MiniLM-L6-v2` sentence transformer model (~80 MB) is pre-downloaded during Docker image build. If the download fails during build:

- Check network during build: `docker compose build qdrant-mcp ingestion-pipeline`
- The model is baked into the image and available immediately at runtime — no cold start delay.
