# wiki-js-mcp v3 Migration — Comprehensive Test Strategy

> **Status**: Design phase — written 2026-05-23
> **Baseline**: 79/79 tests passing (single-file `test_all_tools.py` in Docker)
> **Target**: 200+ tests across 4 MCP servers + Qdrant DB, deterministic & repeatable

---

## Architecture Summary (v3 Target)

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                           │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Tesseract MCP│  │ Ingestion    │  │  Qdrant MCP  │               │
│  │   Server     │  │ Pipeline MCP │  │   Server     │               │
│  │  ~6 tools    │  │   ~7 tools   │  │  ~10 tools   │               │
│  │              │  │              │  │              │               │
│  │ OCR text     │  │ detect       │  │ search       │               │
│  │ doc type     │  │ ingest       │  │ upsert       │               │
│  │ HOCR output  │  │ search       │  │ delete       │               │
│  │ preprocessing│  │ status       │  │ collection   │               │
│  │              │  │ batch dir    │  │  management  │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                 │                        │
│         │                 │          ┌──────┴───────┐               │
│         │                 │          │   Qdrant DB  │               │
│         │                 │          │  (port 6333) │               │
│         │                 │          └──────────────┘               │
│         │                 │                                         │
│  ┌──────┴─────────────────┴──────────────────┐                      │
│  │          Updated Wiki.js MCP Server        │                      │
│  │  smart_query → calls Qdrant via Qdrant MCP │                      │
│  │  vector engine removed (was embedded)      │                      │
│  │  ~43 tools (dropped: vector_search,         │                      │
│  │   rebuild_vector_index)                     │                      │
│  └──────────────────────┬────────────────────┘                      │
│                         │                                           │
│  ┌──────────────────────┴──────────────────────┐                   │
│  │           Wiki.js + PostgreSQL               │                   │
│  │               (existing stack)                │                   │
│  └──────────────────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 1. Test Categories per Component

### 1.1 Tesseract MCP Server (~6 tools, ~35 tests)

| # | Tool | Unit Tests | Integration Tests | Edge Cases |
|---|------|-----------|-------------------|------------|
| 1 | `tesseract_extract_text` | parameter validation, error on missing file, encoding fallback | real text PDF, scanned PDF, DOCX, image (PNG/JPG), plain text, markdown | empty file, corrupt file, 100+ page PDF, non-Latin text (CJK, Arabic), mixed-language doc, 0x0 image, massive image (>50MB), password-protected PDF |
| 2 | `tesseract_detect_document_type` | returns correct type for each format | text PDF vs scanned PDF classification, DOCX with images detection | empty DOCX, DOCX with zero text + only images, nested PDFs, hybrid PDF (some text pages + some scanned pages) |
| 3 | `tesseract_hocr_output` | valid HOCR structure produced, XML well-formedness | HOCR contains bounding boxes, HOCR preserves reading order, confidence scores per word | empty page HOCR, single-character page, page with no text (image only), multi-column layout |
| 4 | `tesseract_preprocess_image` | parameter validation (DPI, mode, threshold) | deskew corrects rotation, binarize threshold, noise removal, DPI scaling | grayscale input, 1x1 pixel image, inverted colors, extreme rotation (45°), watermark background |
| 5 | `tesseract_batch_process` | directory scanning, file filtering by extension | batch of mixed types (PDF+PNG+JPG), progress reporting, partial failure handling | empty directory, directory with 0 supported files, directory with 500+ files, permission-denied files, symlinks |
| 6 | `tesseract_get_languages` | returns expected language list | language pack availability check | eng-only deployment, custom language packs |

**Unit tests (~15)**: Mock Tesseract CLI/API, test parameter parsing, error handling, output parsing. No real Tesseract process needed.

**Integration tests (~20)**: Real Tesseract in Docker container, real document files. Every file format exercised.

### 1.2 Qdrant MCP Server (~10 tools, ~55 tests)

| # | Tool | Unit Tests | Integration Tests | Edge Cases |
|---|------|-----------|-------------------|------------|
| 1 | `qdrant_search` | query validation, limit clamping, filter parsing | vector search returns results, search with metadata filter, search with payload filter, empty collection search | empty query, limit=0, limit=1000, non-existent collection, empty collection |
| 2 | `qdrant_upsert` | parameter validation, ID generation, vector dimension check | insert single point, batch insert 100 points, update existing point, insert with payload | wrong dimension vector, null payload, empty payload, duplicate ID (upsert behavior), 10,000 point batch |
| 3 | `qdrant_delete` | ID validation, selector parsing | delete by ID, delete by filter, delete all in collection, verify point count after delete | delete non-existent ID, delete from empty collection, concurrent delete |
| 4 | `qdrant_create_collection` | name validation, dimension validation, distance metric validation | create collection, create with custom config, create with named vectors | duplicate collection name, name with special characters (unicode), 0-dimension, very large dimension (4096) |
| 5 | `qdrant_delete_collection` | name validation | delete collection, verify points gone, verify collection listing updated | delete non-existent collection, delete then recreate same name |
| 6 | `qdrant_list_collections` | output format validation | empty state (no collections), after creating 3 collections, after deleting 1 | pagination (100+ collections) |
| 7 | `qdrant_collection_info` | parameter validation | point count, vector count, disk usage, segments count | empty collection info, non-existent collection |
| 8 | `qdrant_scroll` | limit/offset validation, filter parsing | scroll through all points, scroll with filter, verify ordering | empty collection scroll, offset beyond collection size, filter matching 0 points |
| 9 | `qdrant_count` | filter parsing | exact count matches after upserts, count after deletes, count with filter | empty collection count, filter matching all points, filter matching no points |
| 10 | `qdrant_health` | — | connection check, cluster status, version info | Qdrant container not running, Qdrant unhealthy, slow response timeout |

**Unit tests (~20)**: Mock Qdrant HTTP client (httpx), validate tool output schemas, test parameter edge cases. No real Qdrant needed.

**Integration tests (~35)**: Real Qdrant container, real vector operations, full CRUD lifecycle. Pre-populated collections for search tests.

### 1.3 Ingestion Pipeline MCP Server (~7 tools, ~50 tests)

| # | Tool | Unit Tests | Integration Tests | Edge Cases |
|---|------|-----------|-------------------|------------|
| 1 | `ingestion_detect` | file type detection logic, MIME routing, content hash computation | returns correct type for every format, confidence scores, page count for PDFs | empty file, 0-page PDF, corrupt DOCX, file with wrong extension (.txt actually a PDF), binary file, password-protected file, 500MB PDF, zero-byte file |
| 2 | `ingestion_ingest` | orchestrator flow, status transitions, idempotency check | full pipeline: detect → parse → chunk → embed → store, force re-ingest, dedup on content hash | re-ingest same file (expect already_ingested), ingest with force=True, partial failure (some chunks fail), OOM on large doc, connection lost mid-ingest, concurrent ingest of same file |
| 3 | `ingestion_search` | query validation, limit clamping, filter parsing | search returns relevant chunks, search with source filter, search with file_type filter, mixed query (wikis + chunks) | empty query, query with only stop words, query in non-English language, no results found, searching before any ingestion |
| 4 | `ingestion_status` | parameter handling, pagination | status of single doc by ID, status by content hash, listing recent documents, filter by status (completed/failed/processing/partial) | no documents ingested, invalid document_id, invalid content_hash format |
| 5 | `ingestion_batch_directory` | directory scanning, file filtering, recursive flag | batch ingest 5 mixed-type files, batch with recursive subdir, progress/results per file, skipped duplicates | empty directory, directory with 0 supported files, subdir with no supported files, max batch size (500 files), nested directory loops (symlinks) |
| 6 | `ingestion_delete_document` | ID validation, cascading delete verification | delete document + all chunks, verify chunks removed, verify can re-ingest after delete | delete non-existent document, delete already-deleted document, verify cascade (chunks, references all gone) |
| 7 | `ingestion_stats` | output format validation | returns total docs, total chunks, total bytes, breakdown by file_type, breakdown by status | empty state (0 docs ingested), after batch of 100 docs |

**Unit tests (~18)**: Mock Tesseract MCP responses, mock Qdrant MCP responses, isolatable pure-logic functions (detector, chunker, parser registry).

**Integration tests (~32)**: Full pipeline with real Tesseract MCP + Qdrant MCP. Real document files ingested end-to-end.

### 1.4 Updated Wiki.js MCP Server (~43 tools, ~100 tests)

| Test Group | Description | Test Count |
|-----------|-------------|-----------|
| **Carry-forward tests** | All 79 existing tests from `test_all_tools.py` that don't involve removed tools | ~73 |
| **Dropped tools removed** | Verify `wikijs_vector_search` and `wikijs_rebuild_vector_index` are gone | 2 |
| **smart_query updated** | Calls Qdrant (not embedded engine), returns correct results via Qdrant MCP, fallback modes with Qdrant unavailable, RRF merge still works | 8 |
| **Qdrant integration** | smart_query → Qdrant MCP → vector search → merge with keyword → ranked results | 4 |
| **Deprecation notice** | Old tools return clear deprecation message with migration guidance | 2 |
| **New cross-server errors** | Graceful handling when Qdrant MCP is unreachable, Tesseract MCP is slow | 3 |
| **Migration backward compat** | Export v2 format → import into v3 still works, existing SQLite data handled | 3 |
| **Link to ingestion** | wiki page can reference ingested document chunks, backlinks cross server boundary | 5 |

**Integration tests (~53)**: Real Wiki.js stack + Qdrant container + pre-populated data. Tests the full smart_query → Qdrant pipeline.

**End-to-end tests (~20)**: Complete document → ingestion → Qdrant → wiki search flow. (Counted in section 1.6.)

### 1.5 Qdrant DB Container (~10 tests)

Tests that validate the Qdrant container itself is healthy and correctly configured:

- Container starts with correct version
- Health check endpoint returns OK
- Collections persist across container restart
- Memory limits respected
- API authentication works (if enabled)
- Disk persistence works (data survives down/up)
- Concurrent read/write operations

These are infrastructure tests, not tool tests. Run as a pre-suite smoke test.

### 1.6 End-to-End Integration Tests (~25 tests)

Full cross-server flows:

| Flow | Steps | Test Count |
|------|-------|-----------|
| **Document → Wiki search** | Tesseract OCR PDF → Ingest chunks → Qdrant upsert → Wiki smart_query → returns chunks | 5 |
| **Text PDF flow** | Tesseract detect text PDF → Ingest (no OCR) → Qdrant store → Wiki search finds relevant sections | 3 |
| **Scanned PDF flow** | Tesseract OCR scanned PDF → Ingest chunks → Qdrant store → Wiki search finds OCR text | 3 |
| **DOCX with images flow** | Tesseract detect DOCX+images → OCR embedded images → Ingest → Qdrant → Wiki search | 3 |
| **Batch flow** | Batch directory of 10 mixed files → all ingested → all searchable via Wiki | 3 |
| **Update flow** | Ingest doc → update doc on disk → re-ingest with force → old chunks gone, new chunks searchable | 2 |
| **Delete flow** | Ingest doc → wiki search finds it → delete via ingestion → wiki search no longer finds it | 2 |
| **Idempotency flow** | Ingest doc → same doc again → returns already_ingested → no duplicate chunks | 2 |
| **Wiki page + doc chunk linking** | Ingest doc → create wiki page referencing chunk → backlinks work | 2 |

---

## 2. Test Infrastructure — Required Containers

### 2.1 Infrastructure Matrix

| Test Level | Containers Required | Startup Time | Runs Where |
|-----------|-------------------|-------------|-----------|
| **Unit tests** | None (pure Python) | <1s | Local, CI |
| **Tesseract integration** | `tesseract-mcp` only | ~10s | CI, local (docker compose up tesseract-mcp) |
| **Qdrant integration** | `qdrant` + `qdrant-mcp` | ~15s | CI, local |
| **Ingestion integration** | `qdrant` + `qdrant-mcp` + `tesseract-mcp` + `ingestion-mcp` | ~25s | CI only |
| **Wiki.js integration** | `db` (postgres) + `wiki` + `setup` + `wiki-mcp` | ~60s | CI, local |
| **Full E2E** | All 8 containers | ~90s | CI only (per-PR) |
| **Performance** | All 8 containers | ~90s | CI nightly |
| **Regression** | `db` + `wiki` + `setup` + `wiki-mcp` + `qdrant` | ~70s | Every commit |

### 2.2 Docker Compose Profiles

```yaml
# docker-compose.v3.yml — profile-based service grouping

services:
  db: &db
    image: postgres:15-alpine
    profiles: [wiki, e2e, regression, perf]

  wiki: &wiki
    image: ghcr.io/requarks/wiki:2
    profiles: [wiki, e2e, regression, perf]

  setup: &setup
    image: curlimages/curl:latest
    profiles: [wiki, e2e, regression, perf]

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333", "6334:6334"]
    profiles: [qdrant, ingestion, e2e, regression, perf]

  tesseract-mcp:
    build: ./mcp-servers/tesseract
    ports: ["8001:8001"]
    profiles: [tesseract, ingestion, e2e, perf]

  ingestion-mcp:
    build: ./mcp-servers/ingestion
    ports: ["8002:8002"]
    depends_on: [qdrant, tesseract-mcp]
    profiles: [ingestion, e2e, perf]

  qdrant-mcp:
    build: ./mcp-servers/qdrant
    ports: ["8003:8003"]
    depends_on: [qdrant]
    profiles: [qdrant, e2e, regression, perf]

  wiki-mcp:
    build: ./mcp-servers/wiki
    ports: ["8000:8000"]
    depends_on: [setup, qdrant-mcp]
    profiles: [wiki, e2e, regression, perf]
```

### 2.3 Test Runner Docker Compose

A dedicated `docker-compose.test.yml` that mounts test directories and runs pytest:

```yaml
services:
  test-runner:
    build:
      context: .
      dockerfile: Dockerfile.test
    volumes:
      - ./tests:/app/tests:ro
      - ./test-data:/app/test-data:ro
      - test_results:/app/test-results
    environment:
      - TESSERACT_MCP_URL=http://tesseract-mcp:8001
      - QDRANT_MCP_URL=http://qdrant-mcp:8003
      - INGESTION_MCP_URL=http://ingestion-mcp:8002
      - WIKI_MCP_URL=http://wiki-mcp:8000
      - QDRANT_URL=http://qdrant:6333
    command: >
      pytest tests/ -v
      --junitxml=/app/test-results/junit.xml
      --cov=/app/mcp-servers
      --cov-report=xml:/app/test-results/coverage.xml
      --cov-report=html:/app/test-results/htmlcov
    depends_on: [qdrant, tesseract-mcp, ingestion-mcp, qdrant-mcp, wiki-mcp]
```

---

## 3. Test Data — Sample Documents

All test data lives in `tests/test-data/` (volume-mounted read-only into test containers). Organized by format and purpose:

```
tests/test-data/
├── README.md                          # How to regenerate test data
├── text-pdf/
│   ├── hello-world.pdf                # 1-page, "Hello World" content, ~1KB
│   ├── technical-report.pdf           # 15-page, sections with tables, ~500KB
│   ├── empty.pdf                       # 0-page (corner case — handled by parser)
│   ├── large-report.pdf               # 100+ pages, ~5MB (performance test only)
│   └── multi-column.pdf               # 2-column layout, 3 pages
├── scanned-pdf/
│   ├── scanned-typed-letter.pdf       # 1-page, clean typewriter scan, ~200KB
│   ├── scanned-handwritten.pdf        # 1-page, handwritten notes, ~300KB
│   ├── scanned-form.pdf               # 2-page, form fields + text, ~400KB
│   └── scanned-mixed-lang.pdf         # 2-page, English + Arabic, ~350KB
├── docx/
│   ├── simple-memo.docx               # 1-page, plain text only
│   ├── report-with-tables.docx        # 5-page, text + tables
│   ├── with-images.docx               # 2 embedded PNG images with text labels
│   ├── with-charts.docx               # 3 embedded chart images (pie, bar)
│   ├── empty.docx                      # 0 paragraphs
│   └── malformed.docx                 # Valid .zip but not a DOCX (corner case)
├── markdown/
│   ├── simple-readme.md               # Standard README content
│   ├── api-reference.md               # ## headings, code blocks, tables
│   └── chinese-readme.md              # Simplified Chinese content
├── text/
│   ├── plain-notes.txt                # UTF-8 plain text
│   ├── latin1-encoded.txt             # Latin-1 encoded (encoding fallback test)
│   └── empty.txt                       # 0 bytes
├── images/
│   ├── screenshot.png                 # UI screenshot with text, 1920x1080
│   ├── whiteboard-photo.jpg           # Photo of handwritten whiteboard
│   ├── logo.png                        # No text, just a logo
│   ├── tiny.png                        # 1x1 pixel
│   └── diagram.png                    # Flowchart with text labels
├── mixed-batch/                        # For batch directory tests
│   ├── report.pdf
│   ├── notes.docx
│   ├── photo.jpg
│   ├── overview.md
│   └── subdir/
│       └── deep-note.txt
└── corrupt/                            # Deliberately corrupt files
    ├── corrupt.pdf                     # Truncated PDF header
    ├── corrupt.docx                    # Broken ZIP structure
    ├── not-actually-png.png            # Renamed .txt as .png
    └── 30mb-binary-blob.bin            # Large binary, no format match
```

### 3.1 Test Data Principles

1. **Git-tracked**: All test data committed to repo (no download-on-first-run). Keep under 10MB total (exclude `large-report.pdf` from git, generate at test time via script).
2. **Deterministic content**: Every file has known, verifiable text content for assertion in tests.
3. **Regeneratable**: Each file has a generation script in `tests/test-data/generate/` (Python script using fpdf, python-docx, Pillow).
4. **Minimal size**: Use smallest possible files that exercise the behavior (e.g., `hello-world.pdf` is 1 page, not a 50-page book).
5. **Isolation**: Tests never modify test-data files. Output goes to temp directories. Each test file uses its own subset.

---

## 4. Test Fixtures

### 4.1 pytest Fixtures (in `conftest.py` files)

```python
# conftest.py — top-level fixtures shared across all test files

@pytest.fixture(scope="session")
def qdrant_client():
    """Qdrant HTTP client connected to test container, session-scoped."""
    client = QdrantClient(host="qdrant", port=6333)
    yield client
    client.close()

@pytest.fixture(scope="session")
def qdrant_test_collection(qdrant_client):
    """Pre-created Qdrant collection with 384-dim vectors (MiniLM)."""
    name = "test_collection_v3"
    qdrant_client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    yield name
    qdrant_client.delete_collection(name)

@pytest.fixture(scope="session")
def preloaded_qdrant_collection(qdrant_client):
    """
    Qdrant collection pre-loaded with 50 known document chunks.
    Used for search quality tests.
    """
    name = "preloaded_test"
    qdrant_client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    # Load from JSON fixture
    points = json.loads(
        Path("tests/fixtures/preloaded_points.json").read_text()
    )
    qdrant_client.upsert(collection_name=name, points=points)
    yield name
    qdrant_client.delete_collection(name)

@pytest.fixture
def temp_mcp_client(mcp_server_url):
    """Per-test SSE client for the given MCP server, auto-closes."""
    # Uses httpx or mcp SDK to connect to SSE endpoint
    ...

@pytest.fixture
def sample_text_pdf():
    """Path to hello-world.pdf test data."""
    return Path("test-data/text-pdf/hello-world.pdf")

@pytest.fixture
def sample_scanned_pdf():
    """Path to scanned-typed-letter.pdf test data."""
    return Path("test-data/scanned-pdf/scanned-typed-letter.pdf")

@pytest.fixture
def sample_docx():
    """Path to simple-memo.docx test data."""
    return Path("test-data/docx/simple-memo.docx")

@pytest.fixture
def sample_docx_with_images():
    """Path to with-images.docx test data."""
    return Path("test-data/docx/with-images.docx")

@pytest.fixture
def tmp_ingestion_dir(tmp_path):
    """Temp directory for ingestion output tests, auto-cleaned."""
    return tmp_path / "ingestion_output"
```

### 4.2 JSON Fixture Files

```
tests/fixtures/
├── preloaded_points.json          # 50 Qdrant points with MiniLM vectors + payloads
├── expected_ocr_text.json         # Known text output for each test document
├── expected_chunk_hashes.json     # SHA-256 hashes of expected chunks
├── smart_query_expected.json      # Expected results for known queries
└── wiki_test_pages.json           # Page definitions for Wiki.js test data setup
```

### 4.3 Pre-loaded Qdrant Data (`preloaded_points.json`)

50 document chunks covering:
- 10 chunks from a technical report on databases
- 10 chunks from API documentation
- 10 chunks from OCR'd financial form
- 10 chunks from a README markdown file
- 10 chunks from a DOCX product spec

Each point includes:
```json
{
  "id": 1,
  "vector": [0.123, -0.456, ...],  // 384-dim MiniLM vector
  "payload": {
    "source_path": "test-data/text-pdf/technical-report.pdf",
    "source_filename": "technical-report.pdf",
    "file_type": "text_pdf",
    "page_number": 3,
    "chunk_index": 2,
    "section_heading": "## Database Architecture",
    "content_hash": "sha256...",
    "ingestion_id": "test-ingestion-001",
    "metadata": {"parser_version": "1.0.0"}
  }
}
```

These points are generated once by a script and committed to git. The generation script (`tests/fixtures/generate_points.py`) uses the same embedding model as production to ensure vector consistency.

---

## 5. Regression Tests — Wiki.js Tools After Migration

### 5.1 Tools Removed in v3

| Tool | Reason | Test |
|------|--------|------|
| `wikijs_vector_search` | Replaced by Qdrant | Verify tool returns deprecation error with migration guidance |
| `wikijs_rebuild_vector_index` | Replaced by Qdrant | Verify tool returns deprecation error with migration guidance |

### 5.2 Tools Modified in v3

| Tool | Change | Regression Tests |
|------|--------|-----------------|
| `wikijs_smart_query` | Calls Qdrant MCP instead of embedded engine | All 6 existing smart_query tests + 8 new integration tests |
| `wikijs_get_affected_pages` | Semantic signal now from Qdrant | Re-verify semantic signal weight with new backend |

### 5.3 Tools Unchanged (Must Behave Identically)

73 existing tests from `test_all_tools.py` are carried forward. These cover:

- **Page Management**: create, update, get, search, bulk_get, backlinks, rebuild_backlinks, page_stats, bulk_stats, append, tag management, filter, recent_changes, wiki_stats, wiki_health, export, import
- **Graph**: extract_links, page_graph, shortest_path
- **Hierarchy**: create_repo_structure, nested_page, children, doc_hierarchy
- **File Integration**: link_file, sync_file, file_overview, bulk_update
- **Deletion**: delete_page, batch_delete, delete_hierarchy, cleanup_orphaned
- **System**: connection_status, repository_context, manage_collections

### 5.4 Regression Test Runner

```bash
# Run only the unchanged-tool regression suite
docker compose -f docker-compose.v3.yml --profile regression up -d
docker compose -f docker-compose.test.yml run test-runner \
  pytest tests/regression/ -v --tb=short

# Expected: 73/73 pass (same as v2 minus the 2 removed vector tools)
```

### 5.5 Diff-Based Regression Detection

After each migration change, run the full regression suite and compare with v2 baseline:

```bash
# Generate v3 results
docker compose exec test-runner pytest tests/regression/ --json-report \
  > test-results/v3-regression.json

# Compare with v2 baseline
python scripts/compare_results.py \
  test-results/v2-baseline.json \
  test-results/v3-regression.json

# Fails if any previously-passing test now fails or produces different output
```

---

## 6. Performance Tests

### 6.1 Latency Targets

| Operation | Target (p50) | Target (p99) | Notes |
|-----------|-------------|-------------|-------|
| OCR single-page PDF | <3s | <8s | Tesseract on CPU, 300 DPI |
| OCR 10-page scanned PDF | <25s | <60s | Batch OCR, parallel pages |
| Detect file type | <100ms | <500ms | Local file I/O only |
| Ingest text PDF (15 pages) | <5s | <15s | Parse + chunk + embed + upsert |
| Ingest scanned PDF (10 pages) | <30s | <90s | OCR + parse + chunk + embed + upsert |
| Qdrant vector search (1K points) | <50ms | <200ms | Cosine similarity, 384-dim |
| Qdrant vector search (10K points) | <100ms | <500ms | With metadata filter |
| Qdrant upsert (100 points) | <200ms | <1s | Batch insert |
| smart_query (200 wiki pages + 1K chunks) | <2s | <5s | RRF merge + enrichment |
| Wiki.js GraphQL roundtrip | <500ms | <2s | Existing baseline |
| Ingestion batch (50 mixed files) | <120s | <300s | Full pipeline |

### 6.2 Performance Test Suite

Located in `tests/performance/`:

```python
# tests/performance/test_latency.py

@pytest.mark.performance
@pytest.mark.slow
class TestOcrLatency:
    def test_single_page_ocr_latency(self, tesseract_client, sample_scanned_pdf):
        latencies = []
        for _ in range(10):  # 10 warm runs
            start = time.perf_counter()
            result = tesseract_client.extract_text(sample_scanned_pdf)
            latencies.append(time.perf_counter() - start)

        p50 = statistics.median(latencies)
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        assert p50 < 3.0, f"OCR p50 latency {p50:.2f}s exceeds 3s target"
        assert p99 < 8.0, f"OCR p99 latency {p99:.2f}s exceeds 8s target"

    def test_ten_page_scanned_pdf_latency(self, tesseract_client, ten_page_scanned):
        start = time.perf_counter()
        result = tesseract_client.extract_text(ten_page_scanned)
        elapsed = time.perf_counter() - start

        assert elapsed < 25.0, f"10-page OCR took {elapsed:.1f}s"

@pytest.mark.performance
@pytest.mark.slow
class TestSearchLatency:
    def test_qdrant_search_1k_points(self, qdrant_client, preloaded_1k_collection):
        latencies = []
        query_vector = random_vector(384)

        for _ in range(50):
            start = time.perf_counter()
            qdrant_client.search(
                collection_name=preloaded_1k_collection,
                query_vector=query_vector,
                limit=10,
            )
            latencies.append(time.perf_counter() - start)

        p50 = statistics.median(latencies)
        assert p50 < 0.05, f"Search p50: {p50*1000:.0f}ms"

    def test_smart_query_end_to_end(self, wiki_mcp_client, preloaded_qdrant_collection):
        start = time.perf_counter()
        result = wiki_mcp_client.call_tool("wikijs_smart_query", {
            "query": "database architecture patterns"
        })
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"smart_query took {elapsed:.1f}s"

@pytest.mark.performance
@pytest.mark.slow
class TestBatchThroughput:
    def test_ingest_50_mixed_files(self, ingestion_client, mixed_batch_dir):
        start = time.perf_counter()
        result = ingestion_client.call_tool("ingestion_batch_directory", {
            "directory_path": str(mixed_batch_dir),
            "recursive": True,
        })
        elapsed = time.perf_counter() - start

        assert elapsed < 120.0, f"50-file batch took {elapsed:.1f}s"
        data = json.loads(result)
        assert data["ingested"] >= 45  # Allow some unsupported files
```

### 6.3 Performance Regression Detection

- Store baseline latencies in `tests/performance/baselines/v3-baseline.json`
- CI runs performance tests nightly
- Alert if any p50 exceeds 120% of baseline
- Alert if any p99 exceeds 150% of baseline

---

## 7. Test Organization — File Structure

```
tests/
├── conftest.py                          # Shared fixtures, pytest configuration
├── pytest.ini                           # Markers, timeout config, coverage config
│
├── unit/                                # No containers needed, pure Python
│   ├── test_tesseract_tools.py          # ~15 tests
│   ├── test_qdrant_tools.py             # ~20 tests
│   ├── test_ingestion_detect.py         # ~8 tests
│   ├── test_ingestion_chunker.py        # ~10 tests
│   ├── test_ingestion_orchestrator.py   # ~12 tests
│   └── test_wiki_tools.py               # ~15 tests (logic-only, mock GraphQL)
│
├── integration/                         # Real containers, real MCP calls
│   ├── tesseract/
│   │   ├── conftest.py                  # Tesseract MCP client fixture
│   │   ├── test_extract_text.py         # ~8 tests
│   │   ├── test_detect_type.py          # ~5 tests
│   │   ├── test_hocr.py                 # ~4 tests
│   │   ├── test_preprocess.py           # ~5 tests
│   │   └── test_batch.py                # ~4 tests
│   │
│   ├── qdrant/
│   │   ├── conftest.py                  # Qdrant client + collection fixtures
│   │   ├── test_search.py               # ~8 tests
│   │   ├── test_upsert.py               # ~6 tests
│   │   ├── test_delete.py               # ~5 tests
│   │   ├── test_collections.py          # ~8 tests
│   │   ├── test_scroll.py               # ~4 tests
│   │   └── test_health.py               # ~3 tests
│   │
│   ├── ingestion/
│   │   ├── conftest.py                  # All MCP client fixtures
│   │   ├── test_ingest_file.py          # ~10 tests
│   │   ├── test_ingest_directory.py     # ~6 tests
│   │   ├── test_search_chunks.py        # ~6 tests
│   │   ├── test_status.py               # ~5 tests
│   │   ├── test_delete.py               # ~4 tests
│   │   └── test_stats.py                # ~3 tests
│   │
│   └── wiki/
│       ├── conftest.py                  # Wiki.js MCP client + setup data fixture
│       ├── test_pages.py                # ~20 tests
│       ├── test_smart_query.py          # ~12 tests
│       ├── test_graph.py                # ~11 tests
│       ├── test_hierarchy.py            # ~4 tests
│       ├── test_files.py                # ~4 tests
│       ├── test_deletion.py             # ~4 tests
│       ├── test_import_export.py        # ~7 tests
│       └── test_system.py               # ~3 tests
│
├── e2e/                                 # Full stack, cross-server flows
│   ├── conftest.py                      # ALL MCP clients, all containers ready
│   ├── test_document_to_wiki.py         # ~10 tests
│   ├── test_batch_pipeline.py           # ~5 tests
│   ├── test_idempotency.py              # ~5 tests
│   └── test_deletion_flow.py            # ~5 tests
│
├── regression/                          # Carry-forward v2 tests
│   ├── conftest.py                      # Wiki.js setup, no Qdrant needed
│   ├── test_pages_regression.py         # ~53 tests (from v2 test_all_tools)
│   ├── test_graph_regression.py         # ~11 tests
│   ├── test_hierarchy_regression.py     # ~4 tests
│   ├── test_files_regression.py         # ~4 tests
│   ├── test_deletion_regression.py      # ~4 tests
│   └── test_system_regression.py        # ~3 tests
│
├── performance/                         # Latency/throughput benchmarks
│   ├── conftest.py                      # All containers, warmup logic
│   ├── baselines/
│   │   └── v3-baseline.json            # Recorded performance baselines
│   ├── test_ocr_latency.py              # ~5 tests
│   ├── test_search_latency.py           # ~6 tests
│   ├── test_ingestion_throughput.py     # ~4 tests
│   └── test_smart_query_perf.py         # ~3 tests
│
├── fixtures/                            # JSON fixtures, pre-loaded data
│   ├── preloaded_points.json
│   ├── expected_ocr_text.json
│   ├── expected_chunk_hashes.json
│   ├── smart_query_expected.json
│   ├── wiki_test_pages.json
│   └── generate_points.py               # Script to regenerate points
│
└── test-data/                           # Sample documents (committed to git)
    ├── README.md
    ├── generate/                        # Generation scripts
    ├── text-pdf/
    ├── scanned-pdf/
    ├── docx/
    ├── markdown/
    ├── text/
    ├── images/
    ├── mixed-batch/
    └── corrupt/
```

### 7.1 Test Runner Configuration

```ini
# tests/pytest.ini

[pytest]
testpaths = tests
markers =
    unit: Tests that run without containers (pure Python logic)
    integration: Tests that require real containers
    e2e: Full end-to-end cross-server tests
    regression: Carry-forward tests from v2
    performance: Latency/throughput benchmarks
    slow: Tests that take >10 seconds
    nightly: Tests that only run in nightly CI

timeout = 120
timeout_method = signal

addopts = -v --tb=short --strict-markers -p no:warnings

# Coverage
; coverage is configured in pyproject.toml

# Per-test-file timeouts
[tool:pytest]
timeout_func_default = 30
timeout_overrides =
    tests/performance/*: 600
    tests/e2e/*: 300
```

---

## 8. CI Strategy

### 8.1 CI Pipeline (GitHub Actions)

```
┌─────────────────────────────────────────────────────────────────┐
│                       EVERY PUSH / PR                            │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │  Lint + Type  │   │  Unit Tests   │   │ Regression   │         │
│  │   Check       │   │ (~60 tests)   │   │   Suite      │         │
│  │  <30s         │   │   <2m         │   │  (~73 tests)  │         │
│  │  ruff + mypy  │   │  pytest -m    │   │  pytest -m    │         │
│  │  (per server) │   │  unit -n auto │   │  regression   │         │
│  └──────────────┘   └──────────────┘   └──────────────┘         │
│                                                 │                │
│                                         Requires Docker:         │
│                                         db, wiki, setup,         │
│                                         wiki-mcp, qdrant         │
│                                         (~70s startup)           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              Integration Tests (per server)               │    │
│  │                                                          │    │
│  │  Tesseract (~25 tests, ~3m)   Qdrant (~35 tests, ~2m)   │    │
│  │  Ingestion (~32 tests, ~5m)                               │    │
│  │                                                          │    │
│  │  Requires: tesseract-mcp OR qdrant+qdrant-mcp OR         │    │
│  │            all 3 for ingestion                            │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ⚠ E2E tests run only if any of these paths changed:             │
│     mcp-servers/** tests/e2e/** tests/test-data/**                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              E2E Tests (conditional)                      │    │
│  │              (~25 tests, ~8m, all 8 containers)           │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         NIGHTLY                                   │
│                                                                   │
│  ┌──────────────────────────────┐  ┌──────────────────────────┐  │
│  │   Performance Benchmarks     │  │   Full Integration + E2E  │  │
│  │   (~18 tests, ~15m)          │  │   (always runs, ~15m)     │  │
│  │                              │  │                          │  │
│  │   Records baselines          │  │   All integration tests  │  │
│  │   Alerts on regression       │  │   All E2E tests          │  │
│  │   >120% p50, >150% p99       │  │   All regression tests   │  │
│  └──────────────────────────────┘  └──────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              Stress Tests                                  │    │
│  │              (large files, 500-file batch, 10K points)     │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 CI Test Matrix

| Job | Trigger | Containers | Est. Runtime | Parallel |
|-----|---------|-----------|-------------|----------|
| Lint + Type Check | Every push | None | 30s | per server |
| Unit tests | Every push | None | 2m | 4x (per server) |
| Tesseract integration | Every push | tesseract-mcp | 3m | yes |
| Qdrant integration | Every push | qdrant, qdrant-mcp | 2m | yes |
| Ingestion integration | Every push | qdrant, qdrant-mcp, tesseract-mcp, ingestion-mcp | 5m | no |
| Wiki.js regression | Every push | db, wiki, setup, wiki-mcp, qdrant | 5m | no |
| E2E tests | Conditional (path filter) | all 8 | 8m | no |
| Performance | Nightly | all 8 | 15m | no |
| Stress tests | Nightly | all 8 | 10m | no |

### 8.3 GitHub Actions Workflow (Conceptual)

```yaml
name: Test Suite

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 3 * * *'  # Nightly at 3 AM UTC

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint Tesseract MCP
        run: cd mcp-servers/tesseract && ruff check . && mypy .
      - name: Lint Qdrant MCP
        run: cd mcp-servers/qdrant && ruff check . && mypy .
      - name: Lint Ingestion MCP
        run: cd mcp-servers/ingestion && ruff check . && mypy .
      - name: Lint Wiki MCP
        run: cd mcp-servers/wiki && ruff check . && mypy .

  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        server: [tesseract, qdrant, ingestion, wiki]
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: |
          cd mcp-servers/${{ matrix.server }}
          pip install -e ".[test]"
          pytest tests/unit/ -v -m unit -n auto --cov

  integration:
    needs: [lint, unit-tests]
    runs-on: ubuntu-latest
    strategy:
      matrix:
        suite: [tesseract, qdrant, ingestion, wiki-regression]
    steps:
      - uses: actions/checkout@v4
      - name: Start required containers
        run: docker compose -f docker-compose.v3.yml --profile ${{ matrix.suite }} up -d --wait
      - name: Run integration tests
        run: |
          docker compose -f docker-compose.test.yml run test-runner \
            pytest tests/integration/${{ matrix.suite }}/ -v -m "integration and not slow"

  e2e:
    if: |
      github.event_name == 'schedule' ||
      contains(github.event.head_commit.modified, 'mcp-servers/') ||
      contains(github.event.head_commit.modified, 'tests/e2e/')
    needs: [integration]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Start full stack
        run: docker compose -f docker-compose.v3.yml --profile e2e up -d --wait
      - name: Run E2E tests
        run: |
          docker compose -f docker-compose.test.yml run test-runner \
            pytest tests/e2e/ -v -m e2e

  performance:
    if: github.event_name == 'schedule'
    needs: [integration]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Start full stack
        run: docker compose -f docker-compose.v3.yml --profile perf up -d --wait
      - name: Run performance tests
        run: |
          docker compose -f docker-compose.test.yml run test-runner \
            pytest tests/performance/ -v -m performance
      - name: Check for regressions
        run: python scripts/check_perf_regressions.py
```

---

## 9. How Tests Stay With the Project

### 9.1 Test File Location

All tests live in a top-level `tests/` directory at the repo root:

```
wiki-js-mcp/
├── tests/                              # ALL tests here
│   ├── unit/                           # Per-server unit tests
│   ├── integration/                    # Per-server integration tests
│   ├── e2e/                            # Cross-server flows
│   ├── regression/                     # v2 carry-forward
│   ├── performance/                    # Benchmarks
│   ├── fixtures/                       # Reusable JSON fixtures
│   └── test-data/                      # Sample documents
│
├── mcp-servers/
│   ├── tesseract/                      # No tests/ dir — all in top-level tests/
│   ├── qdrant/
│   ├── ingestion/
│   └── wiki/
│
└── README.md                           # Includes test instructions
```

### 9.2 Rationale for Top-Level Tests

1. **Cross-server tests need access to all MCP servers** — a single `tests/` root enables shared fixtures and e2e flows.
2. **Easier CI configuration** — one test runner image, one docker compose, one pytest invocation.
3. **Consistent with mature projects** — Django, FastAPI, and most Python projects use top-level `tests/`.
4. **Test data is shared** — `tests/test-data/` is consumed by integration, e2e, and performance tests.

### 9.3 Test Dependencies (`pyproject.toml` per server)

Each MCP server declares test dependencies in its own `pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "pytest-timeout>=2.2",
    "pytest-xdist>=3.5",    # Parallel test execution
    "pytest-json-report>=1.5",
    "httpx>=0.27",           # For HTTP-based MCP client
]
```

The top-level test runner image installs all four servers' test dependencies.

### 9.4 README Test Instructions

Add to `README.md`:

```markdown
## Running Tests

### Quick Start (unit tests only, no Docker)
```bash
pip install -e "mcp-servers/*/[test]"
pytest tests/unit/ -v -m unit -n auto
```

### Integration Tests (requires Docker)
```bash
# Start the containers for the test suite you want
docker compose -f docker-compose.v3.yml --profile qdrant up -d --wait

# Run the tests
docker compose -f docker-compose.test.yml run test-runner \
  pytest tests/integration/qdrant/ -v

# Stop containers when done
docker compose -f docker-compose.v3.yml --profile qdrant down
```

### Full Test Suite
```bash
docker compose -f docker-compose.v3.yml --profile e2e up -d --wait
docker compose -f docker-compose.test.yml run test-runner pytest tests/ -v
```

### Running a Single Test
```bash
docker compose -f docker-compose.test.yml run test-runner \
  pytest tests/integration/qdrant/test_search.py::test_semantic_search -v
```

### Test Profiles
| Profile | Containers | What's tested |
|---------|-----------|---------------|
| `tesseract` | tesseract-mcp | OCR tools |
| `qdrant` | qdrant + qdrant-mcp | Vector DB tools |
| `ingestion` | qdrant + qdrant-mcp + tesseract-mcp + ingestion-mcp | Pipeline tools |
| `wiki` | db + wiki + setup + wiki-mcp | Wiki.js tools (no Qdrant needed) |
| `regression` | db + wiki + setup + wiki-mcp + qdrant | Wiki.js regression suite |
| `e2e` | All 8 containers | Cross-server flows |
| `perf` | All 8 containers | Performance benchmarks |
```

---

## 10. Coverage Targets

### 10.1 Per-Component Targets

| Component | Line Coverage | Branch Coverage | Notes |
|-----------|-------------|----------------|-------|
| **Tesseract MCP** tools | 90% | 80% | OCR output varies by engine version; some branches untestable (OOM, OS errors) |
| **Tesseract MCP** parsers | 85% | 75% | Many error paths are OS-dependent |
| **Qdrant MCP** tools | 95% | 90% | Pure HTTP client, highly testable |
| **Qdrant MCP** error handling | 90% | 85% | Network errors mockable |
| **Ingestion MCP** orchestrator | 90% | 85% | Key business logic, must be well-covered |
| **Ingestion MCP** detector | 95% | 90% | Pure function, trivially testable |
| **Ingestion MCP** chunker | 95% | 90% | Pure function, trivially testable |
| **Ingestion MCP** parsers | 85% | 75% | Some error paths require corrupt files |
| **Wiki.js MCP** (unchanged tools) | 85% | 75% | Carried from v2; improve if refactoring |
| **Wiki.js MCP** smart_query (updated) | 90% | 85% | Critical path, must be well-covered |
| **Wiki.js MCP** client | 80% | 70% | GraphQL client with retry logic |
| **Wiki.js MCP** db layer | 75% | 65% | SQLAlchemy models, few branches |

### 10.2 Overall Targets

| Metric | Minimum | Target |
|--------|---------|--------|
| **Line coverage** | 80% | 88% |
| **Branch coverage** | 70% | 80% |
| **Files with <70%** | 0 | 0 |
| **Critical paths** (smart_query, ingest, search) | 90% | 95% |

### 10.3 Enforcement

```toml
# pyproject.toml (top-level test runner)

[tool.coverage.run]
source = ["mcp-servers"]
omit = ["*/tests/*", "*/test-data/*", "*/migrations/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
fail_under = 80

[tool.coverage.html]
directory = "test-results/htmlcov"
```

### 10.4 CI Enforcement

```yaml
# In GitHub Actions
- name: Check coverage
  run: |
    coverage report --fail-under=80
    coverage xml -o test-results/coverage.xml
- name: Upload coverage
  uses: codecov/codecov-action@v4
  with:
    files: test-results/coverage.xml
    fail_ci_if_error: false
    target: 80%
    threshold: 2%
```

---

## Appendix A: Determinism and Repeatability

### Principles

1. **Fixed random seeds**: Embedding models set `seed=42` in test configuration.
2. **Time-independent assertions**: Tests never assert on `now()`, `created_at`, or `updated_at` exact values. Use approximate comparisons (`pytest.approx(0.92, abs=0.05)` for vector similarities).
3. **Ordered iterables only**: Tests that iterate over dicts use `sorted()` or `collections.OrderedDict`.
4. **No network calls**: All MCP servers communicate within Docker network only. No external API calls.
5. **Content hash as ground truth**: Test assertions compare SHA-256 hashes of known-good output, not exact string matching (OCR can vary slightly by Tesseract version).
6. **Snapshot testing with tolerance**: Hash-based snapshots of expected output, with `pytest.approx` for float comparisons.

### Idempotent Setup

- Test data is read-only (volume-mounted `:ro`)
- Each test creates its own Qdrant collections, ingestion records, wiki pages
- Cleanup happens in fixture teardown, with `force=True` to handle partial states
- `docker compose down -v` between major test suites to reset state

---

## Appendix B: Edge Cases — Complete Matrix

### Empty Documents

| File | Expected Behavior |
|------|------------------|
| `empty.txt` (0 bytes) | Detection: `FileType.TEXT`, Parse: returns 1 empty page, Chunk: 0 chunks, Ingest: skipped with warning |
| `empty.docx` (0 paragraphs) | Detection: `FileType.DOCX`, Parse: returns 1 empty page, Chunk: 0 chunks, Ingest: skipped |
| `empty.pdf` (0 pages) | Detection: raises `EmptyDocumentError`, Ingest: status=failed |

### Corrupted Files

| File | Expected Behavior |
|------|------------------|
| `corrupt.pdf` (truncated header) | Detection: `UnsupportedFileType` or parse failure, Ingest: status=failed, error preserved |
| `corrupt.docx` (broken ZIP) | Detection: `UnsupportedFileType` or parse failure, Ingest: status=failed |
| `not-actually-png.png` (.txt renamed) | Detection: `FileType.TEXT` (MIME override by extension), then content-based detection should surface inconsistency |
| `30mb-binary-blob.bin` | Detection: `UnsupportedFileType`, clean error |

### Large Documents

| File | Expected Behavior |
|------|------------------|
| `large-report.pdf` (100+ pages) | Parse: completes (all pages), Chunk: produces many chunks, Ingest: all chunks embedded and stored, no OOM |
| 500-file batch directory | Batch: progress reported per file, partial failure handled, timing acceptable |

### Mixed-Language Documents

| File | Expected Behavior |
|------|------------------|
| `scanned-mixed-lang.pdf` (EN + AR) | OCR: produces text for both, Chunk: handles RTL/LTR mixture, Search: finds content in both languages |
| `chinese-readme.md` | Detection: `FileType.MARKDOWN`, Parse: UTF-8 preserved, Chunk: CJK-aware splitting, Search: Chinese queries work |

### Edge Case Tests Summary

| Category | Test Count |
|----------|-----------|
| Empty documents | 6 |
| Corrupted files | 5 |
| Large documents | 4 |
| Mixed language | 3 |
| Encoding edge cases | 4 |
| Concurrent operations | 3 |
| **Total edge case tests** | **25** |

---

## Appendix C: Test Count Summary

| Component | Unit | Integration | E2E | Regression | Perf | Total |
|-----------|------|------------|-----|-----------|------|-------|
| Tesseract MCP | 15 | 26 | — | — | 5 | 46 |
| Qdrant MCP | 20 | 34 | — | — | 6 | 60 |
| Ingestion MCP | 30 | 34 | — | — | 4 | 68 |
| Wiki.js MCP | 15 | 65 | — | 73 | 3 | 156 |
| Qdrant DB (container) | — | 10 | — | — | — | 10 |
| E2E cross-server | — | — | 25 | — | — | 25 |
| **Total** | **80** | **169** | **25** | **73** | **18** | **365** |

### Compared to v2 Baseline

| Metric | v2 (current) | v3 (target) |
|--------|-------------|------------|
| Test files | 1 (`test_all_tools.py`) | 35+ (organized by category) |
| Test functions | 79 | 365 |
| Test categories | 6 (implicit) | 6 (explicit: unit, integration, e2e, regression, perf, stress) |
| Test isolation | None (sequential in one file) | Full (per-file fixtures, parallelizable) |
| CI parallelization | None | 4-way parallel for unit + per-server integration |
| Coverage tracking | None | Per-component with 80% minimum |
| Performance tracking | None | Nightly benchmarks with regression alerts |
| Edge case coverage | Minimal | 25 dedicated edge case tests |
| Determinism guarantee | None explicit | Fixed seeds, hash-based assertions, time-independent |

---

## Appendix D: Migration Plan — Test Suite Implementation Order

### Phase 1: Foundation (Week 1)
1. Set up `tests/` directory structure
2. Write `conftest.py` with shared fixtures
3. Write `pytest.ini` and CI config
4. Create `docker-compose.v3.yml` with profiles
5. Create `Dockerfile.test` for test runner
6. Write `tests/test-data/README.md` and generation scripts
7. Generate all test data files

### Phase 2: Unit Tests (Week 1–2)
8. Write Tesseract MCP unit tests
9. Write Qdrant MCP unit tests
10. Write Ingestion MCP unit tests (detector, chunker, orchestrator)
11. Write Wiki.js MCP unit tests (logic-only)

### Phase 3: Integration Tests (Week 2–3)
12. Tesseract integration tests (one test file at a time)
13. Qdrant integration tests
14. Ingestion integration tests
15. Wiki.js integration tests (carrying forward v2 patterns)

### Phase 4: Regression Suite (Week 3)
16. Port v2 `test_all_tools.py` to pytest-format regression tests
17. Verify 73/73 carry-forward tests pass
18. Add deprecation tests for removed tools
19. Add smart_query update tests

### Phase 5: E2E + Performance (Week 3–4)
20. Write E2E cross-server flow tests
21. Write performance benchmark tests
22. Record baseline performance metrics
23. Set up nightly CI with regression alerts

### Phase 6: Polish (Week 4)
24. Achieve 80%+ line coverage on all components
25. Add 25 edge case tests
26. CI green on all jobs
27. Update `README.md` with test instructions
28. Document test strategy (this file finalized)
