# Quick Reference

Single-page cheat sheet for LLM agents operating against wiki-js-mcp v3.

## Server Map

| Server | Container | Port | Tools | Backend |
|--------|-----------|------|-------|---------|
| **Wiki.js MCP** | `wikijs_mcp` | 8000 | ~43 | Wiki.js GraphQL + Qdrant |
| **Qdrant MCP** | `wikijs_qdrant_mcp` | 8001 | 8 | Qdrant REST :6334 |
| **Ingestion Pipeline** | `wikijs_ingestion` | 8002 | 7 | Qdrant + pytesseract |
| **Tesseract MCP** | `wikijs_tesseract_mcp` | 8003 | 7 | Tesseract binary |

## Tool Catalog (Compact)

### Wiki.js MCP (~43 tools, port 8000)

**Page CRUD:** `create_page(title, content, space_id?, parent_id?)` · `update_page(page_id, title?, content?)` · `get_page(page_id?, slug?)` · `search_pages(query, space_id?)`

**Bulk:** `bulk_get_pages(page_ids, include_content?)` · `bulk_get_page_stats(page_ids)`

**Backlinks:** `get_backlinks(page_id)` · `rebuild_backlink_index()`

**Stats:** `get_page_stats(page_id)` · `bulk_get_page_stats(page_ids)`

**Append:** `append_to_page(page_id, content, position="end")`

**Tags:** `search_by_tag(tag, include_subtags?)` · `list_all_tags(hierarchical?)` · `set_page_tags(page_id, tags)` · `filter_pages(filters)`

**Smart Query:** `smart_query(query, limit=10, include_summaries?, include_link_context?)`

**Graph:** `extract_page_links(page_id, link_type?)` · `get_page_graph(page_id, depth=1, direction="both", max_nodes=50)` · `find_shortest_path(from_page_id, to_page_id, max_depth=5)`

**Hierarchy:** `create_repo_structure(repo_name, description?, sections?)` · `create_nested_page(title, content, parent_path, create_parent_if_missing?)` · `get_page_children(page_id?, page_path?)` · `create_documentation_hierarchy(project_name, file_mappings, auto_organize?)`

**File Integration:** `link_file_to_page(file_path, page_id, relationship?)` · `sync_file_docs(file_path, change_summary, snippet?)` · `generate_file_overview(file_path, include_functions?, include_classes?, include_dependencies?, include_examples?, target_page_id?)` · `bulk_update_project_docs(summary, affected_files, context, auto_create_missing?)`

**Import/Export:** `export_wiki(output_dir, include_frontmatter?)` · `export_page(page_id, output_path?, include_frontmatter?)` · `import_page(file_path, target_path?, parent_id?, update_existing?)` · `import_directory(dir_path, base_parent_path?, update_existing?)`

**Health:** `wiki_health(include_checks?, exclude_page_ids?, exclude_paths?)` · `get_recent_changes(limit=20, since_days?, since_date?)` · `wiki_stats()` · `get_affected_pages(page_id, max_results=20, include_reasoning?)`

**Deletion:** `delete_page(page_id?, page_path?, remove_file_mapping?)` · `batch_delete_pages(page_ids?, page_paths?, path_pattern?, confirm_deletion, remove_file_mappings?)` · `delete_hierarchy(root_path, delete_mode, confirm_deletion, remove_file_mappings?)` · `cleanup_orphaned_mappings()`

**System:** `connection_status()` · `repository_context()` · `manage_collections(collection_name, description?, space_ids?)`

**Spaces:** `list_spaces()` · `create_space(name, description?)`

### Qdrant MCP (8 tools, port 8001)

`create_collection(name, vector_size=384, distance="Cosine")` · `list_collections()` · `collection_info(name)` · `delete_collection(name)` · `search(collection, query_text, limit=10, filters?, score_threshold?, with_payload?)` · `upsert_chunks(collection, chunks, wait?)` · `delete_by_filter(collection, filters)` · `scroll(collection, limit=50, offset?, filters?, with_payload?)`

### Ingestion Pipeline (7 tools, port 8002)

`ingest_detect_type(file_path)` · `ingest_document(file_path, collection?, chunk_size=1500, chunk_overlap=200, force=False)` · `ingest_directory(dir_path, collection?, recursive=True, file_patterns?)` · `ingest_get_status(document_id?)` · `ingest_delete_document(document_id, collection?)` · `ingest_search_chunks(query, collection?, limit=10, filters?)` · `ingest_list_documents()`

### Tesseract MCP (7 tools, port 8003)

`ocr_get_languages()` · `ocr_detect_document_type(input_path)` · `ocr_extract_text(input_path, language="eng+ita", output_format?, page_range?, dpi=300, psm=3)` · `ocr_extract_hocr(input_path, language?, page_range?, dpi=300)` · `ocr_get_confidence(input_path, language?)` · `ocr_process_document(input_path, language?, auto_detect=True)` · `ocr_preprocess_and_extract(input_path, language?, threshold_method?, deskew?, denoise?)`

## Qdrant Collections

| Collection | Vector Size | Distance | Purpose | Key Payload Fields |
|------------|------------|----------|---------|-------------------|
| `wiki_pages` | 384 | Cosine | Wiki page semantic search | `page_id`, `title`, `path`, `locale` |
| `documents` | 384 | Cosine | Ingested document chunks | `document_id`, `chunk_index`, `source_file`, `file_type`, `text`, `content_hash` |

Model: `all-MiniLM-L6-v2` (384 dimensions, ~80 MB, pre-downloaded in images).

## SQLite Tables

### Wiki.js MCP (`wikijs_mappings.db`)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `file_mappings` | File path → page ID | `file_path`, `page_id`, `file_hash`, `repository_root` |
| `backlinks` | Cross-reference links | `source_page_id`, `target_page_id`, `target_path`, `link_text` |
| `repository_contexts` | Repo → space mapping | `root_path`, `space_name`, `space_id` |

### Ingestion Pipeline (`ingestion.db`)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `ingested_documents` | Track ingested files (idempotency) | `document_id`, `source_file`, `content_hash`, `status`, `chunks_created` |
| `document_chunks` | Chunk metadata | `document_id`, `chunk_index`, `chunk_hash`, `page_number`, `section_title` |
| `page_chunk_references` | Wiki page → chunk links | `wiki_page_id`, `chunk_id`, `document_id` |

## Cursor Configuration

```json
{
  "mcpServers": {
    "wiki-js":   { "url": "http://localhost:8000/sse" },
    "qdrant":    { "url": "http://localhost:8001/sse" },
    "tesseract": { "url": "http://localhost:8003/sse" },
    "ingestion": { "url": "http://localhost:8002/sse" }
  }
}
```

## Workflow Templates

### Template 1: Ingest Document → Create Wiki Page

```
1. ingest_document(file_path="report.pdf")         → get document_id
2. ingest_search_chunks(query="topic", limit=5)     → get relevant chunks
3. wikijs_create_page(title="From: report.pdf",
     content=chunks_concatenated)                   → file in wiki
```

### Template 2: Smart Query → Bulk Read → Synthesize

```
1. wikijs_smart_query("natural language question", limit=10)
2. wikijs_get_page_stats(top_3_ids)
3. wikijs_bulk_get_pages(relevant_ids)
4. Synthesize answer with citations
```

### Template 3: Health Check → Fix Issues

```
1. wikijs_wiki_health()                             → get all issues
2. wikijs_bulk_get_pages(orphan_ids + stale_ids)    → read problem pages
3. For each: link orphans, update stale, delete obsolete
4. wikijs_append_to_page(log_id, "## lint | Summary")
```

### Template 4: Link Graph Exploration

```
1. wikijs_extract_page_links(page_id)               → see what it links to
2. wikijs_get_backlinks(page_id)                    → see what links to it
3. wikijs_find_shortest_path(from_id, to_id)        → find path between two
```

### Template 5: Batch Export → Edit → Re-import

```
1. wikijs_export_wiki("./backup")                   → full export
2. Edit markdown files locally
3. wikijs_import_directory("./backup", update_existing=True)
```

## Docker Commands

```bash
# Start full stack (8 containers)
docker compose up -d

# View status
docker compose ps

# View logs for a service
docker compose logs wiki-js-mcp
docker compose logs ingestion-pipeline

# Rebuild a specific service after code changes
docker compose build qdrant-mcp && docker compose up -d qdrant-mcp

# Fast tests (Qdrant only, ~2 min)
docker compose --profile test run --rm test-runner

# Full-stack tests
docker compose up -d
docker compose --profile integration run --rm test-runner pytest tests/integration/stack/ tests/regression/ -v

# Seed test data
docker compose exec wiki-js-mcp python3 scripts/seed_wiki_docs.py
```

## Ports and Endpoints

| Service | Port | Endpoint | Protocol |
|---------|------|----------|----------|
| Wiki.js Web UI | 3000 | `http://localhost:3000` | HTTP |
| Wiki.js MCP | 8000 | `http://localhost:8000/sse` | SSE |
| Qdrant MCP | 8001 | `http://localhost:8001/sse` | SSE |
| Ingestion Pipeline | 8002 | `http://localhost:8002/sse` | SSE |
| Tesseract MCP | 8003 | `http://localhost:8003/sse` | SSE |
| Qdrant REST | 6334 | `http://localhost:6334` | REST |
| Qdrant gRPC | 6333 | `localhost:6333` | gRPC |
| PostgreSQL | 5432 | Internal only | TCP |

## Common Errors Quick Fix

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `Connection refused` on SSE | Container not running | `docker compose up -d` |
| `Collection not found` | Qdrant collection not created | Use `qdrant_create_collection(name)` or let ingestion create it |
| `Authentication failed` | Wiki.js token expired | Check `.env` `WIKIJS_TOKEN`, restart wiki-js-mcp |
| `File not found` in ingestion | File not in shared volume | Copy file to a path under `/data/shared/` inside container |
| `No text extracted` | Scanned PDF with no OCR | Pass to `ocr_extract_text` from Tesseract MCP instead |
| `Page not found` | Wrong page ID or path | Use `wikijs_search_pages` to find the correct ID |
| `Qdrant timeout` | Qdrant-db container not healthy | Check `docker compose ps`, restart `qdrant-db` |
| `Cursor doesn't discover tools` | Wrong mcp.json or SSE endpoint | `curl http://localhost:8000/sse`, restart Cursor |

## Key Rules for Agents

1. **Never read one-by-one** — Use `bulk_get_pages` for 2+ pages (cap: 50)
2. **Triage before reading** — Use `get_page_stats` or `wiki_health` first
3. **Ingest documents before searching** — If content is from external files, ingest first
4. **Append-only log** — The log page is append-only via `append_to_page`
5. **Cross-references matter** — When updating a page, check `get_affected_pages`
6. **Smart query is the primary search** — Combines semantic (Qdrant) + keyword via RRF
7. **Document pipeline = detect → extract → chunk → embed → upsert → record**
8. **Idempotent ingestion** — Re-ingesting the same file is a no-op unless `force=True`

## Related Documents

- [System Overview](architecture/system-overview.md) — 8-container stack and data flow
- [Tool Catalog](reference/tool-catalog.md) — Full tool signatures with all parameters
- [LLM Wiki Workflows](guides/llm-wiki-workflows.md) — Detailed workflow patterns
- [Error Catalog](reference/error-catalog.md) — Full error catalog with solutions
- [Ingestion Pipeline Design](architecture/ingestion-pipeline-design.md) — Pipeline internals
