# Multi-MCP Architecture

Distributed service architecture for wiki-js-mcp v3.

## Overview

v3 replaces the monolithic v2 MCP server with 4 independent MCP servers, each owning a specific domain:

```
┌─────────────────────────────────────────────────────────────┐
│                      LLM Agent / Cursor                     │
└────┬──────────┬──────────┬──────────┬───────────────────────┘
     │SSE       │SSE       │SSE       │SSE
     ▼          ▼          ▼          ▼
┌─────────┐┌─────────┐┌─────────┐┌──────────────┐
│Wiki.js  ││Qdrant   ││Tesseract││Ingestion     │
│MCP :8000││MCP :8001││MCP :8003││Pipeline :8002│
└────┬────┘└────┬────┘└─────────┘└──────┬───────┘
     │GraphQL   │qdrant-         pytesseract│qdrant-client
     │          │client          (in-proc)  │
     ▼          ▼                           ▼
┌─────────┐┌──────────┐              ┌──────────┐
│Wiki.js  ││Qdrant DB │              │Qdrant DB │
│:3000    ││REST :6334│              │REST :6334│
└────┬────┘└──────────┘              └──────────┘
     │
     ▼
┌──────────┐
│PostgreSQL│
│:5432     │
└──────────┘
```

## Service Design

### Why Separate MCP Servers?

| Principle | Implementation |
|-----------|---------------|
| **Separation of concerns** | Each MCP server owns one domain (wiki, search, OCR, ingestion) |
| **Independent scaling** | Servers can be restarted independently without affecting others |
| **MCP-native** | Standard FastMCP SSE transport for Cursor IDE integration |
| **Direct communication** | Intra-service calls use native libraries (`qdrant-client`, `pytesseract`), not MCP |

### Communication Patterns

1. **Agent → MCP Server**: SSE (Server-Sent Events) via FastMCP
2. **Wiki.js MCP → Wiki.js**: GraphQL API over HTTP
3. **Wiki.js MCP → Qdrant**: `qdrant-client` library, REST :6334
4. **Qdrant MCP → Qdrant**: `qdrant-client` library, REST :6334
5. **Ingestion Pipeline → Qdrant**: `qdrant-client` library, REST :6334
6. **Ingestion Pipeline → Tesseract**: `pytesseract` in-process (no HTTP/SSE overhead for batch processing)

## Collections

### `wiki_pages`

Used by Wiki.js MCP for semantic search via `wikijs_smart_query`.

**Schema:**
- Vector size: 384 (all-MiniLM-L6-v2)
- Distance: Cosine
- Payload: `page_id`, `title`, `path`, `locale`

### `documents`

Used by Ingestion Pipeline for ingested document chunks.

**Schema:**
- Vector size: 384 (all-MiniLM-L6-v2)
- Distance: Cosine
- Payload: `document_id`, `chunk_index`, `file_type`, `source_path`

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| External Qdrant | Replaces embedded vector engine. Native KNN, payload filtering, multi-collection. |
| Separate MCP servers | Each domain is an independent service with its own Dockerfile and lifecycle. |
| Tesseract over PaddleOCR | 10x smaller image (~300 MB vs 5 GB), 8x faster CPU inference, no GPU/PyTorch dependency. |
| Direct pytesseract in pipeline | No MCP overhead for batch document processing. tesseract-mcp is for agent-facing OCR. |
| Qdrant-client in wikijs-mcp | Direct Qdrant calls for `smart_query` latency. Qdrant MCP is for agent-facing vector operations. |
| all-MiniLM-L6-v2 | 384-dim embeddings, fast, Qdrant's default model. Consistent across all services. |
