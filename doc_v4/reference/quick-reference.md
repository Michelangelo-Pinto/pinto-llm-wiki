# Quick Reference v4

Single-page cheat sheet for LLM agents operating against wiki-js-mcp v4.

## Server Map

| Server | Container | Port | Tools | Backend |
|--------|-----------|------|-------|---------|
| **Qdrant MCP** | `wikijs_qdrant_mcp` | 8001 | 8 | Qdrant REST :6334 |
| **Ingestion Pipeline** | `wikijs_ingestion` | 8002 | 7 | Qdrant + pytesseract |
| **Tesseract MCP** | `wikijs_tesseract_mcp` | 8003 | 7 | Tesseract binary |

## Knowledge Base

**v4 replaces Wiki.js with a file-system knowledge base** at `knowledge/`. Content is organized as markdown files in a category/subcategory hierarchy with `index.md` for routing.

```
knowledge/
  index.md           # Master category map
  category/
    index.md          # Category listing
    subcategory/
      index.md        # Subcategory listing
      page.md         # Knowledge page
```

### File Operations (replaces wikijs_* tools)

| Task | v3 (Wiki.js) | v4 (Filesystem) |
|------|-------------|-----------------|
| Create page | `wikijs_create_page` | `Write` to `knowledge/cat/sub/file.md` |
| Read page | `wikijs_get_page` | `Read knowledge/cat/sub/file.md` |
| Update page | `wikijs_update_page` | `StrReplace` on file |
| Search keyword | `wikijs_search_pages` | `Grep` in `knowledge/` |
| Search semantic | `wikijs_smart_query` | `qdrant_search` + `Read` results |
| Bulk read | `wikijs_bulk_get_pages` | Multiple `Read` calls |
| Append to log | `wikijs_append_to_page` | `StrReplace` (append) on `knowledge/log.md` |
| List pages | `wikijs_get_page_children` | `Glob` in category directory |
| Page stats | `wikijs_get_page_stats` | `Grep` for frontmatter fields |
| Create hierarchy | `wikijs_create_repo_structure` | `Shell mkdir -p` + `Write` index.md |

## Tool Catalog (Compact)

### Qdrant MCP (8 tools, port 8001)

`qdrant_create_collection(name, vector_size=384, distance="Cosine")` · `qdrant_list_collections()` · `qdrant_collection_info(name)` · `qdrant_delete_collection(name)` · `qdrant_search(collection, query_text, limit=10, filters?, score_threshold?, with_payload?)` · `qdrant_upsert_chunks(collection, chunks)` · `qdrant_delete_by_filter(collection, filter)` · `qdrant_scroll(collection, limit=50, offset?, with_payload?, with_vector=False)`

### Ingestion Pipeline (7 tools, port 8002)

`ingest_detect_type(file_path)` · `ingest_document(file_path, collection?, chunk_size=1500, chunk_overlap=200, force=False)` · `ingest_directory(dir_path, collection?, recursive=True, file_patterns?)` · `ingest_get_status(document_id?)` · `ingest_delete_document(document_id, collection?)` · `ingest_search_chunks(query, collection?, limit=10, filters?)` · `ingest_list_documents()`

### Tesseract MCP (7 tools, port 8003)

`ocr_get_languages()` · `ocr_detect_document_type(input_path)` · `ocr_extract_text(input_path, language="eng+ita", output_format?, page_range?, dpi=300, psm=3)` · `ocr_extract_hocr(input_path, language?, page_range?)` · `ocr_get_confidence(input_path, language?)` · `ocr_process_document(input_path, language?, auto_detect_type=True, preprocess=True, dpi=300)` · `ocr_preprocess_and_extract(input_path, language?, preprocess_steps?)`

## Qdrant Collections

| Collection | Vector Size | Distance | Purpose | Key Payload Fields |
|------------|------------|----------|---------|-------------------|
| `documents` | 384 | Cosine | Ingested document chunks | `document_id`, `chunk_index`, `source_file`, `file_type`, `text`, `content_hash` |

Model: `all-MiniLM-L6-v2` (384 dimensions, ~80 MB, pre-downloaded in images).

## SQLite Tables (Ingestion Pipeline)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `ingested_documents` | Track ingested files (idempotency) | `document_id`, `source_file`, `content_hash`, `status`, `chunks_created` |
| `document_chunks` | Chunk metadata | `document_id`, `chunk_index`, `chunk_hash`, `page_number`, `section_title` |
| `page_chunk_references` | File → chunk links | `file_path`, `chunk_id`, `document_id` |

## Cursor Configuration

```json
{
  "mcpServers": {
    "qdrant":     { "type": "sse", "url": "http://localhost:8001/sse" },
    "ingestion":  { "type": "sse", "url": "http://localhost:8002/sse" },
    "tesseract":  { "type": "sse", "url": "http://localhost:8003/sse" }
  }
}
```

## Workflow Templates

### Template 1: Ingest Document → Create Knowledge Page

```
1. ingest_document(file_path="report.pdf")         → get document_id
2. ingest_search_chunks(query="topic", limit=5)     → get relevant chunks
3. Write knowledge/ingested/YYYY-MM-DD-slug/report.md
   with frontmatter (source_type, source_file, etc.)
4. Update knowledge/ingested/index.md with new entry
```

### Template 2: Semantic Query → Read → Synthesize

```
1. qdrant_search(collection="documents", query_text="natural language question", limit=10)
2. Read the top 3-5 matching knowledge/ MD files
3. Synthesize answer with citations (links to MD files)
4. Optionally: Write query result to knowledge/queries/YYYY-MM-DD-query.md
```

### Template 3: Health Check → Fix Issues

```
1. Glob knowledge/**/*.md → list all MD files
2. For each file: verify frontmatter completeness
3. For each file: verify it appears in parent index.md
4. For each index.md: verify listed files exist
5. Fix any broken references or missing entries
```

### Template 4: Web Ingestion → Knowledge Page

```
1. Browser: navigate URL → extract content
2. Format as clean markdown with frontmatter
3. Write knowledge/ingested/YYYY-MM-DD-slug/page.md
4. Update knowledge/ingested/index.md
5. Optionally: ingest_document for semantic indexing
```

## Docker Commands

```bash
# Start full stack (4 containers)
docker compose up -d

# View status
docker compose ps

# View logs for a service
docker compose logs qdrant-mcp
docker compose logs ingestion-pipeline

# Rebuild a specific service after code changes
docker compose build qdrant-mcp && docker compose up -d qdrant-mcp

# Fast tests (Qdrant only)
docker compose --profile test run --rm test-runner

# Full-stack tests
docker compose up -d
docker compose --profile integration run --rm test-runner pytest tests/integration/stack/ -v
```

## Ports and Endpoints

| Service | Port | Endpoint | Protocol |
|---------|------|----------|----------|
| Qdrant MCP | 8001 | `http://localhost:8001/sse` | SSE |
| Ingestion Pipeline | 8002 | `http://localhost:8002/sse` | SSE |
| Tesseract MCP | 8003 | `http://localhost:8003/sse` | SSE |
| Qdrant REST | 6334 | `http://localhost:6334` | REST |
| Qdrant gRPC | 6333 | `localhost:6333` | gRPC |

## Common Errors Quick Fix

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `Connection refused` on SSE | Container not running | `docker compose up -d` |
| `Collection not found` | Qdrant collection not created | Use `qdrant_create_collection("documents")` or let ingestion create it |
| `File not found` in ingestion | File not in shared volume | Copy file to a path under `/data/shared/` inside container |
| `No text extracted` | Scanned PDF with no OCR | Pass to `ocr_extract_text` from Tesseract MCP instead |
| `Qdrant timeout` | Qdrant-db container not healthy | Check `docker compose ps`, restart `qdrant-db` |
| `Cursor doesn't discover tools` | Wrong mcp.json or SSE endpoint | `curl http://localhost:8001/sse`, restart Cursor |

## Key Rules for Agents

1. **Search before writing** — Use Grep + qdrant_search to avoid duplicate content
2. **Always update index.md** — Every new file must appear in its category's index.md
3. **Frontmatter required** — `title`, `category`, `created`, `updated` at minimum
4. **Ingest documents before searching** — If content is from external files, ingest first
5. **Append-only log** — `knowledge/log.md` is append-only
6. **Document pipeline = detect → extract → chunk → embed → upsert → record**
7. **Idempotent ingestion** — Re-ingesting the same file is a no-op unless `force=True`
8. **Max 4 levels deep** in `knowledge/` hierarchy
9. **Slug lowercase with hyphens** for file and directory names
10. **Mermaid supported** — Use ```mermaid blocks for diagrams in MD files

## Related Documents

- [System Overview](architecture/system-overview.md) — 4-container stack and data flow
- [Tool Catalog](reference/tool-catalog.md) — Full tool signatures with all parameters
- [LLM Wiki Workflows](guides/llm-wiki-workflows.md) — Detailed workflow patterns
- [Error Catalog](reference/error-catalog.md) — Full error catalog with solutions
- [Ingestion Pipeline Design](architecture/ingestion-pipeline-design.md) — Pipeline internals
