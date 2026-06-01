# Patterns

Code patterns and design conventions across the v4 MCP ecosystem.

## Current v4 Patterns

### Tool Structure

Every MCP tool follows a consistent pattern across all 3 servers. See [Tool Structure](tool-structure.md) for full details including the canonical tool signature, registration, and error handling.

### Qdrant Embedding

- Model: `all-MiniLM-L6-v2` (384-dim vectors, Cosine distance)
- Pre-loaded at Docker build time — no cold start
- Used by: `qdrant-mcp` (search, upsert), `ingestion-pipeline` (embed chunks)

### Ingestion Chunking

- Target: 1500 chars per chunk, 200 char overlap
- Hard cap: 2500 chars per chunk
- Section-aware: respects PDF page boundaries, markdown headings
- See [Ingestion Pipeline Design](../architecture/ingestion-pipeline-design.md)

### Idempotency

- SHA-256 content hash prevents re-ingestion of identical files
- `force=True` flag bypasses idempotency check
- Document tracking in `ingestion.db` SQLite database

### Knowledge Base File Operations

- Agent writes `.md` files directly to `knowledge/` with `Write`
- Searches via `Grep` (keyword) or `qdrant_search` (semantic)
- Every directory has an `index.md` for routing
- Content files excluded from git (only `index.md` tracked)

## Archived v3 Patterns

The following v3 patterns were removed in v4:

- `graphql-and-db.md` — Wiki.js GraphQL queries and SQLite patterns (Wiki.js MCP removed)
- `caching-and-hooks.md` — BacklinkIndex caching and fire-and-forget hooks (Wiki.js MCP removed)

These are archived in `plans/v4-migration/archived-docs/`.

## Related Documents

- [MCP Servers](../mcp-servers/index.md) — Per-server documentation
- [Database](../architecture/database.md) — SQLite and Qdrant data models
