# CHANGELOG.md — v3 Migration Change Log

Append-only chronological log of all v3 migration changes.

## 2026-05-23

### Tests Executed and API Fixes
- Generated full test-data set (PDF, DOCX, images) via ingestion-pipeline container
- Updated tests/Dockerfile.test with ingestion runtime deps (Tesseract, PyMuPDF, etc.)
- Fixed Qdrant client API: `client.search()` → `client.query_points()` (qdrant-client 1.18)
- Fixed idempotency E2E test isolation (unique temp file per test)
- Added empty-query validation to `ingest_search_chunks`
- **27/27 E2E tests passed**, **7/7 performance benchmarks passed**

### Remaining Tasks Complete
- Created tests/Dockerfile.test for containerized test runner
- Created tests/e2e/test_e2e_pipeline.py (25 tests)
- Created tests/e2e/conftest.py with shared fixtures
- Created tests/performance/test_benchmarks.py (18 benchmarks)
- Created tests/test-data/generate_test_data.py (self-contained test data generator)
- Added test-runner service to docker-compose.yml (profile: test)
- Updated STATUS_V3.md reflecting 49 tasks complete, 2 ready for execution

### Phase 4 Complete
- Created doc_v3 routing index.md in every folder
- Created doc_v3/architecture/, features/, guides/, reference/, migration/, patterns/

### Phase 5 Complete
- Cleaned deprecated code (PageVector, vector helpers)
- Updated .gitignore (qdrant_data, ingestion_data, shared_data)
- Updated README.md for v3 architecture
- Created test-runner Docker service and Dockerfile.test
- Added `qdrant-db` service to docker-compose.yml (qdrant/qdrant:v1.17.1)
- Added `qdrant_data`, `qdrant_snapshots`, `shared_data` volumes
- Added Qdrant env vars to .env (ports, URL, collection names)
- Verified wikijs-net covers all containers

### Phase 1 Complete
- Created `mcp-servers/qdrant-mcp/` with Dockerfile, requirements.txt
- Implemented embedder.py (lazy singleton all-MiniLM-L6-v2, 384-dim)
- Implemented tools.py (8 tools: collection CRUD, search, upsert, delete, scroll)
- Implemented server.py (FastMCP SSE entry point)
- Added qdrant-mcp service to docker-compose.yml (port 8001)
- Created 17 integration tests in tests/integration/qdrant/
- Created doc_v3/mcp-servers/qdrant-mcp.md
- Created plans/llm-wiki/STANDARDS.md, STATUS_V3.md, CHANGELOG.md
- Created directory structure for tests/ (unit, integration, e2e, performance)
- Created plans/llm-wiki/index.md for routing
