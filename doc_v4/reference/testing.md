# Testing Guide

How and what we test across the wiki-js-mcp v4 ecosystem.

## Test Pyramid

```
         ┌──────────────┐
         │  Regression   │  ~10 tests (Wiki.js MCP tool suite)
         │  (wiki tools) │  Full stack required
         ├──────────────┤
         │  Stack Int.   │  ~10–15 tests (cross-service)
         │  (health +    │  Full stack required
         │   ingest→     │
         │   search)     │
         ├──────────────┤
         │    Smoke      │  ~37 tests (SSE transport)
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

| Suite | Path | Services | Transport | Test Count | Marker |
|-------|------|----------|-----------|------------|--------|
| Unit | `tests/unit/` | None (pure Python) | Mocked deps | ~109 | `unit` |
| Qdrant Integration | `tests/integration/qdrant/` | `qdrant-db` | Direct import | 26 | `integration` |
| Ingestion E2E | `tests/e2e/` | `qdrant-db` | Direct import | 27 | `e2e` |
| Performance | `tests/performance/` | `qdrant-db` | pytest-benchmark | 7 | `performance` |
| Smoke | `tests/smoke/` | Full stack | SSE (HTTP) | ~37 | `smoke` |
| Stack Integration | `tests/integration/stack/` | Full stack | Direct import + TCP/HTTP | ~10–15 | `integration_stack` |
| Wiki Regression | `tests/regression/` | Full stack | Direct import | ~10 | `regression` |

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

# Run all fast tests
docker compose --profile test run --rm test-runner pytest tests/ -v -m "integration or e2e or performance"
```

### `integration` profile — Full stack

For stack integration and regression tests. Requires the entire 5-container stack.

```bash
# Start full stack first
docker compose up -d

# Run stack integration tests
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ -v -m integration_stack

# Run wiki regression tests
docker compose --profile integration run --rm test-runner \
  pytest tests/regression/ -v -m regression

# Run all full-stack tests
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/regression/ -v -m "integration_stack or regression"
```

## Suite Details

### Unit Tests (`tests/unit/`)

**Purpose:** Fast, container-free tests of pure helper functions across all 4 MCP servers. Enables rapid iteration and TDD without Docker.

**What's tested:**
- **Wiki.js MCP:** Markdown link extraction, external link extraction, markdown→HTML conversion, file hashing, AST code structure parsing
- **Qdrant MCP:** Filter construction (must/should/must_not logic), embedding computation (with mocked SentenceTransformer)
- **Ingestion Pipeline:** Text chunking, heading-based splitting, sentence-boundary splitting, file type detection by extension
- **Tesseract MCP:** Image preprocessing pipeline (grayscale, adaptive threshold, deskew, denoise, sharpen)

**Design choice:** Tests use `unittest.mock.patch` and `pytest-mock` to isolate pure logic from external dependencies (file system, Qdrant client, Tesseract binary). Source modules are imported via `sys.path.insert()`.

**Command:**
```bash
# Run all unit tests (no Docker required)
PYTHONPATH="mcp-servers/qdrant-mcp/src:mcp-servers/ingestion-pipeline/src:mcp-servers/wiki-js-mcp/src:mcp-servers/tesseract-mcp/src" \
pytest tests/unit/ -v -m unit

# Run a specific module
pytest tests/unit/tesseract/test_preprocess.py -v -m unit
```

### Qdrant Integration (`tests/integration/qdrant/`)

**Purpose:** Verify Qdrant MCP tool functions work correctly against a running Qdrant instance.

**What's tested:**
- Embedding computation (384-dim vectors)
- Collection management (create, list, info, delete)
- Point operations (upsert, search, scroll, delete_by_filter)
- Edge cases (empty queries, missing collections, large batches)
- `score_threshold` filtering
- Upsert + search roundtrip with `document_id`

**Design choice:** Tests import tool functions directly (`from qdrant_mcp.tools import ...`) instead of going through SSE. This gives deterministic, fast tests. SSE transport is smoke-tested in stack health tests.

**Command:**
```bash
docker compose --profile test run --rm test-runner pytest tests/integration/qdrant/ -v -m integration
```

### Ingestion E2E (`tests/e2e/`)

**Purpose:** End-to-end document ingestion pipeline: detect file type → extract text (with OCR for scanned docs) → chunk → embed → upsert to Qdrant.

**What's tested:**
- Text PDF parsing
- Scanned PDF OCR routing
- DOCX text extraction
- DOCX with embedded images
- Markdown and plain text ingestion
- Image ingestion with OCR
- Background processing and `ingest_get_status` polling

**Test data:** Pre-generated fixtures in `tests/test-data/`. See [tests/test-data/README.md](../../tests/test-data/README.md).

**Command:**
```bash
docker compose --profile test run --rm test-runner pytest tests/e2e/ -v -m e2e
```

### Smoke Tests (`tests/smoke/`)

**Purpose:** Validate that every MCP tool is discoverable and callable via the real SSE transport (HTTP), complementing integration tests that import tools directly. Ensures the SSE layer that Cursor IDE uses is functional.

**What's tested:**
- Tool discovery: all 26 tools across 4 servers are listed by `tools/list`
- Basic invocation: parameter-less and simple-parameter tools return valid JSON without crashing
- Tools requiring real data (page IDs, file paths) are tested for discovery only

**Design choice:** A custom `McpSseClient` (in `tests/smoke/conftest.py`) implements the MCP SSE protocol using `httpx`. It connects to the SSE endpoint, parses the `endpoint` event, and sends JSON-RPC requests.

**Command:**
```bash
# Requires full stack: docker compose up -d
docker compose --profile integration run --rm test-runner pytest tests/smoke/ -v -m smoke
```

### Performance (`tests/performance/`)

**Purpose:** Benchmark Qdrant MCP operations with `pytest-benchmark`.

**What's measured:**
- Embedding computation latency (single and batch)
- Collection create/delete throughput
- Upsert throughput (1, 10, 100 chunks)
- Search latency
- Scroll pagination throughput

**Command:**
```bash
docker compose --profile test run --rm test-runner pytest tests/performance/ -v -m performance --benchmark-only
```

### Stack Integration (`tests/integration/stack/`)

**Purpose:** Verify cross-service communication in the full 5-container stack.

**What's tested:**
- TCP connectivity to all 6 services
- SSE endpoint responsiveness for all 4 MCP servers
- Cross-service flow: ingest document → search via Qdrant MCP
- Wiki.js + Qdrant: `smart_query` semantic path works with seeded pages

**Command:**
```bash
# Requires full stack: docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ -v -m integration_stack
```

### Wiki Regression (`tests/regression/`)

**Purpose:** Verify Wiki.js MCP v3 tools work and deprecated v2 tools are absent.

**What's tested:**
- Connection and authentication
- Page CRUD (create, get, update, search, delete)
- `smart_query` with Qdrant semantic path
- `wikijs_wiki_stats` and `wikijs_wiki_health`
- Deprecated tools (`wikijs_vector_search`, `wikijs_rebuild_vector_index`, `PageVector`) raise `ImportError`

**Legacy script:** `mcp-servers/wiki-js-mcp/scripts/test_all_tools.py` remains as a standalone runner for backward compatibility. The pytest regression suite is the preferred test method.

**Command:**
```bash
# Requires full stack: docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/regression/ -v -m regression
```

## Test Data

Pre-generated fixtures are committed in `tests/test-data/`. To regenerate:

```bash
docker compose build ingestion-pipeline
docker compose run --rm \
  -v ./tests/test-data:/data/test-data \
  ingestion-pipeline \
  python /data/test-data/generate_test_data.py
```

See [tests/test-data/README.md](../../tests/test-data/README.md) for the full fixture catalog.

## CI Pipeline

All test suites run automatically via GitHub Actions (`.github/workflows/test.yml`). The workflow uses two jobs:

### `qdrant-tests` (fast, ~3 min)

Runs on every push and pull request to `main`. Requires only `qdrant-db` (profile `test`).

- Qdrant integration tests (26 tests)
- E2E ingestion tests (27 tests)
- Performance benchmarks (7 tests)

### `stack-tests` (full-stack, ~5 min)

Runs on push to `main` and manual dispatch only. Requires the full 5-container stack (profile `integration`).

- Stack integration tests (~10–15 tests)
- Wiki regression tests (~10 tests)

The fast job provides rapid feedback on PRs while the stack job ensures comprehensive validation on merge to main.

[![Test Suite](https://github.com/mikep/wiki-js-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/mikep/wiki-js-mcp/actions/workflows/test.yml)

## Quick Commands Reference

```bash
# All fast tests (Qdrant only)
docker compose --profile test run --rm test-runner

# All tests including full-stack
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/ -v -m "not (integration_stack or regression)"
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/regression/ -v -m "integration_stack or regression"

# Single test
docker compose --profile test run --rm test-runner \
  pytest tests/integration/qdrant/test_qdrant_mcp.py::TestSearch::test_search_returns_results -v
```
