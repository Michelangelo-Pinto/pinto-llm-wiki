# Test Results

> **Last run:** 2026-05-24 via `test-runner` container (`test` profile).

## Suite Summary

| Suite | Test Count | Passed | Failed | Skipped | Duration |
|-------|-----------|--------|--------|---------|----------|
| Unit | ~109 | — | — | — | < 5s (no Docker) |
| Qdrant Integration | 26 | 26 | 0 | 0 | ~35s |
| Ingestion E2E | 27 | 27 | 0 | 0 | ~32s |
| Performance | 7 | 7 | 0 | 0 | ~71s |
| Smoke | ~25 | — | — | — | Requires full stack |
| Stack Integration | ~10 | — | — | — | Requires full stack |
| **Fast profile total** | **60** | **60** | **0** | **0** | ~104s |
| **Unit total** | **~109** | — | — | — | < 5s |

### All tests passing

All 60 fast-profile tests (Qdrant integration + E2E + performance) pass.

Stack and smoke suites require `docker compose up -d` plus `--profile integration`. Run separately when the full 4-container stack is available.

## How to Reproduce

```bash
# 1. Fast tests (Qdrant only)
docker compose --profile test run --rm test-runner \
  pytest tests/integration/qdrant/ tests/e2e/ tests/performance/ -v

# 2. Full-stack tests (requires docker compose up -d first)
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/smoke/ -v -m "integration_stack or smoke"
```
