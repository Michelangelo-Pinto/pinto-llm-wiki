# Decision Log

Design and architecture decisions made during v3 completion.

## Template

```markdown
### [Date] — [Task NN]: [Decision Title]

**Decision:** [What was decided]

**Rationale:** [Why this choice]

**Alternatives considered:**
- [Alternative 1] — [Why rejected]
- [Alternative 2] — [Why rejected]
```

## Decisions

### 2026-05-24 — Task 01: Pre-download embedding model placement

**Decision:** Place the `RUN python3 -c "..."` command immediately after `pip install` and before `RUN useradd`, in both Dockerfiles.

**Rationale:** This ensures the model is downloaded in a separate Docker layer that can be cached independently, and the model files end up in the correct filesystem location before the non-root user is created.

**Alternatives considered:**
- Using a separate script file — rejected because a one-liner is simpler and avoids an extra COPY step

### 2026-05-24 — Task 02: BacklinkIndex indexes via __table_args__

**Decision:** Added both indexes via `__table_args__` on the `BacklinkIndex` model, using `Index()` imported from SQLAlchemy. Indexes auto-create on next startup via existing `Base.metadata.create_all(engine)`.

**Rationale:** Using `__table_args__` is the standard SQLAlchemy declarative pattern for table-level constraints. The indexes are lightweight (B-tree on integer columns) and will improve BFS graph traversal performance at scale.

### 2026-05-24 — Task 03: CI workflow verified as-is

**Decision:** The existing `.github/workflows/test.yml` is complete and correct. No modifications needed.

**Rationale:** The workflow already covers all test suites with appropriate Docker profiles, splits fast/stack jobs, and limits stack tests to main branch pushes.

### 2026-05-24 — Task 07: Idempotent delete for non-existent collections

**Decision:** `qdrant_delete_collection` now checks collection existence via `client.get_collection()` before attempting deletion. If the collection does not exist, returns `{"status": "not_found"}` instead of an error.

**Rationale:** Delete is naturally idempotent — the desired end state (collection does not exist) is achieved regardless of whether it existed before. Returning an error for a non-existent collection is misleading to LLM agents.

### 2026-05-24 — Task 04: SSE smoke test client approach

**Decision:** Implemented a custom `McpSseClient` using `httpx` that handles the FastMCP SSE transport protocol (GET /sse → parse endpoint event → POST JSON-RPC to message endpoint).

**Rationale:** Using `httpx` (already a dependency) keeps the test lightweight. The custom client is minimal (~80 lines) and serves exactly the smoke testing needs.

### 2026-05-24 — Task 06: Stack/regression test fixes

**Decision:** Fixed three bugs in existing stack and regression tests: wrong function name (`ingest_status` → `ingest_get_status`), wrong parameter name (`collection_name` → `collection`), buggy async sleep helper, and deprecated `asyncio.get_event_loop().run_until_complete()`.

**Rationale:** These bugs were identified by cross-referencing test code against actual source signatures. All fixes verified against tool function definitions from the exploration agent report.
