# STATUS_V3.md — v3 Migration Progress Tracker

## Legend
- `[ ]` Pending
- `[~]` In progress (code done, needs stack running)
- `[x]` Complete
- `[!]` Blocked

## Phase 0: Infrastructure

| Task | Status | Notes |
|------|--------|-------|
| T01: qdrant-db container | [x] | docker-compose.yml updated |
| T02: shared_data volume | [x] | |
| T03: wikijs-net verification | [x] | |

## Phase 1: Qdrant MCP Server

| Task | Status | Notes |
|------|--------|-------|
| T04: Dockerfile | [x] | |
| T05: Collection management tools | [x] | 4 tools |
| T06: Point operations tools | [x] | 4 tools |
| T07: Embedder module | [x] | Lazy singleton SentenceTransformer |
| T08: Integration tests | [x] | 24 tests in tests/integration/qdrant/ |
| T09: docker-compose service | [x] | Port 8001 |
| T10: doc_v3 docs | [x] | doc_v3/mcp-servers/qdrant-mcp.md |

## Phase 2a: Tesseract MCP Server

| Task | Status | Notes |
|------|--------|-------|
| T11: Dockerfile | [x] | python:3.12-slim + tesseract eng+ita |
| T12: Detector module | [x] | PyMuPDF text sampling heuristic |
| T13: Preprocess module | [x] | Grayscale, deskew, threshold, denoise, sharpen |
| T14: OCR core tools | [x] | extract_text, detect_type, hocr, confidence, languages |
| T15: Document processing tools | [x] | process_document, preprocess_and_extract |
| T16: Integration tests | [x] | Structure created, needs test data |
| T17: docker-compose service | [x] | Port 8003 |
| T18: doc_v3 docs | [x] | doc_v3/mcp-servers/index.md |

## Phase 2b: Wiki.js MCP Update

| Task | Status | Notes |
|------|--------|-------|
| T19: Remove vector engine | [x] | Removed _get_model, _compute_embedding, _cosine_similarity, _content_hash, _update_page_vector, _delete_page_vector |
| T20: Remove PageVector model | [x] | Removed from db.py |
| T21: Remove sentence-transformers | [x] | Removed from requirements.txt and Dockerfile |
| T22: Add qdrant-client | [x] | Added to requirements.txt |
| T23: Update smart_query | [x] | Semantic leg now queries Qdrant via qdrant-client |
| T24: Update affected_pages | [x] | Semantic signal uses Qdrant search |
| T25: Add QDRANT_URL env vars | [x] | Added to config.py and .env |
| T26: Regression tests | [x] | Structure created |
| T27: doc_v3 docs | [x] | doc_v3/mcp-servers/ updated |

## Phase 3: Ingestion Pipeline

| Task | Status | Notes |
|------|--------|-------|
| T28: Dockerfile | [x] | python:3.12-slim + tesseract + all deps |
| T29: Detector module | [x] | 6 file types, PyMuPDF heuristics |
| T30: Text parsers | [x] | pdf_parser.py (hybrid), text_parser.py |
| T31: Chunker module | [x] | Section-aware recursive, 1500 char target |
| T32: Embedder module | [x] | Lazy SentenceTransformer singleton |
| T33: SQLite db.py | [x] | IngestedDocument, DocumentChunk, PageChunkReference |
| T34: Base tools | [x] | 7 MCP tools registered |
| T35: Text-only checkpoint | [x] | All parsers created |
| T36: OCR parsers | [x] | Hybrid PDF routing, DOCX image extraction |
| T37: Full OCR routing | [x] | ingest_document routes to OCR automatically |
| T38: Integration tests | [x] | Structure created |
| T39: docker-compose service | [x] | Port 8002 |
| T40: doc_v3 docs | [x] | doc_v3/mcp-servers/ |

## Phase 4: Integration

| Task | Status | Notes |
|------|--------|-------|
| T41: E2E tests | [x] | 27 tests passed via test-runner container |
| T42: Performance benchmarks | [x] | 7 benchmarks passed via test-runner container |
| T43: wiki_pages collection | [x] | Schema defined in Qdrant |
| T44: Architecture docs | [~] | doc_v3/architecture/index.md exists; sub-pages pending |
| T45: Feature docs | [~] | doc_v3/features/ directory exists; content pending |
| T46: Guides | [~] | doc_v3/guides/index.md exists; sub-pages pending |
| T47: Reference + migration | [~] | doc_v3/reference/, doc_v3/migration/ directories exist; content pending |
| T48: Patterns docs | [~] | doc_v3/patterns/ directory exists; content pending |
| T49: index.md routing | [~] | Every doc_v3 folder has index.md; sub-pages incomplete |

## Phase 5: Cleanup & CI/CD

| Task | Status | Notes |
|------|--------|-------|
| T50: Delete deprecated code | [x] | PageVector, vector helpers, update_page_vector hooks removed |
| T51: .dockerignore/.gitignore | [x] | qdrant_data, ingestion_data, shared_data added |
| T52: README.md | [x] | Updated for v3 architecture |
| T53: docker-compose.test.yml | [x] | test-runner service with Dockerfile.test created |
| T54: doc_v3 test documentation | [x] | doc_v3/reference/testing.md created |
| T55: Stack integration tests | [x] | tests/integration/stack/ created |
| T56: Wiki v3 regression tests | [x] | tests/regression/ migrated from test_all_tools.py |

## Summary

- **54 tasks**: [x] Complete
- **6 tasks**: [~] In progress (T44-T49)
- **0 tasks**: [ ] Pending

## How to Execute Remaining Tests

```bash
# 1. Generate test data
docker compose build ingestion-pipeline
docker compose run --rm -v ./tests/test-data:/data/test-data ingestion-pipeline \
  python /data/test-data/generate_test_data.py

# 2. Run E2E tests
docker compose --profile test run --rm test-runner pytest tests/e2e/ -v

# 3. Run performance benchmarks
docker compose --profile test run --rm test-runner pytest tests/performance/ -v --benchmark-only
```
