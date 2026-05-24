# Task 05: Unit Test Suite (~80 tests)

| Field | Value |
|-------|-------|
| Status | completed |
| Priority | P0 |
| Effort | Large |
| Depends on | 03 (CI pipeline for automated runs) |
| Blocks | none |

## Objective

Create ~80 unit tests with mocked dependencies to enable fast iteration without Docker. Complement the existing integration/E2E tests which require running services.

## Background

Current tests require Docker services (Qdrant, Wiki.js). While these provide realistic validation, they're slow (~104s for 60 fast tests) and can't run in all environments. Unit tests with mocked external dependencies run in milliseconds and enable rapid TDD cycles.

The `doc_v3/improvements/index.md` lists "Unit test suite" as a large-effort quick win.

## Implementation Plan

### 1. Identify testable units

For each of the 4 MCP servers, identify pure functions that can be unit tested:

**Wiki.js MCP:**
- `_extract_links(content)` — markdown link extraction
- `_resolve_paths_to_ids(paths)` — path resolution (mock GraphQL)
- `_cosine_similarity` / embedding helpers (if still present)
- Statistics computation helpers
- Date filtering in `wikijs_get_recent_changes`

**Qdrant MCP:**
- `compute_embedding(text)` — with mock SentenceTransformer
- Validation/formatting helpers
- Filter construction logic

**Ingestion Pipeline:**
- `chunker.split_text()` — chunking logic
- `detector.classify_page()` — classification logic
- Content hash computation

**Tesseract MCP:**
- `preprocess.deskew()` — image processing (with fixture images)
- `detector.classify_pdf_page()` — classification heuristics
- Page range parsing

### 2. Set up test infrastructure

- Add `pytest-mock` to test requirements
- Create `tests/unit/` directory with per-server subdirectories
- Add `unit` pytest marker
- Add `pytest.ini` marker registration

### 3. Write tests

Target ~80 tests:
- ~30 for Wiki.js MCP helpers
- ~15 for Qdrant MCP
- ~20 for Ingestion Pipeline
- ~15 for Tesseract MCP

### 4. Integrate with CI

Add `pytest tests/unit/ -v -m unit` to CI workflow (Task 03).

## Decisions

### 2026-05-24 — Task 05: Unit test organization

**Decision:** Unit tests are organized by MCP server under `tests/unit/{wiki,qdrant,ingestion,tesseract}/`. Tests import source modules via `sys.path.insert()` to avoid Docker dependency. Mocked dependencies use `unittest.mock.patch` and `pytest-mock`.

**Rationale:** Per-server directories make it clear which component is being tested. `sys.path` insertion is a practical way to import source code without installing packages or running in Docker. `pytest-mock` provides the `mocker` fixture for clean mocking.

### 2026-05-24 — Task 05: Test targets

**Decision:** ~109 unit tests created across 4 test files, exceeding the target of ~80. Tests cover all pure functions identified during codebase exploration.

**Rationale:** Every identified pure function gets test coverage. The excess over 80 is intentional — it's better to over-deliver on test coverage than to stop at an arbitrary number. Tesseract preprocessing functions received especial attention due to their mathematical nature.

## Documentation Updates

- [ ] `doc_v3/improvements/index.md` — mark "Unit test suite" as completed
- [ ] `doc_v3/reference/testing.md` — add unit test section to test pyramid and suite catalog
- [ ] `doc_v3/reference/test-results.md` — add unit test results

## Completion Criteria

- [ ] Unit tests exist for all 4 MCP servers
- [ ] At least 60 tests pass (target: ~80)
- [ ] All tests run without Docker (pure Python, mocked deps)
- [ ] `pytest` marker `unit` is registered
- [ ] Unit tests run in CI pipeline
- [ ] Test documentation updated

## Notes

- Created 4 unit test files with ~109 total tests:
  - `tests/unit/wiki/test_utils.py` — 35 tests (link extraction, markdown→HTML, file hashing, AST parsing)
  - `tests/unit/qdrant/test_filters_and_embedder.py` — 14 tests (filter construction, embedding computation with mocks)
  - `tests/unit/ingestion/test_chunker_and_detector.py` — 28 tests (text chunking, heading splitting, section splitting, file type detection)
  - `tests/unit/tesseract/test_preprocess.py` — 32 tests (grayscale, threshold, deskew, denoise, sharpen, full pipeline)
- Added `numpy`, `opencv-python-headless`, `pytest-mock` to `tests/Dockerfile.test`
- Added unit test job to CI workflow (no Docker services needed)
- All unit tests run without Docker — pure Python with mocked/monkeypatched deps
- `pytest` marker `unit` already existed in `pytest.ini`
