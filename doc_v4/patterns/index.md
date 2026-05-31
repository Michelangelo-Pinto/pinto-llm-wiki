# Patterns

Code patterns and design conventions across the v4 multi-MCP ecosystem.

## Quick Navigation

| Document | Description | Read when |
|----------|-------------|-----------|
| [Tool Structure](tool-structure.md) | Canonical tool pattern, auth, registration, JSON returns | Understanding how tools work across all 4 servers |
| [GraphQL and DB](graphql-and-db.md) | Query constants, parallel gather, mutations, SQLite lifecycle | Working with Wiki.js GraphQL or SQLite |
| [Caching and Hooks](caching-and-hooks.md) | Stats cache, BacklinkIndex, Qdrant indexing, fire-and-forget hooks | Understanding cache layers and side effects |

## Design Philosophy

1. **Simplicity over premature optimization**: Cache only when measured performance requires it
2. **Fire-and-forget hooks**: Side effects (backlinks, stats invalidation) must not fail the primary operation
3. **Explicit session control**: One SQLite session per operation, always closed in `finally`
4. **Uniform error handling**: All tools return JSON errors, never raise to the MCP framework
5. **Lazy cross-module imports**: Heavy deps (SentenceTransformer, QdrantClient) imported inside functions

## Communication Patterns

### Agent-to-Server: SSE

All 4 MCP servers expose SSE transport for Cursor/Claude integration on ports 8001-8004.

### Server-to-Backend: Direct Libraries

| From | To | Library |
|------|----|---------|
| Wiki.js MCP | Wiki.js | httpx (GraphQL) |
| Wiki.js MCP | Qdrant | qdrant-client |
| Qdrant MCP | Qdrant | qdrant-client |
| Ingestion Pipeline | Qdrant | qdrant-client |
| Ingestion Pipeline | Tesseract | pytesseract (in-process) |
| Tesseract MCP | Tesseract | pytesseract |

## Testing Pattern

Tests import tool functions directly (not via SSE) for determinism and speed. SSE transport is smoke-tested in stack health tests. See [Testing Guide](../reference/testing.md).

## Related Sections

- [Architecture](../architecture/index.md) — System design and server registry
- [Features](../features/index.md) — Feature catalog by priority
- [MCP Servers](../mcp-servers/index.md) — Per-server tool catalogs
- [Tool Catalog](../reference/tool-catalog.md) — All 26 tools with signatures
