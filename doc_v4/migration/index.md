# Migration: v3 → v4

Guide for migrating from pinto-llm-wiki v3 (Wiki.js-based) to v4 (file-system knowledge base).

## What Changed

| Aspect | v3 | v4 |
|--------|----|----|
| Containers | 8 (PostgreSQL + Wiki.js + 4 MCP + Qdrant) | 4 (3 MCP + Qdrant) |
| MCP servers | 4 (Wiki.js MCP + Qdrant + Ingestion + Tesseract) | 3 (Qdrant + Ingestion + Tesseract) |
| Total tools | ~65 | 22 |
| Knowledge store | Wiki.js + PostgreSQL | File-system `knowledge/` |
| Wiki.js MCP | 43 tools (CRUD, graph, hierarchy, health, etc.) | Removed |
| Page lifecycle | Wiki.js GraphQL CRUD | Filesystem MD read/write |
| Semantic search | `wikijs_smart_query` (RRF fusion) | `qdrant_search` |
| Keyword search | `wikijs_search_pages` | `Grep` on filesystem |
| Qdrant collections | `wiki_pages` + `documents` | `documents` only |
| SQLite databases | `pinto_llm_mappings.db` + `ingestion.db` | `ingestion.db` only |
| Backlinks / Graph | SQLite-based, auto-synced | Filesystem links in markdown |

## Removed Features

The following v3 features are not present in v4:

- **BacklinkIndex**: Cross-reference tracking between pages (replaced by explicit markdown links)
- **Page graph**: BFS/SP graph traversal (no longer applicable)
- **Wiki health checks**: Orphan detection, stale pages (can be reimplemented via `Grep` + `Glob`)
- **Import/Export**: Markdown roundtrip via Wiki.js GraphQL (files are already markdown on disk)
- **File-to-page mapping**: `FileMapping` SQLite table (filesystem is the source of truth)
- **Tag management**: Wiki.js tag system (tags in frontmatter YAML of MD files)
- **Spaces**: Wiki.js space organization (replaced by `knowledge/` directory hierarchy)

## Tool Mapping

| v3 Tool | v4 Replacement |
|---------|---------------|
| `wikijs_create_page` | `Write` to `knowledge/cat/sub/file.md` |
| `wikijs_update_page` | `StrReplace` on file |
| `wikijs_get_page` | `Read` file |
| `wikijs_bulk_get_pages` | Multiple `Read` calls |
| `wikijs_search_pages` | `Grep` in `knowledge/` |
| `wikijs_smart_query` | `qdrant_search` + `Read` |
| `wikijs_append_to_page` | `StrReplace` (append) on file |
| `wikijs_get_page_children` | `Glob` in directory |
| `wikijs_get_page_stats` | `Grep` for frontmatter |
| `wikijs_create_repo_structure` | `Shell mkdir -p` + `Write` index.md |
| `wikijs_wiki_health` | Manual `Grep`/`Glob` lint (not yet automated) |

## Unchanged

| Feature | Status |
|---------|--------|
| Qdrant MCP (8 tools) | Unchanged |
| Ingestion Pipeline (7 tools) | Unchanged |
| Tesseract MCP (7 tools) | Unchanged |
| Docker Compose profiles | Simplified (test/integration) |
| SSE transport | Unchanged |
| Embedding model (all-MiniLM-L6-v2, 384-dim) | Unchanged |
| Ingestion idempotency (SHA-256) | Unchanged |

## Docker Stack Changes

```bash
# v3: 8 containers
docker compose up -d   # Started db, wiki, setup, pinto-llm-wiki, qdrant-db, qdrant-mcp, ingestion-pipeline, tesseract-mcp

# v4: 4 containers
docker compose up -d   # Starts qdrant-db, qdrant-mcp, ingestion-pipeline, tesseract-mcp
```

The `.env` file no longer needs `POSTGRES_PASSWORD`, `WIKIJS_PASSWORD`, `MCP_PORT`, or any Wiki.js variables.

## Port Changes

| Port | v3 | v4 |
|------|----|----|
| 8000 | Wiki.js MCP | Removed |
| 3000 | Wiki.js UI | Removed |
| 5432 | PostgreSQL | Removed |
| 8001 | Qdrant MCP | Qdrant MCP |
| 8002 | Ingestion Pipeline | Ingestion Pipeline |
| 8003 | Tesseract MCP | Tesseract MCP |
| 6333-6334 | Qdrant DB | Qdrant DB |
