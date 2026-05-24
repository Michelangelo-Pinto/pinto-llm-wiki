# MCP Server Documentation

Four independent MCP servers forming the wiki-js-mcp v3 ecosystem.

## Server Overview

| Server | Document | Tools | Delegates To |
|--------|----------|-------|--------------|
| Wiki.js MCP | [wiki-js-mcp.md](wiki-js-mcp.md) | ~43 | Qdrant DB |
| Qdrant MCP | [qdrant-mcp.md](qdrant-mcp.md) | 8 | Qdrant DB |
| Tesseract MCP | [tesseract-mcp.md](tesseract-mcp.md) | 7 | — |
| Ingestion Pipeline | [ingestion-pipeline-mcp.md](ingestion-pipeline-mcp.md) | 7 | Qdrant DB, Tesseract |

## Communication Map

```mermaid
flowchart TD
    WMCP[Wiki.js MCP] -->|"qdrant-client"| Qdrant[(Qdrant DB)]
    QMCP[Qdrant MCP] -->|"qdrant-client"| Qdrant
    IMCP[Ingestion Pipeline] -->|"qdrant-client"| Qdrant
    IMCP -->|"pytesseract"| Tesseract[Tesseract binary]
```

## Design Philosophy

- **Separation of concerns**: Each MCP server owns one domain
- **Independent scaling**: Servers can be restarted independently
- **MCP-native**: Standard FastMCP SSE transport for Cursor integration
- **Direct communication**: Intra-service calls use native libraries (qdrant-client, pytesseract), not MCP

## Related Sections

- [Architecture](../architecture/index.md) — System design and server registry
- [Tool Catalog](../reference/tool-catalog.md) — All ~65 tools with full signatures
- [Features](../features/index.md) — Feature catalog by priority
- [Guides](../guides/index.md) — Workflows and operations
