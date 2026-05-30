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

### Step 1: Place file in shared volume

Ask the user to copy the file to `/data/shared/`:
```
cp document.pdf /data/shared/
```

### Step 2: Ingest the document

```
ingest_document(file_path="/data/shared/document.pdf") → returns document_id + chunk count
```

Check status:
```
ingest_get_status(document_id="abc123") → verify chunks created
```

### Step 3: Retrieve relevant content

```
ingest_search_chunks(query="key concept", limit=5) → get relevant text chunks
```

### Step 4: Create knowledge page

Write a summary MD file in `knowledge/ingested/YYYY-MM-DD-slug/` with frontmatter:
```yaml
source_type: file
source_file: "document.pdf"
source_name: "Document Title"
fetched_at: "2026-05-30"
```

### Step 5: Update indexes and log

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

## Cross-Cutting Rules

1. **Never write without searching first** — Grep + qdrant_search before creating new content
2. **Always update index.md** — every new file must appear in its category index
3. **Frontmatter mandatory** — `title`, `category`, `created`, `updated` at minimum
4. **Append-only log** — `knowledge/log.md` is append-only, use StrReplace for appends
5. **Source attribution** — external content requires `source_type`, `source_url`/`source_file`, `source_name`, `fetched_at`
6. **Max depth 4** — no more than 4 levels from `knowledge/` root
7. **Slug format** — lowercase, hyphens for spaces, no special characters
