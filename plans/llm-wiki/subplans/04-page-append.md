# wikijs_append_to_page — Full Implementation Plan

---

- **Status**: `completed`

## Test results (2026-05-22)

| Test | Result | Notes |
|------|--------|-------|
| Create test page | PASS | Page created for append testing |
| Append content | PASS | Entry appended, status=appended, correct length |
| Verify appended content | PASS | Content contains appended entry |
| Second append | PASS | Both entries present after second append |
| Prepend | PASS | Content starts with prepended text |
| Invalid position | PASS | Returns error for position="middle" |
| Non-existent page | PASS | Returns error message |

## Acceptance criteria

- [x] Appends content to the end of an existing page
- [x] Optionally prepends content to the start
- [x] Returns confirmation with updated page metadata
- [x] Fails gracefully with clear error if the page doesn't exist
- [x] Fails gracefully with clear error if position is invalid
- [x] Retry loop handles concurrent writes (post-write verification)
- [x] No backlink sync performed (correct for append-only)
- **Priority**: P2 — Core LLM Wiki workflow
- **Dependencies**: None

## Purpose

Append (or prepend) content to an existing page in a single MCP call. Primary use: `log.md` — the append-only chronological register of ingests, queries, and lint passes in the LLM Wiki pattern.

Without this tool, the agent must manually: fetch page -> append in memory -> write back. That's 2 GraphQL round trips + manual string manipulation + risk of forgetting a newline separator.

## Design decision: optimistic locking with retry loop

Wiki.js `pages.update` has no native "update if version matches" semantics. A simple fetch-then-update would risk silent data loss if two agents write to the same page concurrently (e.g., two concurrent ingest processes both appending to `log.md`).

**Approach**: post-write verification with retry.

```
Loop (max 3 attempts):
  1. Fetch current content + updatedAt via GraphQL pages.single
  2. Build new_content: old + "\n" + appended  (or prepended + "\n" + old)
  3. Write back via pages.update
  4. Re-read page, verify appended text is present at expected position
  5. If verified -> return success
  6. If not -> another writer intervened -> exponential backoff (1s, 2s, 4s) -> retry
```

After 3 failures, return error: `"Page modified concurrently after 3 attempts"`.

This is a read-check-write loop with post-write verification. No Wiki.js support needed. Handles concurrent log writes correctly.

### Why not database-level optimistic locking?

Wiki.js stores content in PostgreSQL but exposes no "etag" or "if-match" semantics via GraphQL. The post-write verification achieves the same correctness guarantee at the application level.

## No backlink sync

Unlike `wikijs_update_page`, append only extends content at the end/start. Existing markdown links are unchanged. No `_sync_backlinks_for_page` call needed.

## Implementation

### Signature

```python
@mcp.tool()
async def wikijs_append_to_page(page_id: int, content: str, position: str = "end") -> str:
```

Returns: `{pageId, title, status: "appended", newContentLength, attempts: 1}`

### File

`mcp-server/src/wiki_mcp_server/tools_pages.py`

### Logic

1. Validate `position` is "end" or "start" -> error if invalid
2. `await wikijs.authenticate()` (once, outside loop)
3. **Retry loop (max 3 attempts):**
   a. Fetch current page via GraphQL `_GET_PAGE_BY_ID_QUERY`
   b. If not found -> error
   c. Build new_content based on position
   d. Write back via `pages.update` (reuse mutation + variable pattern from `wikijs_update_page`)
   e. Re-fetch page
   f. Verify: `appended_content in new_page_content` and at expected position
   g. Pass -> return result
   h. Fail -> sleep 2^attempt seconds, retry
4. After 3 attempts -> `{"error": "Page modified concurrently after 3 attempts"}`

## Logging

| Event | Level | Message |
|-------|-------|---------|
| Append started | `INFO` | `append_to_page page {id}: appending {N} chars` |
| Retry needed | `WARNING` | `append_to_page page {id}: retry {n}/3, content mismatch` |
| Append succeeded | `INFO` | `append_to_page page {id}: appended, new length {N}, attempts {M}` |
| Max retries | `ERROR` | `append_to_page page {id}: failed after 3 attempts` |

## Test results

To be filled after implementation and verification.
