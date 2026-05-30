# Tests — Developer Guide v4

How to write, run, and debug tests for wiki-js-mcp v4.

## Directory Structure

```
tests/
├── pytest.ini                  # Marker definitions
├── conftest.py                 # Shared fixtures (qdrant_url, qdrant_client)
├── Dockerfile.test             # Test runner container image
├── __init__.py
├── integration/
│   ├── qdrant/
│   │   ├── __init__.py
│   │   ├── conftest.py         # clean_collection fixture
│   │   └── test_qdrant_mcp.py  # 26 tests
│   └── stack/
│       ├── __init__.py
│       ├── conftest.py         # Stack health wait + env
│       ├── test_stack_health.py
│       └── test_stack_ingest_search.py
├── e2e/
│   ├── __init__.py
│   ├── conftest.py             # Test data paths, session collection
│   └── test_e2e_pipeline.py    # 27 tests
├── performance/
│   ├── __init__.py
│   └── test_benchmarks.py      # 7 benchmarks
├── unit/
│   ├── qdrant/
│   ├── ingestion/
│   └── tesseract/
└── test-data/
    ├── README.md               # Fixture catalog
    ├── generate_test_data.py   # Regeneration script
    ├── pdf/
    ├── docx/
    ├── images/
    ├── markdown/
    ├── text/
    └── mixed/
```

## Prerequisites

- Docker and Docker Compose
- `.env` file (copy from `.env.example`)

## Quick Start

```bash
# Run all fast tests (Qdrant integration + E2E + performance)
docker compose --profile test run --rm test-runner

# Run a specific suite
docker compose --profile test run --rm test-runner pytest tests/integration/qdrant/ -v

# Run a single test
docker compose --profile test run --rm test-runner \
  pytest tests/integration/qdrant/test_qdrant_mcp.py::TestSearch::test_search_returns_results -v
```

## Markers

Defined in `tests/pytest.ini`:

| Marker | Requires | Description |
|--------|----------|-------------|
| `integration` | `qdrant-db` | Qdrant MCP tool tests |
| `e2e` | `qdrant-db` | Ingestion pipeline tests |
| `performance` | `qdrant-db` | Benchmarks (slow) |
| `integration_stack` | Full stack | Cross-service tests |
| `unit` | None | Pure unit tests |

Use markers to filter:

```bash
pytest tests/ -m "integration or e2e"
pytest tests/ -m "not integration_stack"
```

## How Tests Import Code

Tests run inside the `test-runner` container. Source code is mounted as read-only volumes:

```yaml
volumes:
  - ./tests:/app/tests:ro
  - ./mcp-servers/qdrant-mcp/src:/app/qdrant_mcp:ro
  - ./mcp-servers/ingestion-pipeline/src:/app/ingestion_pipeline:ro
```

The `PYTHONPATH` includes all source directories:
```
PYTHONPATH=/app:/app/qdrant_mcp:/app/ingestion_pipeline
```

This means tests can do direct imports:
```python
from qdrant_mcp.tools import qdrant_search
from ingestion_pipeline.tools import ingest_document
```

**No SSE transport is used in tests** — direct imports are deterministic and faster. SSE transport is smoke-tested in `tests/integration/stack/test_stack_health.py`.

## Generating Test Data

```bash
docker compose build ingestion-pipeline
docker compose run --rm \
  -v ./tests/test-data:/data/test-data \
  ingestion-pipeline \
  python /data/test-data/generate_test_data.py
```

Fixtures are committed to the repo. Regenerate only when changing the generator script or adding new file types.

## Troubleshooting

### Import errors in tests

If you see `ModuleNotFoundError: No module named 'qdrant_mcp'`:
- Make sure the volume mounts are correct in `docker-compose.yml`
- The source path inside the container matches `PYTHONPATH`

### Tests skip with "Test data not found"

E2E tests skip when fixture files are missing. Regenerate with:
```bash
docker compose run --rm -v ./tests/test-data:/data/test-data ingestion-pipeline python /data/test-data/generate_test_data.py
```

### Qdrant connection refused

Ensure `qdrant-db` is healthy:
```bash
docker compose ps qdrant-db
docker compose logs qdrant-db
```

### Stack tests fail with timeout

Stack tests wait up to 30s for services to be healthy. If they timeout:
```bash
docker compose ps
docker compose logs qdrant-mcp
```
