# Architecture

v3 distributed architecture with Qdrant vector DB, Tesseract OCR, and multi-MCP servers.

## Quick Navigation

| Document | Description | Read when |
|----------|-------------|-----------|
| [System Overview](system-overview.md) | 8 containers, data flow, startup order, volumes, networks | Understanding the full stack |
| [Multi-MCP Architecture](multi-mcp-architecture.md) | Service mesh design, communication patterns, rationale | Understanding why 4 servers instead of 1 |
| [MCP Server Registry](mcp-server-registry.md) | Per-server catalog: containers, ports, dependencies | Looking up a specific server's config |
| [Qdrant Vector DB](qdrant-vector-db.md) | Collection schema, HNSW config, backup, embedding model | Understanding vector search internals |
| [Modules](modules.md) | Python module map across all 4 repositories, per-module descriptions | Finding where code lives |
| [Database](database.md) | SQLite models, Qdrant collections, session patterns, v2 vs v3 changes | Understanding data storage |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| External Qdrant | Replaces embedded vector engine. Native KNN, payload filtering, multi-collection. |
| Separate MCP servers | Each domain (wiki, search, OCR, ingestion) is an independent service. |
| Tesseract over PaddleOCR | 10x smaller image, 8x faster CPU, no GPU/PyTorch dependency. ~300 MB vs 5 GB. |
| Direct library for pipeline | Ingestion uses pytesseract directly (no MCP overhead for batch processing). |
| Qdrant-client in wikijs-mcp | Direct Qdrant calls for smart_query latency. MCP server also available for agent use. |
| all-MiniLM-L6-v2 | 384-dim, fast, Qdrant's default model. Consistent across all services. |

## Agent Reading Order

For an LLM agent to understand the v3 system:

1. **[System Overview](system-overview.md)** — The 8-container stack, data flow diagrams, and startup order.
2. **[Multi-MCP Architecture](multi-mcp-architecture.md)** — Why 4 independent servers, how they communicate.
3. **[MCP Server Registry](mcp-server-registry.md)** — Which server does what, which ports, what dependencies.
4. **[Qdrant Vector DB](qdrant-vector-db.md)** — How semantic search works in v3.
5. **[Database](database.md)** — What's stored in SQLite vs Qdrant.

**[Modules](modules.md)** is for developers who need to find specific source files.

## Related Sections

- [MCP Servers](../mcp-servers/index.md) — Per-server tool catalogs
- [Features](../features/index.md) — Feature catalog by priority and server
- [Patterns](../patterns/index.md) — Code conventions and communication patterns
