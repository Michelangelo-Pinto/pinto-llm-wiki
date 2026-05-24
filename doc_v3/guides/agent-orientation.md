# Agent Orientation

How to instruct the LLM agent (Cursor IDE) to use wiki-js-mcp v3 tools effectively. This guide is for the **human operator** — it tells you what to say to the agent, what context to give it, and how to get the best results.

## Before You Start

The agent needs the Docker stack running and Cursor configured:

```bash
docker compose up -d
docker compose ps    # Verify all 8 containers healthy
```

Cursor `mcp.json` must include all 4 servers (see [Multi-MCP Setup](multi-mcp-setup.md)).

## First Contact: Contextualizing the Agent

When you first open a session with the agent, give it context. The agent doesn't know about wiki-js-mcp until you tell it. Send this as your first message:

```
You are connected to wiki-js-mcp v3, a 4-server MCP ecosystem:
- wiki-js (port 8000): ~43 tools for Wiki.js CRUD, search, graph, health
- qdrant (port 8001): 8 tools for Qdrant vector search
- ingestion (port 8002): 7 tools for document processing (PDF, DOCX, images)
- tesseract (port 8003): 7 tools for on-demand OCR

Before doing anything, read these documents to understand the system:
1. doc_v3/reference/quick-reference.md
2. doc_v3/guides/llm-wiki-workflows.md
3. doc_v3/guides/file-paths-and-volumes.md

I need you to [describe your goal here].
```

To make this even faster, use the shorthand:

```
@doc_v3/reference/quick-reference.md @doc_v3/guides/llm-wiki-workflows.md @doc_v3/guides/file-paths-and-volumes.md

[Your goal]
```

## Prompt Templates for Common Tasks

### Ingest a document and create a wiki page

```
Ingest this document and create a wiki page from its content:
- File: /data/shared/report.pdf
- Wiki space: [space name or id]
- Page title: [suggested title]

Steps:
1. Use ingest_document on ingestion server (port 8002)
2. Use ingest_search_chunks to get relevant content
3. Use wikijs_create_page on wiki-js server (port 8000)
4. Use wikijs_get_affected_pages to find related pages
```

### Semantic search across the wiki

```
Search the wiki for information about [topic].
Use wikijs_smart_query to find relevant pages, then wikijs_bulk_get_pages to read the top results.
Summarize what you find and cite the wiki pages.
```

### Run a health check

```
Run wikijs_wiki_health to check the wiki for orphans, stale pages, and untagged pages.
Show me the results and recommend fixes.
```

### Export the entire wiki for offline editing

```
Export the full wiki to /data/shared/wiki-backup-YYYY-MM-DD.
Use wikijs_export_wiki.
Then tell me the docker compose cp command to extract the files to my host.
```

### Import manually edited pages

```
Import all .md files from /data/shared/edited-pages/ back into the wiki.
Use wikijs_import_directory with update_existing=True.
After import, run wikijs_rebuild_backlink_index.
```

### OCR a scanned document

```
OCR this scanned PDF and create a wiki page from the text:
- File: /data/shared/scan.pdf
- First use ocr_detect_document_type (tesseract port 8003) to check if OCR is needed
- Then use ocr_process_document to extract text (auto-detect pages)
- If confidence is low, use ocr_preprocess_and_extract
- Create a wiki page from the extracted text
```

## Conventions to Tell the Agent

If the agent seems confused, remind it of these conventions:

```
Important conventions for wiki-js-mcp:
- Tool names use prefixes: wikijs_*, qdrant_*, ingest_*, ocr_*
- File paths for ingestion must be under /data/shared/
- Use wikijs_bulk_get_pages for reading 2+ pages (never one-by-one)
- Use wikijs_get_page_stats before reading full page content
- The log page is append-only; use wikijs_append_to_page
- Export output goes inside the container; extract with docker compose cp
- Ingestion is idempotent; re-ingesting the same file is a no-op
- smart_query combines semantic (Qdrant) + keyword (Wiki.js) via RRF
```

## What NOT to Ask the Agent

Some operations the agent cannot perform directly — they require manual intervention:

| Don't ask the agent to... | Instead, do this yourself |
|---------------------------|--------------------------|
| "Start the Docker stack" | Run `docker compose up -d` in your terminal |
| "Configure Cursor" | Edit `mcp.json` manually, then restart Cursor |
| "Copy files into the container" | Use `docker compose cp` in your terminal |
| "Change environment variables" | Edit `.env` and run `docker compose up -d` |
| "Install new Tesseract languages" | Edit the Dockerfile and rebuild |
| "Extract exported files" | Use `docker compose cp wiki-js-mcp:/data/shared/... ./...` |
| "Create a Qdrant collection" (if schema matters) | Use `qdrant_create_collection` but verify schema first |
| "Build Docker images" | Run `docker compose build` in your terminal |

## Troubleshooting Agent Issues

### "Tool not found"

The agent doesn't know which server has which tool. Remind it:
- `wikijs_*` tools are on port 8000
- `qdrant_*` tools are on port 8001
- `ingest_*` tools are on port 8002
- `ocr_*` tools are on port 8003

### "File not found" during ingestion

The agent may use a path that doesn't exist in the container. Remind it:
- All files must be under `/data/shared/`
- Use `docker compose cp` to copy files into the container first

### Agent reads pages one-by-one

Remind it: "Use wikijs_bulk_get_pages for reading multiple pages — it's faster and uses fewer round trips."

### Agent doesn't check existing content before creating

Remind it: "Use wikijs_search_pages first to check if a page on this topic already exists."

## Related Documents

- [Quick Reference](../reference/quick-reference.md) — All tools and commands at a glance
- [LLM Wiki Workflows](llm-wiki-workflows.md) — Detailed workflow patterns with mermaid diagrams
- [Multi-MCP Setup](multi-mcp-setup.md) — Cursor configuration
- [File Paths and Volumes](file-paths-and-volumes.md) — Where files go
- [Troubleshooting](troubleshooting.md) — Common operational issues
