# System Overview v4

wiki-js-mcp v4 is a 4-container Docker stack providing 3 independent MCP servers wrapping Qdrant vector search, Tesseract OCR, and document ingestion. **Wiki.js and PostgreSQL were removed in v4** — the knowledge base is now a file-system markdown hierarchy in `knowledge/`.

## Components

| Component | Container | Role | Port |
|-----------|-----------|------|------|
| **Qdrant DB** | `wikijs_qdrant` | Vector database (semantic search) | 6333 (gRPC) / 6334 (REST) |
| **Qdrant MCP** | `wikijs_qdrant_mcp` | 8 tools wrapping Qdrant REST API | 8001 |
| **Ingestion Pipeline** | `wikijs_ingestion` | Document processing with OCR | 8002 |
| **Tesseract MCP** | `wikijs_tesseract_mcp` | Agent-facing OCR tools | 8003 |

The knowledge base lives on the filesystem at `knowledge/`, organized by categories with `index.md` routing files.

## Data Flow

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant QMCP as Qdrant MCP :8001
    participant IMCP as Ingestion Pipeline :8002
    participant Qdrant as Qdrant DB :6334
    participant KB as knowledge/ (filesystem)

    Note over Agent,KB: Flow 1: Semantic Query
    Agent->>QMCP: qdrant_search("topic")
    QMCP->>Qdrant: search(documents, query_vector)
    Qdrant-->>QMCP: semantic results
    QMCP-->>Agent: JSON results with scores
    Agent->>KB: Read matching MD files

    Note over Agent,KB: Flow 2: Document Ingestion
    Agent->>IMCP: ingest_document("report.pdf")
    IMCP->>IMCP: detect type → extract → chunk → embed
    IMCP->>Qdrant: upsert(documents, vectors)
    Qdrant-->>IMCP: ok
    IMCP->>IMCP: log in SQLite
    IMCP-->>Agent: {"status": "completed", "chunks_created": 12}
    Agent->>KB: Write report.md in knowledge/ingested/
```

## Startup Order

1. `qdrant-db` starts — health check via gRPC :6333
2. `qdrant-mcp` starts after qdrant-db healthy — serves SSE on :8001
3. `ingestion-pipeline` starts after qdrant-db healthy — serves SSE on :8002
4. `tesseract-mcp` starts independently — serves SSE on :8003

## Volumes

| Volume | Mount | Purpose |
|--------|-------|---------|
| `qdrant_data` | `/qdrant/storage` | Qdrant vector data |
| `qdrant_snapshots` | `/qdrant/snapshots` | Qdrant backup snapshots |
| `shared_data` | `/data/shared` | Shared files (read-only for ingestion/tesseract) |
| `ingestion_data` | `/data` | Ingestion SQLite database (`ingestion.db`) |

## Network

All 4 containers share the `wikijs-net` bridge network. Inter-container communication uses Docker service names: `qdrant-db:6334`, `qdrant-mcp:8001`, etc.

## MCP Transports

Each of the 3 MCP servers uses **SSE** (Server-Sent Events) via FastMCP:

```json
{
  "mcpServers": {
    "qdrant":     { "type": "sse", "url": "http://localhost:8001/sse" },
    "ingestion":  { "type": "sse", "url": "http://localhost:8002/sse" },
    "tesseract":  { "type": "sse", "url": "http://localhost:8003/sse" }
  }
}
```

## What Changed from v3

| Aspect | v3 | v4 |
|--------|-----|-----|
| Containers | 8 | 4 |
| MCP servers | 4 | 3 |
| Total tools | ~65 | 22 |
| Knowledge store | Wiki.js + PostgreSQL | Filesystem `knowledge/` |
| Wiki.js MCP | 43 tools | Removed |
| Page lifecycle | Wiki.js GraphQL CRUD | Filesystem MD read/write |
| Semantic search | Qdrant via wikijs_smart_query (RRF) | Qdrant via qdrant_search |
| Keyword search | wikijs_search_pages | Grep on filesystem |
| Document processing | Same (ingestion pipeline) | Same |
| OCR | Same (Tesseract MCP) | Same |

For more details on the 3-server design, see [Multi-MCP Architecture](multi-mcp-architecture.md).
