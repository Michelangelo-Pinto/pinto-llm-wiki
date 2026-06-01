# MCP Server Architecture v4

pinto-llm-wiki v4 uses 3 independent MCP servers plus Qdrant vector DB, running in 4 Docker containers.

## Overview

```
Agent (Cursor IDE / LLM)
 │
 ├── SSE :8001 → Qdrant MCP ────→ Qdrant DB :6334 (semantic search)
 ├── SSE :8002 → Ingestion Pipeline ─→ Qdrant DB :6334 (document storage)
 │                                    └→ Tesseract (in-process OCR)
 └── SSE :8003 → Tesseract MCP (agent-facing OCR)
```

The knowledge base lives on the filesystem at `knowledge/`, organized as markdown by category with `index.md` routing.

## Service Design

### Why Separate MCP Servers?

| Principle | Implementation |
|-----------|---------------|
| **Separation of concerns** | Each MCP server owns one domain (search, ingestion, OCR) |
| **Independent scaling** | Servers can be restarted independently |
| **MCP-native** | Standard FastMCP SSE transport for Cursor IDE integration |
| **Direct communication** | Intra-service calls use native libraries (`qdrant-client`, `pytesseract`), not MCP |

### Communication Patterns

1. **Agent → MCP Server**: SSE (Server-Sent Events) via FastMCP
2. **Qdrant MCP → Qdrant**: `qdrant-client` library, REST :6334
3. **Ingestion Pipeline → Qdrant**: `qdrant-client` library, REST :6334
4. **Ingestion Pipeline → Tesseract**: `pytesseract` in-process (no HTTP/SSE overhead for batch processing)

## Collections

Qdrant stores one collection for document chunks. For full schema details, see [Qdrant Vector DB](qdrant-vector-db.md).

| Collection | Used by | Purpose |
|------------|---------|---------|
| `documents` | Ingestion Pipeline | Ingested document chunks for semantic search |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| External Qdrant | Native KNN, payload filtering. Replaces embedded vector engine from v2. |
| Separate MCP servers | Each domain is an independent service with its own Dockerfile and lifecycle. |
| Tesseract over PaddleOCR | 10x smaller image (~300 MB vs 5 GB), 8x faster CPU inference, no GPU/PyTorch dependency. |
| Direct pytesseract in pipeline | No MCP overhead for batch document processing. tesseract-mcp is for agent-facing OCR. |
| File-system knowledge base | Knowledge stored as markdown in `knowledge/`. No database-backed wiki needed. |
| all-MiniLM-L6-v2 | 384-dim embeddings, fast, consistent across all services. |
| `documents` collection | Single Qdrant collection for all ingested content. Filterable by `file_type`, `source_file`, etc. |
