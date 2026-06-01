# Architecture

v4 distributed architecture with Qdrant vector DB, Tesseract OCR, and 3 independent MCP servers. Knowledge base is file-system based (`knowledge/`).

## Quick Navigation

| Document | Description | Read when |
|----------|-------------|-----------|
| [System Overview](system-overview.md) | 4 containers, data flow, startup order, volumes, networks | Understanding the full stack |
| [Data Flow](data-flow.md) | Sequence diagrams for all major operations: semantic query, document ingestion, OCR | Understanding request lifecycles |
| [MCP Server Registry](mcp-server-registry.md) | Per-server catalog: containers, ports, dependencies | Looking up a specific server's config |
| [Qdrant Vector DB](qdrant-vector-db.md) | Collection schema, HNSW config, backup, embedding model | Understanding vector search internals |
| [Ingestion Pipeline Design](ingestion-pipeline-design.md) | Pipeline, OCR routing, chunking algorithm, idempotency | Understanding document processing |
| [Modules](modules.md) | Python module map across all 3 repositories, per-module descriptions | Finding where code lives |
| [Database](database.md) | SQLite models, Qdrant collections, session patterns | Understanding data storage |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| External Qdrant | Native KNN, payload filtering. Replaces embedded vector engine. |
| Separate MCP servers | Each domain (search, ingestion, OCR) is an independent service. |
| Tesseract over PaddleOCR | 10x smaller image, 8x faster CPU, no GPU/PyTorch dependency. ~300 MB vs 5 GB. |
| Direct library for pipeline | Ingestion uses pytesseract directly (no MCP overhead for batch processing). |
| all-MiniLM-L6-v2 | 384-dim, fast, Qdrant's default model. Consistent across all services. |
| File-system knowledge base | Knowledge stored as markdown in `knowledge/`, organized by category with `index.md` routing. |

## Agent Reading Order

For an LLM agent to understand the v4 system:

1. **[System Overview](system-overview.md)** — The 4-container stack, data flow diagrams, and startup order.
2. **[MCP Server Registry](mcp-server-registry.md)** — Which server does what, which ports, what dependencies.
3. **[Qdrant Vector DB](qdrant-vector-db.md)** — How semantic search works in v4.
4. **[Ingestion Pipeline Design](ingestion-pipeline-design.md)** — How documents are processed end-to-end.
5. **[Database](database.md)** — What's stored in SQLite vs Qdrant.

**[Modules](modules.md)** is for developers who need to find specific source files.

## Related Sections

- [MCP Servers](../mcp-servers/index.md) — Per-server tool catalogs
- [Patterns](../patterns/index.md) — Code conventions and communication patterns
