# LLM Wiki Workflows (v3)

The LLM Wiki pattern defines four core operations: **Ingest**, **Query**, **Lint**, and **Document Processing**. Each workflow uses specific wiki-js-mcp v3 tools. v3 adds OCR and document ingestion to the traditional workflows.

## Query Workflow

Answer a question by finding and synthesizing wiki content with semantic search.

```mermaid
flowchart TD
    SmartQ["1. wikijs_smart_query\nHybrid semantic (Qdrant) + keyword search"]
    Stats["2. wikijs_get_page_stats\nTriage top candidates"]
    BulkRead["3. wikijs_bulk_get_pages\nRead full content of relevant pages"]
    Synthesize["4. Synthesize answer (agent)"]
    File["5. wikijs_create_page\nFile good answers (optional)"]

    SmartQ --> Stats --> BulkRead --> Synthesize --> File
```

**Tool sequence:**
1. `wikijs_smart_query("natural language question", limit=10)` -- ranked results with RRF fusion
2. `wikijs_get_page_stats(top_3_ids)` -- verify relevance via metadata
3. `wikijs_bulk_get_pages(relevant_ids)` -- read full content
4. Synthesize answer with citations
5. `wikijs_create_page(title="Query: ...", content=answer)` -- file good answers

**v3 advantage:** `wikijs_smart_query` uses Qdrant for semantic search, replacing the v2 embedded vector engine. Results are more accurate and the wiki-mcp image is 7x smaller.

## Ingest Workflow

Process new knowledge and integrate it into the wiki. v3 adds document pipeline support.

```mermaid
flowchart TD
    Search["1. wikijs_search_pages\nFind existing pages on topic"]
    Stats["2. wikijs_get_page_stats\nTriage without reading content"]
    Affected["3. wikijs_get_affected_pages\nDiscover related pages (4 signals)"]
    BulkRead["4. wikijs_bulk_get_pages\nRead current state"]
    Update["5. wikijs_update_page\nWrite updated content"]
    Append["6. wikijs_append_to_page\nAppend entry to log.md"]
    Index["7. wikijs_update_page\nUpdate index.md"]
    Rebuild["8. wikijs_rebuild_backlink_index\n(if bulk import)"]

    Search --> Stats --> Affected --> BulkRead --> Update --> Append --> Index
    Update -.->|after bulk| Rebuild
```

**Tool sequence:**
1. `wikijs_search_pages("topic keywords")` -- find existing pages
2. `wikijs_get_page_stats(candidate_ids)` -- triage relevance
3. `wikijs_get_affected_pages(core_page_id)` -- 4-signal impact analysis
4. `wikijs_bulk_get_pages(affected_ids)` -- read current state
5. `wikijs_update_page(id, content=updated)` -- write new content
6. `wikijs_append_to_page(log_id, "## [date] ingest | Title")` -- append to log
7. `wikijs_update_page(index_id, content=updated_index)` -- update index
8. `wikijs_rebuild_backlink_index()` -- only after bulk imports

**v3 advantage:** `wikijs_get_affected_pages` replaces manual backlink+graph+semantic checks with one automated call.

## Document Processing Workflow (NEW in v3)

Ingest external documents (PDF, DOCX, images, markdown) into Qdrant for semantic search.

```mermaid
flowchart TD
    Ingest["1. ingest_document\nDetect type, OCR if needed, chunk, embed, upsert"]
    Status["2. ingest_status\nVerify completion"]
    Search["3. qdrant_search\nFind ingested content"]
    WikiLink["4. wikijs_create_page\nCreate wiki page from extracted content"]

    Ingest --> Status --> Search --> WikiLink
```

**Tool sequence:**
1. `ingest_document(file_path="report.pdf")` -- full pipeline: detect -> extract -> chunk -> embed -> upsert
2. `ingest_status(document_id=doc_id)` -- verify chunks created
3. `qdrant_search("documents", "topic")` -- find relevant chunks
4. `wikijs_create_page(title="From: report.pdf", content=extracted_text)` -- create wiki page

See [OCR and Ingestion Workflows](ocr-and-ingestion-workflows.md) for detailed document processing patterns.

## Lint Workflow

Run health checks and fix issues.

```mermaid
flowchart TD
    Health["1. wikijs_wiki_health\nFull health dashboard (7 checks)"]
    Inspect["2. wikijs_bulk_get_pages\nRead orphan/stale pages"]
    Decide["3. Decide\nLink, update, or delete"]
    Fix["4. wikijs_update_page\nor wikijs_delete_page"]
    Log["5. wikijs_append_to_page\nAppend lint entry to log.md"]

    Health --> Inspect --> Decide --> Fix --> Log
```

**Tool sequence:**
1. `wikijs_wiki_health()` -- dashboard of all issues (orphans, stale, untagged, etc.)
2. `wikijs_bulk_get_pages(orphan_ids + stale_ids)` -- read problematic pages
3. Decide: link orphans, update stale, delete obsolete
4. Execute fixes via `wikijs_update_page` / `wikijs_delete_page`
5. `wikijs_append_to_page(log_id, "## [date] lint | Summary")` -- record in log

**Scale tip:** Use `include_checks=["orphans", "stale"]` to scope health checks. Run full health (7 checks) weekly.

## Navigation Workflow

Explore the wiki graph structure.

```mermaid
flowchart TD
    Extract["1. wikijs_extract_page_links\nWhat does this page link to?"]
    Graph["2. wikijs_get_page_graph\nExplore local neighborhood"]
    Path["3. wikijs_find_shortest_path\nHow are two concepts connected?"]
    Backlinks["4. wikijs_get_backlinks\nWhat links to this page?"]

    Extract --> Graph --> Path
    Graph --> Backlinks
```

**Tool sequence:**
1. `wikijs_extract_page_links(page_id)` -- classify internal/external links
2. `wikijs_get_page_graph(page_id, depth=1, direction="both")` -- immediate neighbors
3. `wikijs_find_shortest_path(from_id, to_id)` -- connection path
4. `wikijs_get_backlinks(page_id)` -- all inbound links

## Scale Rules

1. **Never read one-by-one**: Use `wikijs_bulk_get_pages` for any batch read of 2+ pages (cap: 50)
2. **Triage before reading**: Use `wikijs_get_page_stats` or `wikijs_wiki_health` to identify which pages matter
3. **Batch limit is 50**: Above 50, use `wikijs_smart_query`, `wikijs_wiki_health`, or paginate
4. **Append to log**: The log is append-only. Use `wikijs_append_to_page`, not read-modify-write
5. **Cross-references are the backbone**: When updating a page, use `wikijs_get_affected_pages` to find all related pages
6. **Ingest documents before referencing**: Use `ingest_document` before `wikijs_smart_query` if the content is from external files

## Cross-Server Workflows (v3 Multi-MCP)

These workflows chain tools across multiple MCP servers. Each uses the agent's ability to call tools on different servers in sequence.

### Workflow 1: Document Processing + Wiki Creation

Ingest an external document, search its content semantically, and create a wiki page from the results.

```mermaid
flowchart TD
    Ingest["1. ingest_document\n(Ingestion Pipeline :8002)"]
    Status["2. ingest_get_status\nVerify chunks created"]
    Search["3. ingest_search_chunks\nFind relevant content\n(Ingestion Pipeline :8002)"]
    Create["4. wikijs_create_page\nCreate wiki page from chunks\n(Wiki.js MCP :8000)"]
    Link["5. wikijs_get_affected_pages\nDiscover related wiki pages\n(Wiki.js MCP :8000)"]

    Ingest --> Status --> Search --> Create --> Link
```

**Tool sequence:**

1. `ingest_document(file_path="architecture.pdf")` [Ingestion :8002] — full pipeline: detect → extract → chunk → embed → upsert
2. `ingest_get_status(document_id)` [Ingestion :8002] — confirm chunks created
3. `ingest_search_chunks(query="microservices", limit=5)` [Ingestion :8002] — find most relevant chunks
4. `wikijs_create_page(title="Architecture (from architecture.pdf)", content=chunks_merged)` [Wiki.js :8000] — create wiki page
5. `wikijs_get_affected_pages(page_id)` [Wiki.js :8000] — discover pages that should link to this new page

### Workflow 2: OCR + Wiki Creation

Extract text from an image or scanned PDF using Tesseract MCP, then create a wiki page.

```mermaid
flowchart TD
    OCR["1. ocr_extract_text\n(Tesseract MCP :8003)"]
    Confidence["2. ocr_get_confidence\nCheck OCR quality\n(Tesseract MCP :8003)"]
    Decision{"Confidence\ngood?"}
    Create["3. wikijs_create_page\n(Wiki.js MCP :8000)"]
    Preprocess["3. ocr_preprocess_and_extract\nRe-try with preprocessing\n(Tesseract MCP :8003)"]

    OCR --> Confidence --> Decision
    Decision -->|yes| Create
    Decision -->|no| Preprocess --> Create
```

**Tool sequence:**

1. `ocr_extract_text(input_path="/data/shared/scan.png", language="eng+ita")` [Tesseract :8003] — OCR the image
2. `ocr_get_confidence(input_path="/data/shared/scan.png")` [Tesseract :8003] — check quality
3. If confidence < 70: `ocr_preprocess_and_extract(input_path, deskew=True, denoise=True)` [Tesseract :8003]
4. `wikijs_create_page(title="Scanned Document Content", content=extracted_text, space_id=1)` [Wiki.js :8000]

### Workflow 3: Batch Document Import + Bulk Wiki Creation

Ingest an entire directory of documents, then create wiki pages for each.

```mermaid
flowchart TD
    IngestDir["1. ingest_directory\n(Ingestion Pipeline :8002)"]
    ListDocs["2. ingest_list_documents\nGet all ingested docs\n(Ingestion Pipeline :8002)"]
    SearchAll["3. For each document:\nwikijs_search_pages\nCheck if page exists\n(Wiki.js MCP :8000)"]
    CreatePages["4. For each new document:\nwikijs_create_page\n(Wiki.js MCP :8000)"]
    Rebuild["5. wikijs_rebuild_backlink_index\n(Wiki.js MCP :8000)"]

    IngestDir --> ListDocs --> SearchAll --> CreatePages --> Rebuild
```

**Tool sequence:**

1. `ingest_directory(dir_path="/data/shared/docs/", recursive=True)` [Ingestion :8002] — process all files
2. `ingest_list_documents()` [Ingestion :8002] — get list of ingested documents
3. For each document: `wikijs_search_pages(filename_stem)` [Wiki.js :8000] — check if wiki page already exists
4. For new documents: `wikijs_create_page(title="From: doc_name", content=extracted_summary)` [Wiki.js :8000]
5. `wikijs_rebuild_backlink_index()` [Wiki.js :8000] — after bulk creation, rebuild the backlink graph

### Workflow 4: Semantic Search + Content Update

Search Qdrant directly for semantically similar content, then update wiki pages with findings.

```mermaid
flowchart TD
    QdrantSearch["1. qdrant_search\nSearch documents collection\n(Qdrant MCP :8001)"]
    WikiSearch["2. wikijs_smart_query\nFind related wiki pages\n(Wiki.js MCP :8000)"]
    BulkRead["3. wikijs_bulk_get_pages\nRead candidate pages\n(Wiki.js MCP :8000)"]
    Update["4. wikijs_update_page\nMerge new content\n(Wiki.js MCP :8000)"]
    Affected["5. wikijs_get_affected_pages\nDiscover impact\n(Wiki.js MCP :8000)"]

    QdrantSearch --> WikiSearch --> BulkRead --> Update --> Affected
```

**Tool sequence:**

1. `qdrant_search(collection="documents", query_text="topic", limit=10)` [Qdrant :8001] — search ingested documents
2. `wikijs_smart_query("topic")` [Wiki.js :8000] — find related wiki pages via hybrid search
3. `wikijs_bulk_get_pages(relevant_ids)` [Wiki.js :8000] — read current content
4. `wikijs_update_page(page_id, content=merged_content)` [Wiki.js :8000] — write updated content
5. `wikijs_get_affected_pages(page_id)` [Wiki.js :8000] — find pages that need attention after the update

## Cross-Server Scale Rules

1. **Ingest before search**: Ingested documents must exist in Qdrant before `wikijs_smart_query` can use them
2. **OCR quality check**: Always check OCR confidence before creating wiki pages from OCR output
3. **Bulk imports need backlink rebuild**: After creating many pages, run `wikijs_rebuild_backlink_index()`
4. **Idempotent ingestion**: Re-running `ingest_directory` skips already-ingested files — safe to retry
5. **Cross-server errors are independent**: A Qdrant MCP failure doesn't affect Wiki.js MCP tools and vice versa
