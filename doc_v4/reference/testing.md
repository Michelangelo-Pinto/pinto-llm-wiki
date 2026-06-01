# Testing Guide

How and what we test across the wiki-js-mcp v4 ecosystem.

## Test Pyramid

```
         ┌──────────────┐
         │  Stack Int.   │  ~10 tests (cross-service health + ingest→search)
         │  (cross-svc)  │  Full stack required
         ├──────────────┤
         │    Smoke      │  ~25 tests (SSE transport)
         │  (all tools)  │  Full stack required
         ├──────────────┤
         │     E2E       │  27 tests (ingestion pipeline)
         │  (pipeline)   │  Qdrant-db only
         ├──────────────┤
         │  Integration  │  26 tests (Qdrant MCP)
         │  (qdrant)     │  Qdrant-db only
         ├──────────────┤
         │  Performance  │  7 benchmarks
         │  (benchmarks) │  Qdrant-db only
         ├──────────────┤
         │     Unit      │  ~109 tests (pure functions)
         │  (all servers)│  No containers required
         └──────────────┘
```

## Suite Catalog

| Suite | Path | Services | Transport | Marker |
|-------|------|----------|-----------|--------|
| Unit | `tests/unit/` | None | Mocked deps | `unit` |
| Qdrant Integration | `tests/integration/qdrant/` | `qdrant-db` | Direct import | `integration` |
| Ingestion E2E | `tests/e2e/` | `qdrant-db` | Direct import | `e2e` |
| Performance | `tests/performance/` | `qdrant-db` | pytest-benchmark | `performance` |
| Smoke | `tests/smoke/` | Full stack | SSE (HTTP) | `smoke` |
| Stack Integration | `tests/integration/stack/` | Full stack | Direct import + TCP/HTTP | `integration_stack` |

## Docker Profiles

### `test` profile — Qdrant only (fast)

For Qdrant integration, E2E, and performance tests. Only `qdrant-db` is required.

```bash
# Run Qdrant integration tests
docker compose --profile test run --rm test-runner pytest tests/integration/qdrant/ -v -m integration

# Run E2E ingestion tests
docker compose --profile test run --rm test-runner pytest tests/e2e/ -v -m e2e

# Run performance benchmarks
docker compose --profile test run --rm test-runner pytest tests/performance/ -v -m performance --benchmark-only
```

### `integration` profile — Full stack

For stack integration and smoke tests. Requires the full 4-container stack.

```bash
# Start full stack first
docker compose up -d

# Run stack integration tests
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ -v -m integration_stack

# Run SSE smoke tests
docker compose --profile integration run --rm test-runner \
  pytest tests/smoke/ -v -m smoke
```

## Suite Details

### Unit Tests (`tests/unit/`)

**Purpose:** Fast, container-free tests of pure helper functions across all 3 MCP servers.

**What's tested:**
- **Qdrant MCP:** Filter construction, embedding computation (with mocked SentenceTransformer)
- **Ingestion Pipeline:** Text chunking, heading-based splitting, file type detection by extension
- **Tesseract MCP:** Image preprocessing pipeline (grayscale, adaptive threshold, deskew, denoise, sharpen)

**Command:**
```bash
PYTHONPATH="mcp-servers/qdrant-mcp/src:mcp-servers/ingestion-pipeline/src:mcp-servers/tesseract-mcp/src" \
pytest tests/unit/ -v -m unit
```

### Qdrant Integration (`tests/integration/qdrant/`)

**Purpose:** Verify Qdrant MCP tool functions work correctly against a running Qdrant instance.

**What's tested:**
- Embedding computation (384-dim vectors)
- Collection management (create, list, info, delete)
- Point operations (upsert, search, scroll, delete_by_filter)
- `score_threshold` filtering

### Ingestion E2E (`tests/e2e/`)

**Purpose:** End-to-end document ingestion pipeline: detect file type → extract text (with OCR for scanned docs) → chunk → embed → upsert to Qdrant.

### Smoke Tests (`tests/smoke/`)

**Purpose:** Validate that every MCP tool is discoverable and callable via the real SSE transport.

**What's tested:** Tool discovery and basic invocation for all 22 tools across 3 servers.

### Stack Integration (`tests/integration/stack/`)

**Purpose:** Verify cross-service communication in the full 4-container stack.

**What's tested:**
- TCP connectivity to all services
- SSE endpoint responsiveness for all 3 MCP servers
- Cross-service flow: ingest document → search via Qdrant MCP

## Test Data

Pre-generated fixtures are committed in `tests/test-data/`. To regenerate:

```bash
docker compose build ingestion-pipeline
docker compose run --rm \
  -v ./tests/test-data:/data/test-data \
  ingestion-pipeline \
  python /data/test-data/generate_test_data.py
```

## CI Pipeline

All test suites run automatically via GitHub Actions (`.github/workflows/test.yml`).

### `qdrant-tests` (fast, ~3 min) — every push and PR
- Qdrant integration tests
- E2E ingestion tests
- Performance benchmarks

### `stack-tests` (full-stack, ~5 min) — main branch pushes and manual dispatch
- Stack integration tests
- SSE smoke tests

## Quick Commands Reference

```bash
# All fast tests (Qdrant only)
docker compose --profile test run --rm test-runner

# All tests including full-stack
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/smoke/ -v -m "integration_stack or smoke"

# Single test
docker compose --profile test run --rm test-runner \
  pytest tests/integration/qdrant/test_qdrant_mcp.py::TestSearch::test_search_returns_results -v
```
