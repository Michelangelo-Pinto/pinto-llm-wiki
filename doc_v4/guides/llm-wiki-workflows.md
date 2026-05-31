# LLM Wiki Workflows v4

Detailed step-by-step workflow patterns for LLM agents operating the v4 knowledge base.

## Workflow 1: Ingest (new knowledge → knowledge base)

### Step 1: Search for existing content
```
Grep for "topic keyword" in knowledge/**/*.md
```
If nothing found, proceed to semantic search:
```
qdrant_search(collection="documents", query_text="topic", limit=10)
```

### Step 2: Determine category and path

Based on the content topic, choose the appropriate category from the hierarchy:
```
knowledge/
  software-engineering/  # Architecture, languages, patterns
  data-science/          # ML, statistics, data engineering
  operations/            # DevOps, monitoring, infrastructure
  ingested/              # External content (web, PDF, OCR)
```

### Step 3: Create the markdown file

Write the content to `knowledge/category/subcategory/slug.md` with complete frontmatter:

```yaml
---
title: "Page Title"
category: "category/subcategory"
tags: ["tag1", "tag2"]
created: "2026-05-30"
updated: "2026-05-30"
source_type: agent
description: "Brief description of content"
---
```

### Step 4: Update index files

1. Add entry to `knowledge/category/subcategory/index.md`
2. If a new subcategory was created, add entry to `knowledge/category/index.md`
3. Append to `knowledge/log.md`:
```
## [2026-05-30] ingest | Added topic documentation (file.md)
```

### Step 5: Semantic indexing (optional)

If the content should be searchable semantically, save as temp file in `/data/shared/` and run:
```
ingest_document(file_path="/data/shared/file.md", collection="documents")
```
Note: this requires user to copy the file via `docker compose cp` or `cp` to the shared volume.

---

## Workflow 2: Document Processing (external file → knowledge base)

### Step 0: Pre-Ingestion Analysis (Cursor agent)

Before ingesting, the agent analyzes the document to choose optimal parameters:

```
For text files (.md .txt .json .html .xml .csv): Read file directly
For binary files (.pdf .docx .epub .png .jpg): ingest_detect_type(file_path)
```

Then **spawn PreIngestionAnalyzer subagent** which returns:
- `suggested_chunk_size` and `suggested_chunk_overlap` (based on document type)
- `suggested_collection` (usually "documents")
- `pre_classification` (category, subcategory, language, title, doc_type)
- `should_index` (false if purely reference material)

See [Pre-Ingestion Analysis](pre-ingestion-analysis.md) for the decision matrix.

### Step 1: Place file in shared volume

Ask the user to copy the file to `to_ingest/`:
```
cp document.pdf to_ingest/
```
The `to_ingest/` directory is bind-mounted to `/data/shared` inside containers.

### Step 2: Ingest the document

Using parameters from pre-ingestion analysis:
```
ingest_document(file_path="/data/shared/document.pdf", chunk_size=1000, chunk_overlap=150)
→ returns document_id + chunk count
```

Check status:
```
ingest_get_status(document_id="abc123") → verify chunks created
```

### Step 3: Pre-populate routing metadata

Immediately after ingestion, populate routing layer (Layer 2) for better retrieval:
```
qdrant_scroll(collection="documents", filters={"must": [{"key": "document_id", "match": {"value": "abc123"}}]})
→ get all chunk points
Then qdrant_upsert_chunks with updated routing payload:
  routing.category = pre_classification.category
  routing.language = pre_classification.language
  routing.source_type = "file"
```

### Step 4: Trigger enrichment (optional)

Check if enrichment is enabled:
```
enrich_get_config() → check enabled field
```

If `enabled: true`, run enrichment:
```
enrich_document(document_id="abc123") → launches LangGraph pipeline
enrich_get_status(document_id="abc123") → check completion and logs
```

If enrichment completed, spawn **EnrichmentReviewer** subagent to write metadata.md.

Manual enrichment (`enrich_document`) always works regardless of `enabled` setting.

### Step 5: Retrieve relevant content

```
ingest_search_chunks(query="key concept", limit=5) → get relevant text chunks
```

### Step 6: Create knowledge page

Write a summary MD file in `knowledge/ingested/YYYY-MM-DD-slug/` with frontmatter:
```yaml
source_type: file
source_file: "document.pdf"
source_name: "Document Title"
fetched_at: "2026-05-30"
ingestion:
  document_id: "abc123"
  chunks_created: 24
enrichment:
  strategy: "full"
  status: "completed"
```

### Step 7: Update indexes and log

- Update `knowledge/ingested/index.md`
- Append to `knowledge/log.md`

---

## Workflow 3: Query (semantic search + synthesis)

### Step 1: Semantic search

```
qdrant_search(collection="documents", query_text="natural language question", limit=10)
```

### Step 2: Triage results

Review the top results by score. For scores > 0.5, read the source files:
```
Read knowledge/path/to/file1.md
Read knowledge/path/to/file2.md
```

### Step 3: Keyword fallback

If semantic results are weak, try keyword search:
```
Grep for "exact phrase" in knowledge/**/*.md
```

### Step 4: Synthesize answer

Combine findings into a coherent answer with citations (links to the MD files). Optionally save the query result:
```
Write knowledge/queries/YYYY-MM-DD-query.md
```

---

## Workflow 4: Lint (health check + fix)

### Step 1: Scan all MD files

```
Glob knowledge/**/*.md
```

### Step 2: Frontmatter validation

For each file, check:
- Has `title` field
- Has `category` field
- Has `created` and `updated` dates
- If `source_type` is web/file/upload, has `source_url`/`source_file` + `source_name` + `fetched_at`

### Step 3: Index consistency

For each category:
- Every MD file listed in `index.md` must exist
- Every existing MD file must be listed in its parent `index.md`

### Step 4: Fix issues

- Add missing frontmatter fields
- Add missing index entries
- Remove stale index entries for deleted files
- Append to `knowledge/log.md` with lint results

---

## Workflow 5: OCR (scanned documents)

```
1. ocr_detect_document_type("/data/shared/scan.pdf") → document type
2. ocr_extract_text("/data/shared/scan.pdf", language="eng+ita") → extracted text
3. ocr_get_confidence("/data/shared/scan.pdf") → if < 70%:
4. ocr_preprocess_and_extract("/data/shared/scan.pdf",
     preprocess_steps=["deskew", "denoise", "threshold"]) → improved extraction
5. Write knowledge/ingested/YYYY-MM-DD-slug/ocr-result.md with frontmatter:
   source_type: upload
   source_file: "scan.pdf"
   ocr_confidence: 85
   ocr_language: "eng+ita"
6. Update knowledge/ingested/index.md
7. Append to knowledge/log.md
```

---

## Workflow 6: Web Ingestion (browser → knowledge base)

### Path A — Direct (text pages)

```
1. Browser: navigate to URL
2. Extract content (text or HTML)
3. Format as clean markdown
4. Write knowledge/ingested/YYYY-MM-DD-slug/page.md
   with frontmatter (source_type: web, source_url, source_name, fetched_at)
5. Update knowledge/ingested/index.md
6. Append to knowledge/log.md
```

### Path B — Pipeline (complex pages, PDFs)

```
1. Browser: navigate to URL
2. Save content to agent_tmp/artifacts/file.md
3. Ask user: cp agent_tmp/artifacts/file.md /data/shared/
4. ingest_document(file_path="/data/shared/file.md")
5. Write knowledge/ingested/YYYY-MM-DD-slug/page.md
6. Update indexes and log
```

For complete web ingestion details, see `.cursor/rules/35-web-ingestion.mdc`.

---

## Workflow 7: Multi-Hop Retrieval (complex queries)

For complex queries requiring multiple search passes before synthesis. **Never answer after a single `qdrant_search`.**

### Step 1: Analyze the query

Extract from the user query:
- Semantic topic ("privacy sanctions")
- Explicit references ("Law 456/2018 Art.12")
- Named entities ("Garante Privacy", "GDPR")

For complex queries, spawn **QueryPlanner** subagent to produce a RetrievalPlan.

### Step 2: First pass — Exploratory

```
qdrant_search(collection="documents", query_text="<topic>", limit=10)
```

No filters. Review scores:
- Median > 0.5: good semantic match
- Median < 0.4: try keyword fallback with Grep

### Step 3: Second pass — Filtered

From Pass 1 results, identify dominant `routing.category` and `routing.language`:

```
qdrant_search(
  collection="documents",
  query_text="<refined topic>",
  filters={"must": [{"key": "routing.category", "match": {"value": "legal"}}]},
  limit=5
)
```

### Step 4: Reference pass — Explicit citations

If query mentions a law or code:

```
qdrant_search(
  collection="documents",
  query_text="<topic>",
  filters={"must": [{"key": "references.cites.id", "match": {"value": "456/2018"}}]},
  limit=5
)
```

### Step 5: Expand — Follow cross-references

For each `references.cites` in top results, fetch the referenced document via `qdrant_scroll`.

### Step 6: Keyword fallback

If semantic scores remain weak:
```
Grep "exact phrase" in knowledge/**/*.md
```

### Step 7: Synthesize

Combine all passes, deduplicate by `document_id` + `chunk_index`, cite source files.

See [Multi-Hop Retrieval](multi-hop-retrieval.md) for the full sequence diagram and when-to-stop rules.

---

## Workflow 8: Post-Ingestion Enrichment

Triggered automatically (if `enabled: true`) or manually via `enrich_document`.

### Step 1: Check enrichment status

```
enrich_get_config() → check enabled field
```

### Step 2: Run enrichment (manual)

```
enrich_document(document_id="abc123", collection="documents")
```

The LangGraph enrichment pipeline runs:
1. **pre_analysis** — Decides strategy (skip/basic/references_only/full)
2. **classify_document** — Classifies document type (1 LLM call)
3. **extract_references** — Finds legal citations, cross-references (1 LLM call)
4. **map_references** — Maps refs to relevant chunks (0 LLM)
5. **enrich_chunks** — Assigns section, chunk_type per chunk (0 LLM)
6. **upsert_enriched** — Updates Qdrant payload with Layers 3-5

### Step 3: Check results

```
enrich_get_status(document_id="abc123") → structured JSON logs
```

### Step 4: Review enrichment

Spawn **EnrichmentReviewer** subagent:
1. Read enrichment logs
2. Validate classification and references
3. Write `knowledge/ingested/YYYY-MM-DD-slug/metadata.md`
4. Update `knowledge/ingested/index.md`
5. Append to `knowledge/log.md`

See [Enrichment Config](../../knowledge/enrichment-config.md) for toggle and LLM parameters.

---

## Cross-Cutting Rules

1. **Never write without searching first** — Grep + qdrant_search before creating new content
2. **Always update index.md** — every new file must appear in its category index
3. **Frontmatter mandatory** — `title`, `category`, `created`, `updated` at minimum
4. **Append-only log** — `knowledge/log.md` is append-only, use StrReplace for appends
5. **Source attribution** — external content requires `source_type`, `source_url`/`source_file`, `source_name`, `fetched_at`
6. **Max depth 4** — no more than 4 levels from `knowledge/` root
7. **Slug format** — lowercase, hyphens for spaces, no special characters
8. **Pre-ingestion analysis** — always analyze documents before ingestion to choose optimal chunk_size and pre-populate routing metadata
9. **Multi-hop retrieval** — never answer after a single qdrant_search on complex queries; minimum 2 passes
10. **Enrichment is optional** — default OFF; manually triggerable via enrich_document regardless of config
