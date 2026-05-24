# Data Flow

Request lifecycle diagrams for all major operations in wiki-js-mcp v3. Each section covers a key workflow with a mermaid sequence diagram showing the actors and data transformations involved.

## Semantic Query (`wikijs_smart_query`)

Hybrid search combining Qdrant semantic search and Wiki.js keyword search via Reciprocal Rank Fusion.

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant WMCP as Wiki.js MCP :8000
    participant Wiki as Wiki.js :3000
    participant Qdrant as Qdrant DB :6334
    participant PG as PostgreSQL :5432

    Agent->>WMCP: smart_query("authentication methods", limit=10)
    WMCP->>WMCP: authenticate (JWT)

    par Parallel: semantic + keyword
        WMCP->>WMCP: embed query (all-MiniLM-L6-v2, 384-dim)
        WMCP->>Qdrant: query_points(wiki_pages, query_vector, limit=10)
        Qdrant-->>WMCP: semantic results [id, score, payload]
    and
        WMCP->>Wiki: pages.search("authentication methods")
        Wiki->>PG: SELECT ... WHERE content ILIKE '%auth%'
        PG-->>Wiki: rows
        Wiki-->>WMCP: keyword results [pageId, title, path]
    end

    WMCP->>WMCP: RRF merge (k=60)
    alt summaries requested
        WMCP->>WMCP: truncate content to 500 chars
    end
    alt link_context requested
        WMCP->>WMCP: BacklinkIndex query for inbound counts
    end

    WMCP-->>Agent: [{pageId, title, path, score, summary, inboundLinks}]

    Note over WMCP: Fallback modes:<br/>- full: both semantic + keyword<br/>- semantic: keyword failed<br/>- keyword: Qdrant unavailable
```

## Page Create with Backlink Sync

Creating a page triggers fire-and-forget hooks for backlink indexing and stats cache invalidation.

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant WMCP as Wiki.js MCP :8000
    participant Wiki as Wiki.js :3000
    participant PG as PostgreSQL :5432
    participant SQLite as SQLite :wikijs_mappings.db

    Agent->>WMCP: create_page(title="Auth", content="...", space_id=1)
    WMCP->>WMCP: authenticate (JWT)

    WMCP->>Wiki: mutation { pages { create(...) } }
    Wiki->>PG: INSERT INTO pages (...)
    PG-->>Wiki: ok
    Wiki-->>WMCP: { responseResult: { succeeded: true }, page: { id: 99, ... } }

    par Fire-and-forget hooks
        WMCP->>WMCP: _sync_backlinks_for_page(99, content)
        WMCP->>WMCP: _extract_links(content) → [(text, path), ...]
        WMCP->>WMCP: _resolve_paths_to_ids(paths) → {path: id}
        WMCP->>SQLite: DELETE backlinks WHERE source_page_id=99
        WMCP->>SQLite: INSERT INTO backlinks (...) VALUES ...
    and
        WMCP->>WMCP: _invalidate_stats_cache()
    end

    WMCP-->>Agent: {"pageId": 99, "title": "Auth", "status": "created"}

    Note over WMCP: Hooks are fire-and-forget.<br/>Tool returns success even if hooks fail.<br/>Repair via rebuild_backlink_index().
```

## Page Update

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant WMCP as Wiki.js MCP :8000
    participant Wiki as Wiki.js :3000
    participant PG as PostgreSQL :5432
    participant SQLite as SQLite :wikijs_mappings.db

    Agent->>WMCP: update_page(page_id=99, content="updated content")
    WMCP->>WMCP: authenticate (JWT)

    WMCP->>Wiki: mutation { pages { update(id:99, content:"...") } }
    Wiki->>PG: UPDATE pages SET content='...' WHERE id=99
    PG-->>Wiki: ok
    Wiki-->>WMCP: { responseResult: { succeeded: true } }

    par Fire-and-forget hooks
        WMCP->>SQLite: DELETE backlinks WHERE source_page_id=99
        WMCP->>WMCP: _extract_links("updated content")
        WMCP->>SQLite: INSERT INTO backlinks (...) VALUES ...
    and
        WMCP->>WMCP: _invalidate_stats_cache()
    end

    WMCP-->>Agent: {"pageId": 99, "status": "updated"}
```

## Wiki Health (7 Checks)

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant WMCP as Wiki.js MCP :8000
    participant Wiki as Wiki.js :3000
    participant PG as PostgreSQL :5432
    participant SQLite as SQLite :wikijs_mappings.db

    Agent->>WMCP: wiki_health(include_checks=["orphans","stale","untagged"])
    WMCP->>WMCP: authenticate (JWT)

    par Fetch all pages metadata
        WMCP->>Wiki: pages.list (all pages with tags, updatedAt)
        Wiki->>PG: SELECT id, title, path, tags, updatedAt FROM pages
        PG-->>Wiki: rows
        Wiki-->>WMCP: all pages with metadata
    and Query BacklinkIndex
        WMCP->>SQLite: SELECT source_page_id, target_page_id FROM backlinks
        SQLite-->>WMCP: all backlink rows
    end

    WMCP->>WMCP: orphans: pages with zero inbound links
    WMCP->>WMCP: stale: pages not updated in 90+ days
    WMCP->>WMCP: untagged: pages with empty tags array
    WMCP->>WMCP: link_density: outbound links distribution
    WMCP->>WMCP: most_connected: GROUP BY target_page_id ORDER BY count DESC LIMIT 10

    opt disconnected_clusters requested
        WMCP->>WMCP: BFS on full link graph from BacklinkIndex
        WMCP->>WMCP: find connected components, flag small clusters
    end

    WMCP-->>Agent: {checks_run: [...], orphans: [...], stale: [...], summary: {...}}
```

## Affected Pages (4 Signals)

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant WMCP as Wiki.js MCP :8000
    participant Wiki as Wiki.js :3000
    participant Qdrant as Qdrant DB :6334
    participant SQLite as SQLite :wikijs_mappings.db

    Agent->>WMCP: get_affected_pages(page_id=99, max_results=20)
    WMCP->>WMCP: authenticate (JWT)

    par Signal 1: Backlinks (weight 1.0)
        WMCP->>SQLite: SELECT source_page_id FROM backlinks WHERE target_page_id=99
        SQLite-->>WMCP: [45, 67, 12]
    and Signal 2: Graph neighbors (weight 0.8)
        WMCP->>SQLite: SELECT DISTINCT target_page_id FROM backlinks WHERE source_page_id=99
        SQLite-->>WMCP: pages linked from source
        WMCP->>SQLite: SELECT source_page_id FROM backlinks WHERE target_page_id=99
        SQLite-->>WMCP: all pages in 1-hop neighborhood
    and Signal 3: Semantic similarity (weight 0.6)
        WMCP->>WMCP: embed source page content (384-dim)
        WMCP->>Qdrant: search(wiki_pages, query_vector, score_threshold=0.7)
        Qdrant-->>WMCP: semantically similar pages
    and Signal 4: Shared tags (weight 0.3-0.5)
        WMCP->>Wiki: pages.list (all pages with tags)
        Wiki-->>WMCP: all page tags
    end

    WMCP->>WMCP: deduplicate by page_id
    WMCP->>WMCP: rank by weighted sum of signal scores
    WMCP->>WMCP: resolve titles via bulk_get_pages

    WMCP-->>Agent: {source: {...}, affected_pages: [{pageId, title, relevance_score, reasons}], signal_breakdown: {...}}
```

## Document Ingestion (`ingest_document`)

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant IMCP as Ingestion Pipeline :8002
    participant FS as Filesystem (shared volume)
    participant SQLite as SQLite :ingestion.db
    participant Qdrant as Qdrant DB :6334
    participant Tess as Tesseract (in-process)

    Agent->>IMCP: ingest_document(file_path="/data/shared/report.pdf")

    IMCP->>FS: read file bytes (64 KB chunks)
    IMCP->>IMCP: compute SHA-256 content hash

    IMCP->>SQLite: SELECT FROM ingested_documents WHERE content_hash = 'abc...'
    SQLite-->>IMCP: no match → proceed

    IMCP->>FS: PyMuPDF open PDF, sample first 5 pages
    IMCP->>IMCP: detect: avg 12 chars/page, 4/5 image pages → scanned_pdf

    IMCP->>FS: PyMuPDF render each page at 300 DPI
    IMCP->>Tess: pytesseract.image_to_string(page_img, lang="eng+ita")
    Tess-->>IMCP: extracted text per page

    IMCP->>IMCP: chunk_document(text, source_type="pdf", 1500, 200)
    IMCP-->>IMCP: [chunk1, chunk2, ..., chunk12]

    IMCP->>IMCP: embed_chunks([chunk1, ..., chunk12]) → 12 × 384-dim vectors

    IMCP->>Qdrant: upsert(documents, points=[12 PointStructs])
    Qdrant-->>IMCP: ok

    IMCP->>SQLite: INSERT INTO ingested_documents (document_id, source_file, status="completed", chunks_created=12, content_hash="abc...")
    SQLite-->>IMCP: ok

    IMCP-->>Agent: {"status": "completed", "document_id": "abc123...", "chunks_created": 12}
```

## Import/Export Markdown Roundtrip

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant WMCP as Wiki.js MCP :8000
    participant Wiki as Wiki.js :3000
    participant PG as PostgreSQL :5432
    participant FS as Local Filesystem

    Note over Agent,FS: Export phase

    Agent->>WMCP: export_wiki(output_dir="./backup")
    WMCP->>WMCP: authenticate (JWT)

    WMCP->>Wiki: pages.list (all pages with tags, timestamps)
    Wiki->>PG: SELECT id, title, path, content, tags, created_at, updated_at
    PG-->>Wiki: rows
    Wiki-->>WMCP: all page data

    WMCP->>FS: write ./backup/docs/auth.md (YAML frontmatter + body)
    WMCP->>FS: write ./backup/docs/auth/overview.md
    WMCP->>FS: write ./backup/index.md
    FS-->>WMCP: files written

    WMCP-->>Agent: {"exported": 234, "output_dir": "./backup"}

    Note over Agent,FS: Edit phase (offline)

    Agent-->>Agent: Edit markdown files in Obsidian/VS Code

    Note over Agent,FS: Import phase

    Agent->>WMCP: import_directory(dir_path="./backup", update_existing=True)
    WMCP->>WMCP: authenticate (JWT)

    loop For each .md file in directory tree
        WMCP->>FS: read file, parse YAML frontmatter
        WMCP->>Wiki: pages.singleByPath(path) → check if exists
        Wiki->>PG: SELECT id FROM pages WHERE path = 'docs/auth'
        PG-->>Wiki: {id: 7} or null

        alt Page exists + update_existing
            WMCP->>Wiki: mutation { pages { update(id:7, content:"...", title:"...") } }
            Wiki->>PG: UPDATE pages SET ... WHERE id=7
        else New page
            WMCP->>Wiki: mutation { pages { create(title:"Auth", content:"...") } }
            Wiki->>PG: INSERT INTO pages (...)
        end
        Wiki-->>WMCP: { responseResult: { succeeded: true } }
    end

    WMCP-->>Agent: {"imported": 230, "updated": 200, "created": 30}
```

## Rebuild Backlink Index

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant WMCP as Wiki.js MCP :8000
    participant Wiki as Wiki.js :3000
    participant PG as PostgreSQL :5432
    participant SQLite as SQLite :wikijs_mappings.db

    Agent->>WMCP: rebuild_backlink_index()
    WMCP->>WMCP: authenticate (JWT)

    WMCP->>Wiki: pages.list (all page IDs)
    Wiki->>PG: SELECT id FROM pages
    PG-->>Wiki: [1, 2, 3, ..., 234]
    Wiki-->>WMCP: [1, 2, 3, ..., 234]

    WMCP->>Wiki: bulk get all page content (parallel, cap 50 per batch)
    Wiki->>PG: SELECT id, content FROM pages WHERE id IN (...)
    PG-->>Wiki: rows
    Wiki-->>WMCP: batches of page content

    WMCP->>SQLite: DELETE FROM backlinks (clear index)

    loop For each page
        WMCP->>WMCP: _extract_links(content) → [(text, path), ...]
        WMCP->>WMCP: _resolve_paths_to_ids(paths) → {path: id}
        WMCP->>SQLite: INSERT INTO backlinks (source_page_id, target_page_id, ...)
        WMCP->>WMCP: skip self-links, broken links
    end

    WMCP-->>Agent: {"status": "rebuilt", "pages_processed": 234, "links_found": 1204}
```

## Batch Document Import (`ingest_directory`)

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant IMCP as Ingestion Pipeline :8002
    participant FS as Filesystem (shared volume)

    Agent->>IMCP: ingest_directory(dir_path="/data/documents/", recursive=True)

    IMCP->>FS: rglob("*.pdf"), rglob("*.docx"), rglob("*.md"), ...
    FS-->>IMCP: [file1.pdf, file2.pdf, file3.docx, file4.md, ...]

    loop For each file (sequential)
        IMCP->>IMCP: _file_hash(file) → check SQLite
        alt Already ingested (hash match)
            IMCP->>IMCP: skip (idempotent)
        else New or changed
            IMCP->>IMCP: detect → extract → chunk → embed → upsert → record
        end
    end

    IMCP-->>Agent: {files_processed: 47, files_failed: 2, results: [...], errors: [...]}

    Note over IMCP: Results truncated to 50 each.<br/>Use ingest_get_status() for full list.
```

## Related Documents

- [System Overview](system-overview.md) — Container topology and startup order
- [Multi-MCP Architecture](multi-mcp-architecture.md) — Communication patterns
- [Ingestion Pipeline Design](ingestion-pipeline-design.md) — Pipeline internals
- [LLM Wiki Workflows](../guides/llm-wiki-workflows.md) — Usage patterns
- [Quick Reference](../reference/quick-reference.md) — All tools at a glance
