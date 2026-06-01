# Data Flow

Request lifecycle diagrams for major operations in pinto-llm-wiki v4. Each section covers a key workflow with a mermaid sequence diagram showing the actors and data transformations involved.

## Semantic Search (`qdrant_search`)

Semantic vector search using Qdrant embeddings, followed by file-system read of matching knowledge files.

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant QMCP as Qdrant MCP :8001
    participant Qdrant as Qdrant DB :6334
    participant KB as knowledge/ (filesystem)

    Agent->>QMCP: qdrant_search(collection="documents", query_text="topic", limit=10)
    QMCP->>QMCP: embed query (all-MiniLM-L6-v2, 384-dim)
    QMCP->>Qdrant: search(documents, query_vector, limit=10)
    Qdrant-->>QMCP: results [id, score, payload]
    QMCP-->>Agent: [{document_id, chunk_text, score, payload}]

    Agent->>KB: Read matching knowledge/ MD files
    KB-->>Agent: markdown content
    Agent-->>Agent: synthesize answer with citations
```

## Document Ingestion (`ingest_document`)

Full pipeline: detect file type → extract text → chunk → embed → upsert to Qdrant → track in SQLite.

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant IMCP as Ingestion Pipeline :8002
    participant FS as Filesystem (shared volume)
    participant SQLite as SQLite :ingestion.db
    participant Qdrant as Qdrant DB :6334
    participant Tess as Tesseract (in-process)

    Agent->>IMCP: ingest_document(file_path="/data/shared/report.pdf")
    IMCP->>FS: read file bytes
    IMCP->>IMCP: compute SHA-256 content hash
    IMCP->>SQLite: check if already ingested (hash match)
    SQLite-->>IMCP: no match → proceed

    IMCP->>FS: PyMuPDF open PDF, detect type
    alt Scanned PDF
        IMCP->>FS: render pages at 300 DPI
        IMCP->>Tess: pytesseract.image_to_string(page_img, lang="eng+ita")
        Tess-->>IMCP: extracted text per page
    else Text PDF
        IMCP->>FS: extract text directly via PyMuPDF
    end

    IMCP->>IMCP: chunk_document(text, 1500 chars, 200 overlap) → 12 chunks
    IMCP->>IMCP: embed_chunks → 12 × 384-dim vectors
    IMCP->>Qdrant: upsert(documents, points=[12 PointStructs])
    Qdrant-->>IMCP: ok
    IMCP->>SQLite: INSERT into ingested_documents (document_id, source_file, status="completed", chunks_created=12)
    IMCP-->>Agent: {"status": "completed", "document_id": "abc123", "chunks_created": 12}
```

## Knowledge File Creation (v4 file-system workflow)

Agent creates markdown files directly in the `knowledge/` directory and updates routing indexes.

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant KB as knowledge/ (filesystem)
    participant Qdrant as Qdrant DB :6334

    Agent->>KB: Grep for existing content on topic
    KB-->>Agent: search results or empty

    Agent->>Qdrant: qdrant_search(collection="documents", query_text="topic")
    Qdrant-->>Agent: semantic results

    Agent->>Agent: determine category/subcategory path
    Agent->>KB: Write knowledge/category/subcategory/page.md
    Agent->>KB: Write (frontmatter + content)

    Agent->>KB: Read knowledge/category/subcategory/index.md
    Agent->>KB: StrReplace — add new entry to index

    Agent->>KB: Append to knowledge/log.md
    Note over Agent: Log entry: ## [YYYY-MM-DD] ingest | description
```

## OCR Processing (`ocr_extract_text`)

Standalone OCR of scanned documents via Tesseract MCP.

```mermaid
sequenceDiagram
    participant Agent as LLM Agent
    participant TMCP as Tesseract MCP :8003
    participant FS as Filesystem (shared volume)
    participant Tess as Tesseract binary

    Agent->>TMCP: ocr_extract_text(input_path="/data/shared/scan.pdf", language="eng+ita")
    TMCP->>FS: PyMuPDF open PDF, detect page types
    TMCP->>TMCP: preprocess images (grayscale, deskew, threshold)
    TMCP->>Tess: tesseract image_to_string per page
    Tess-->>TMCP: extracted text
    TMCP-->>Agent: {"text": "...", "confidence": 85, "pages": 5}
```

## Related Documents

- [System Overview](system-overview.md) — Container topology and startup order
- [Ingestion Pipeline Design](ingestion-pipeline-design.md) — Pipeline internals
- [LLM Wiki Workflows](../guides/llm-wiki-workflows.md) — Usage patterns
- [Quick Reference](../reference/quick-reference.md) — All tools at a glance
