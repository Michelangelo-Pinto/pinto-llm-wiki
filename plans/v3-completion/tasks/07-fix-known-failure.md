# Task 07: Fix Known Test Failure

| Field | Value |
|-------|-------|
| Status | completed |
| Priority | P2 |
| Effort | Small |
| Depends on | none |
| Blocks | none |

## Objective

Fix the single known test failure: `test_delete_nonexistent_collection` in the Qdrant integration suite.

## Background

Current test results show 59/60 passing. The one failure:

| Test | Issue |
|------|-------|
| `test_delete_nonexistent_collection` | Expects error on delete of missing collection; behavior may differ by Qdrant client version |

The Qdrant client library (`qdrant-client`) may not raise an error when deleting a collection that doesn't exist, or the error type/format differs from what the test expects. This is a version compatibility issue.

## Implementation Plan

1. Locate the failing test:

```bash
grep -r "test_delete_nonexistent_collection" tests/
```

2. Read the test to understand what it expects

3. Check Qdrant client version and behavior:

```bash
docker compose exec qdrant-mcp python3 -c "
from qdrant_client import QdrantClient
c = QdrantClient(url='http://qdrant-db:6334')
try:
    c.delete_collection('nonexistent_collection_xyz')
    print('No error raised — test needs updating')
except Exception as e:
    print(f'Error raised: {type(e).__name__}: {e}')
"
```

4. Fix the test based on actual behavior:
   - If no error is raised (idempotent delete), update test to expect success
   - If error is raised but wrong type, update expected exception
   - If behavior is version-dependent, add version check or skip condition

5. Re-run to confirm fix:

```bash
docker compose --profile test run --rm test-runner \
  pytest tests/integration/qdrant/ -v -k "test_delete_nonexistent_collection"
```

## Decisions

### 2026-05-24 — Task 07: Idempotent delete for non-existent collections

**Decision:** `qdrant_delete_collection` now checks collection existence via `client.get_collection()` before attempting deletion. If the collection does not exist, returns `{"status": "not_found", "note": "Collection did not exist"}` instead of an error. The test was updated to expect `"not_found"` status rather than `"error"`.

**Rationale:** Delete is naturally idempotent — the desired end state (collection does not exist) is achieved regardless of whether it existed before. Returning an error for a non-existent collection is misleading to LLM agents, who would interpret it as an operation failure rather than "already in desired state."

## Documentation Updates

- [ ] `doc_v3/reference/test-results.md` — update to show 60/60 passing, remove known failure note

## Completion Criteria

- [ ] `test_delete_nonexistent_collection` passes
- [ ] Full Qdrant integration suite: 26/26 passing
- [ ] Test results documentation updated

## Notes

- Modified `mcp-servers/qdrant-mcp/src/qdrant_mcp/tools.py`: `qdrant_delete_collection` function
- Modified `tests/integration/qdrant/test_qdrant_mcp.py`: `test_delete_nonexistent_collection` test
- The function now uses `client.get_collection()` as a pre-check, catching `UnexpectedResponse` for missing collections
- The generic `except Exception` fallback remains for actual failures (network errors, etc.)
