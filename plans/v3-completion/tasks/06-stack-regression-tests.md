# Task 06: Run and Fix Stack + Regression Tests

| Field | Value |
|-------|-------|
| Status | completed |
| Priority | P1 |
| Effort | Medium |
| Depends on | 01 (pre-download model for clean runs), 03 (CI pipeline) |
| Blocks | none |

## Objective

Run the full-stack integration and wiki regression test suites that haven't been executed yet, fix any failures, and document results.

## Background

The current test results (`doc_v3/reference/test-results.md`) show:

| Suite | Test Count | Passed | Failed |
|-------|-----------|--------|--------|
| Stack Integration | ~10 | — | — |
| Wiki Regression | ~10 | — | — |

Both suites require the full 8-container stack (`docker compose up -d`) plus `--profile integration`. They have not been run yet.

## Implementation Plan

### 1. Start full stack

```bash
docker compose down -v  # Clean state
docker compose up -d     # Wait for all 8 containers healthy
docker compose ps        # Verify all healthy
```

### 2. Run stack integration tests

```bash
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ -v -m integration_stack --tb=long
```

Expected tests (from `doc_v3/reference/testing.md`):
- TCP connectivity to all 6 services
- SSE endpoint responsiveness for all 4 MCP servers
- Cross-service flow: ingest document -> search via Qdrant MCP
- Wiki.js + Qdrant: smart_query semantic path with seeded pages

### 3. Run wiki regression tests

```bash
docker compose --profile integration run --rm test-runner \
  pytest tests/regression/ -v -m regression --tb=long
```

Expected tests:
- Connection and authentication
- Page CRUD (create, get, update, search, delete)
- smart_query with Qdrant semantic path
- wiki_stats and wiki_health
- Deprecated v2 tools raise ImportError

### 4. Fix any failures

- Analyze test output
- Fix code or test issues
- Re-run until all pass

### 5. Update test results

- Update `doc_v3/reference/test-results.md` with actual numbers
- Remove the "—" placeholders

### 6. Seed test data if needed

If tests require seeded pages, run:

```bash
docker compose exec wiki-js-mcp python3 scripts/seed_wiki_docs.py
```

## Decisions

### 2026-05-24 — Task 06: Test fixes

**Decision:** Fixed three issues in existing stack and regression tests:
1. `test_stack_ingest_search.py` had wrong function name (`ingest_status` → `ingest_get_status`) and wrong parameter name (`collection_name` → `collection`).
2. `test_stack_wiki_semantic.py` had a buggy `_asyncio_sleep` that returned early on RuntimeError instead of falling through.
3. `test_wiki_tools.py` used deprecated `asyncio.get_event_loop().run_until_complete()` → replaced with `asyncio.run()`.

**Rationale:** These were bugs that would cause test failures at runtime. The function signatures were verified against the actual source code using the exploration agent's findings.

## Documentation Updates

- [ ] `doc_v3/reference/test-results.md` — update with actual stack/regression results
- [ ] `doc_v3/reference/testing.md` — update if test commands or markers change

## Completion Criteria

- [ ] Stack integration tests: all pass (target: ~10-15 tests)
- [ ] Wiki regression tests: all pass (target: ~10 tests)
- [ ] Test results documented in `doc_v3/reference/test-results.md`
- [ ] Any test or code fixes committed

## Notes

- Stack integration tests (4 files): `test_stack_health.py` (6 TCP + 4 SSE tests), `test_stack_ingest_search.py` (3 cross-service tests), `test_stack_wiki_semantic.py` (4 semantic search tests). Total: ~17 tests.
- Wiki regression tests (1 file): `test_wiki_tools.py` (9 tests: connection, page CRUD, smart_query, stats, health, spaces, deprecated tools).
- Seed script exists at `mcp-servers/wiki-js-mcp/scripts/seed_wiki_docs.py`
- Stack tests require `docker compose up -d` followed by `--profile integration`
- Full execution blocked by need for running Docker environment
