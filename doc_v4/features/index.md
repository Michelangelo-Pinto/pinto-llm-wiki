# Features

Feature catalog for wiki-js-mcp v3, organized by priority level (P1–P4) and MCP server.

## Feature inventory

| Priority | Feature | Tools | Deep dive |
|----------|---------|-------|-----------|
| P1 | Bulk page read | `wikijs_bulk_get_pages` | [p1-foundation.md](p1-foundation.md) |
| P1 | Backlinks | `wikijs_get_backlinks`, `wikijs_rebuild_backlink_index` | [p1-foundation.md](p1-foundation.md) |
| P1 | Page stats | `wikijs_get_page_stats`, `wikijs_bulk_get_page_stats` | [p1-foundation.md](p1-foundation.md) |
| P2 | Append to page | `wikijs_append_to_page` | [p2-core.md](p2-core.md) |
| P2 | Tag management | `wikijs_search_by_tag`, `wikijs_list_all_tags`, `wikijs_set_page_tags`, `wikijs_filter_pages` | [p2-core.md](p2-core.md) |
| P2 | Smart query | `wikijs_smart_query` | [p2-core.md](p2-core.md) |
| P2 | Link graph | `wikijs_extract_page_links`, `wikijs_get_page_graph`, `wikijs_find_shortest_path` | [p2-core.md](p2-core.md) |
| P3 | Wiki health | `wikijs_wiki_health` | [p3-health.md](p3-health.md) |
| P3 | Recent changes | `wikijs_get_recent_changes` | [p3-health.md](p3-health.md) |
| P4 | Qdrant integration | `qdrant_search`, `qdrant_upsert_chunks` (Qdrant MCP) | [p4-scale.md](p4-scale.md) |
| P4 | Affected pages | `wikijs_get_affected_pages` | [p4-scale.md](p4-scale.md) |
| P4 | Wiki stats | `wikijs_wiki_stats` | [p4-scale.md](p4-scale.md) |

## Dependency graph

```mermaid
flowchart TD
    subgraph P1 [P1 — Foundation]
        bulk["bulk_get_pages\n(1 tool)"]
        backlinks["backlinks\n(2 tools)"]
        stats["page_stats\n(2 tools)"]
    end

    subgraph P2 [P2 — Core Workflow]
        append["append_to_page\n(1 tool)"]
        tags["tag management\n(4 tools)"]
        smart["smart_query\n(1 tool)"]
        graph["link graph\n(3 tools)"]
    end

    subgraph P3 [P3 — Health & Maintenance]
        health["wiki_health\n(1 tool)"]
        recent["recent_changes\n(1 tool)"]
    end

    subgraph P4 [P4 — Scale Optimizations]
        qdrant["Qdrant integration\n(Qdrant MCP)"]
        affected["affected_pages\n(1 tool)"]
        wiki_stats["wiki_stats\n(1 tool)"]
    end

    bulk -.-> backlinks
    bulk -.-> stats
    backlinks --> graph
    backlinks --> health
    backlinks --> affected
    stats --> smart
    bulk --> smart
    qdrant --> smart
    qdrant --> affected
    backlinks --> affected
    tags --> affected
    backlinks --> wiki_stats
```

Solid arrows: hard dependencies. Dotted arrows: soft dependencies.

## Design philosophy

1. **Metadata-first**: Use `get_page_stats` and `wiki_health` before reading full content
2. **Unified dashboards**: `wiki_health` (7 checks) and `wiki_stats` (aggregates) replace many small lint tools
3. **Search is core**: `smart_query` is the primary discovery tool; Qdrant provides semantic path
4. **Graph-awareness**: BacklinkIndex powers backlinks, graph traversal, health, and affected pages
5. **Proactive maintenance**: `get_affected_pages` automates impact discovery during ingestion
6. **External vectors**: Qdrant replaces embedded sentence-transformers; wiki-js-mcp image stays ~200 MB

## By Server

### Wiki.js MCP (~43 tools)

| Feature Area | Tools | Description |
|-------------|-------|-------------|
| Page CRUD | `create_page`, `update_page`, `get_page`, `search_pages` | Full lifecycle management |
| Spaces | `list_spaces`, `create_space` | Wiki.js space containers |
| Bulk Operations | `bulk_get_pages`, `bulk_get_page_stats` | Parallel reads (cap: 50) |
| Backlinks | `get_backlinks`, `rebuild_backlink_index` | Cross-reference tracking |
| Stats | `get_page_stats` | Metadata-first triage (word count, tags, links) |
| Append | `append_to_page` | Append/prepend with optimistic locking |
| Tags | `search_by_tag`, `list_all_tags`, `set_page_tags`, `filter_pages` | Hierarchical tag management |
| Smart Query | `smart_query` | Hybrid keyword + semantic (Qdrant) via RRF |
| Recent Changes | `get_recent_changes` | Time-windowed change tracking |
| Wiki Health | `wiki_health` | 7 checks: orphans, stale, link_density, untagged, etc. |
| Wiki Stats | `wiki_stats` | Aggregate dashboard (60s cache) |
| Affected Pages | `get_affected_pages` | 4-signal impact analysis (backlink, graph, semantic, tags) |
| Import/Export | `export_wiki`, `export_page`, `import_page`, `import_directory` | Markdown roundtrip with YAML frontmatter |
| Graph | `extract_page_links`, `get_page_graph`, `find_shortest_path` | BFS link graph traversal |
| Hierarchy | `create_repo_structure`, `create_nested_page`, `get_page_children`, `create_documentation_hierarchy` | Path-based nested pages |
| File Integration | `link_file_to_page`, `sync_file_docs`, `generate_file_overview`, `bulk_update_project_docs` | Code-to-wiki mapping |
| Deletion | `delete_page`, `batch_delete_pages`, `delete_hierarchy`, `cleanup_orphaned_mappings` | Safe deletion with cleanup |
| System | `connection_status`, `repository_context`, `manage_collections` | Connectivity and repo context |

### Qdrant MCP (8 tools)

| Feature Area | Tools | Description |
|-------------|-------|-------------|
| Collection Management | `create_collection`, `list_collections`, `collection_info`, `delete_collection` | Full lifecycle |
| Semantic Search | `search` | KNN with payload filters and score threshold |
| Data Operations | `upsert_chunks`, `delete_by_filter`, `scroll` | Point CRUD with batch support |

### Tesseract MCP (7 tools)

| Feature Area | Tools | Description |
|-------------|-------|-------------|
| Text Extraction | `ocr_extract_text` | OCR from images and PDFs |
| Document Analysis | `ocr_detect_document_type`, `ocr_process_document` | Classification + smart processing |
| Structured Output | `ocr_extract_hocr`, `ocr_get_confidence` | Positional HOCR + per-word confidence |
| Preprocessing | `ocr_preprocess_and_extract` | Grayscale, deskew, denoise, sharpen |
| Configuration | `ocr_get_languages` | List installed language packs |

### Ingestion Pipeline (7 tools)

| Feature Area | Tools | Description |
|-------------|-------|-------------|
| Type Detection | `ingest_detect_type` | Classify file before processing |
| Document Processing | `ingest_document` | Full pipeline: detect → extract → chunk → embed → upsert |
| Batch Processing | `ingest_directory` | Recursive directory processing |
| Monitoring | `ingest_get_status`, `ingest_list_documents` | Track progress and history |
| Search | `ingest_search_chunks` | Semantic search within ingested documents |
| Lifecycle | `ingest_delete_document` | Remove document and Qdrant chunks |

## Feature Cross-Cutting Concerns

### Semantic Search

`wikijs_smart_query` (Wiki.js MCP) combines keyword search (Wiki.js GraphQL) with semantic search (Qdrant) via Reciprocal Rank Fusion. `qdrant_search` (Qdrant MCP) provides direct vector search with payload filtering.

### Document Processing

The Ingestion Pipeline handles 7 file types (PDF, DOCX, MD, TXT, PNG, JPG, TIFF) with automatic OCR routing for scanned documents. Tesseract MCP provides on-demand OCR for agent-driven workflows.

### Idempotency

Ingestion uses content hashing to prevent duplicate processing. Re-ingesting the same file updates existing chunks rather than creating duplicates.

### Health and Monitoring

`wikijs_wiki_health` provides 7 checks in a single call. `wikijs_wiki_stats` gives aggregate numbers with 60-second caching. `ingest_get_status` tracks pipeline progress.

For detailed tool documentation, see [MCP Servers](../mcp-servers/index.md) and [Tool Catalog](../reference/tool-catalog.md).

See also: [Architecture](../architecture/index.md) for system design, [Patterns](../patterns/index.md) for code conventions, [Guides](../guides/index.md) for workflows.
