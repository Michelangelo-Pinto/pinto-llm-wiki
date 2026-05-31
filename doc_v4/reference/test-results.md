# Test Results

> **Last run:** 2026-05-24 via `test-runner` container (`test` profile).

## Suite Summary

| Suite | Test Count | Passed | Failed | Skipped | Duration |
|-------|-----------|--------|--------|---------|----------|
| Unit | ~109 | — | — | — | < 5s (no Docker) |
| Qdrant Integration | 26 | 26 | 0 | 0 | ~35s |
| Ingestion E2E | 27 | 27 | 0 | 0 | ~32s |
| Performance | 7 | 7 | 0 | 0 | ~71s |
| Smoke | ~37 | — | — | — | Requires full stack |
| Stack Integration | ~10 | — | — | — | Requires full stack |
| Wiki Regression | ~10 | — | — | — | Requires full stack |
| **Fast profile total** | **60** | **60** | **0** | **0** | ~104s |
| **Unit total** | **~109** | — | — | — | < 5s |

### All tests passing

All 60 fast-profile tests (Qdrant integration + E2E + performance) pass. The previously known failure `test_delete_nonexistent_collection` has been fixed — the delete function now uses idempotent semantics, returning `{"status": "not_found"}` for non-existent collections instead of an error.

Stack and regression suites require `docker compose up -d` plus `--profile integration`. Run separately when the full 5-container stack is available.

## How to Reproduce

```bash
# 1. Fast tests (Qdrant only)
docker compose --profile test run --rm test-runner \
  pytest tests/integration/qdrant/ tests/e2e/ tests/performance/ -v \
  -m "integration or e2e or performance" --tb=short

# 2. Full-stack tests
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/regression/ -v \
  -m "integration_stack or regression" --tb=short
```

See [Testing Guide](testing.md) for suite details and markers.

## v2 baseline

The last v2 monolithic test run (`test_all_tools.py`) reported **79/79 passed**. v3 replaces that script with pytest suites across multiple MCP servers. Legacy runner: [`mcp-servers/wiki-js-mcp/scripts/test_all_tools.py`](../../mcp-servers/wiki-js-mcp/scripts/test_all_tools.py).
