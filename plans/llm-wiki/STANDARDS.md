# STANDARDS.md — Engineering Standards

Code standards, test requirements, and best practices for wiki-js-mcp v3.

## Code Standards

### Comments
- Every public function has a docstring explaining *why*, not *what*
- Non-obvious logic gets inline comments explaining intent
- No obvious comments ("Increment counter", "Return result")
- Module-level docstrings describe the module's responsibility

### Naming
- Python modules: `snake_case` (tools_pages.py, pdf_parser.py)
- Python classes: `PascalCase` (QdrantClient, PageVector)
- Functions/methods: `snake_case` (compute_embedding, classify_pdf_page)
- MCP tools: `snake_case` with server prefix if needed (qdrant_search, ocr_extract_text)
- Database tables: `snake_case` (ingested_documents, page_chunk_references)

### Error Handling
- Every MCP tool returns `json.dumps(result)` 
- Errors returned as `{"error": "descriptive message"}` — never raised
- Log at INFO for completion, WARNING for recoverable, ERROR for failures
- Fire-and-forget hooks: failures logged, not propagated

### Project Structure
- `mcp-servers/<name>/` — One folder per MCP server
  - `Dockerfile`, `requirements.txt`, `pyproject.toml` at root
  - `src/<name>/` for Python package
  - `server.py` as entry point
  - `tools.py` for MCP tool definitions
- `tests/` — Top-level test directory
  - `unit/` — No containers needed
  - `integration/<server>/` — Per-server integration tests
  - `e2e/` — Cross-server end-to-end
  - `performance/` — Benchmarks
  - `fixtures/` — Shared test fixtures
  - `test-data/` — Sample documents
- `doc_v3/` — Documentation mirroring doc_v2 style
- `plans/llm-wiki/` — Plan system

### index.md in Every Folder
Every non-leaf folder must contain an `index.md` for routing:
- Table of contents for sub-items
- Quick description of each file
- Cross-references to related sections

## Test Standards

### Minimum Test Counts per Component
| Component Type | Unit Tests | Integration Tests | Edge Cases |
|----------------|-----------|-------------------|------------|
| MCP Server (single) | 10+ | 20+ | 5+ |
| MCP Server (complex) | 20+ | 40+ | 10+ |
| Pipeline | 30+ | 30+ | 10+ |

### Test Requirements
- Tests written alongside code, never after
- Test file named `test_<module>.py` next to source or in `tests/`
- Deterministic: fixed seeds, content-hash assertions
- Idempotent: clean setup/teardown
- At least one edge case per tool (empty input, missing resource, large batch)
- Docker profiles for selective container startup

### Coverage
- Minimum 80% line coverage (target 88%)
- Minimum 70% branch coverage (target 80%)
- Critical paths (smart_query, ingest, search) at 90%+
- Enforced in CI via `coverage report --fail-under=80`

## PR Checklist
- [ ] All tests pass (unit + integration)
- [ ] No new lint warnings
- [ ] Coverage >= 80% (check with `coverage report`)
- [ ] Documentation updated (doc_v3 and/or code docstrings)
- [ ] STATUS_V3.md updated if task completed
- [ ] CHANGELOG.md entry added
- [ ] `index.md` files updated if new files added to a directory

## Documentation
- Follow `doc_v2/` style: mermaid diagrams, tables, code references with line numbers
- Prefer CODE REFERENCES (`startLine:endLine:filepath`) over markdown code blocks when citing existing code
- Use markdown code blocks with language tags for new/proposed code
- Every architectural diagram uses mermaid flowchart (no external images)
- Docs live in `doc_v3/` and stay with the project
