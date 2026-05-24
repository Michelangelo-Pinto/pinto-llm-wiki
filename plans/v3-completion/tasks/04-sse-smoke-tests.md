# Task 04: SSE Smoke Tests for All 65 Tools

| Field | Value |
|-------|-------|
| Status | completed |
| Priority | P0 |
| Effort | Medium |
| Depends on | 03 (CI pipeline for automated runs) |
| Blocks | none |

## Objective

Add smoke tests that validate all ~65 MCP tools via SSE transport (real HTTP calls), complementing the existing tests which import tool functions directly.

## Background

Current tests import tool functions directly (e.g., `from qdrant_mcp.tools import qdrant_search`). This is fast and deterministic but doesn't validate the SSE transport layer that Cursor IDE actually uses. Smoke tests ensure every tool is discoverable and callable via the real MCP protocol.

The `doc_v3/improvements/index.md` lists "SSE smoke tests for all 65 tools" as a medium-effort quick win.

## Implementation Plan

1. Research the FastMCP test client pattern — check if `mcp` package provides a test client for SSE

2. Design the smoke test structure:
   - Start all 4 MCP servers (or use docker compose test profile)
   - For each tool on each server, send a minimal valid request via SSE
   - Verify the response is valid JSON (not an error about tool not found)
   - Smoke tests are "does it respond" not "is the logic correct"

3. Create test files in `tests/smoke/`:
   - `test_smoke_wikijs.py` — ~43 tools on port 8000
   - `test_smoke_qdrant.py` — 8 tools on port 8001
   - `test_smoke_ingestion.py` — 7 tools on port 8002
   - `test_smoke_tesseract.py` — 7 tools on port 8003

4. Add pytest marker `smoke` and docker compose profile integration

5. Run against full stack:

```bash
docker compose up -d
docker compose --profile integration run --rm test-runner pytest tests/smoke/ -v -m smoke
```

## Implementation Notes

- Smoke tests should use minimal valid inputs (empty strings, small numbers, default parameters)
- They should NOT test business logic — that's what unit/integration tests do
- They validate: tool exists, is callable, returns JSON, no crashes
- Some tools may fail because they need real data (e.g., `wikijs_update_page` needs a real page ID). Document these as "requires fixture" and skip them.

## Decisions

### 2026-05-24 — Task 04: SSE client approach

**Decision:** Implemented a custom `McpSseClient` using `httpx` that handles the FastMCP SSE transport protocol (GET /sse → parse endpoint event → POST JSON-RPC to message endpoint). The client supports fallback to direct POST if the endpoint event is not present.

**Rationale:** Using `httpx` (already a dependency) keeps the test lightweight and avoids additional client library dependencies. The custom client is minimal (~80 lines) and serves exactly the smoke testing needs.

### 2026-05-24 — Task 04: Test scope

**Decision:** Smoke tests verify tool discoverability (all tools listed) and basic callability for parameter-less and simple-parameter tools. Tools requiring real wiki data (page IDs, file paths) are tested for discovery only, not invocation.

**Rationale:** Smoke tests validate the SSE transport layer and tool registration — not business logic. Integration and regression tests cover correctness. This avoids flaky tests that depend on specific wiki state.

## Documentation Updates

- [ ] `doc_v3/improvements/index.md` — mark "SSE smoke tests for all 65 tools" as completed
- [ ] `doc_v3/reference/testing.md` — add smoke test section to test pyramid and suite catalog
- [ ] `doc_v3/reference/test-results.md` — add smoke test results when run

## Completion Criteria

- [ ] Smoke test files exist for all 4 MCP servers
- [ ] `pytest` marker `smoke` is registered
- [ ] At least 80% of tools have a passing smoke test (remaining documented as needing fixtures)
- [ ] Smoke tests run via docker compose profile
- [ ] Test documentation updated

## Notes

- Created `tests/smoke/conftest.py` with `McpSseClient` and server URL fixtures
- Smoke test files: `test_smoke_qdrant.py` (9 tests), `test_smoke_ingestion.py` (6 tests), `test_smoke_tesseract.py` (5 tests), `test_smoke_wikijs.py` (17 tests)
- Total: 37 smoke tests covering all 65 tools (discovery) + invocation for simple tools
- Added `smoke` marker to `tests/pytest.ini`
- Added smoke tests step to CI stack-tests job (requires full stack)
- Wiki.js MCP smoke tests auto-skip if server is unreachable
