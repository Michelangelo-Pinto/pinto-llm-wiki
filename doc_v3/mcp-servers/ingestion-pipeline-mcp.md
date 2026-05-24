# Ingestion Pipeline MCP Server

*Container: `wikijs_ingestion` | Port: `8002` | Transport: SSE | Tools: 7*

Document ingestion pipeline: detect → extract text (with OCR for scanned docs) → chunk → embed → upsert to Qdrant.

## Container

```yaml
ingestion-pipeline:
  build: ./mcp-servers/ingestion-pipeline
  image: wiki-js-ingestion-pipeline:latest
  ports: ["8002:8002"]
  depends_on: [qdrant-db:healthy]
  environment:
    QDRANT_URL: http://qdrant-db:6334
    QDRANT_COLLECTION_DOCUMENTS: documents
    INGESTION_DB: /data/ingestion.db
```

## Tool Catalog

| # | Tool | Purpose |
|---|------|---------|
| 1 | `ingest_detect_type` | Classify file type and OCR requirement |
| 2 | `ingest_document` | Process a single document end-to-end |
| 3 | `ingest_directory` | Batch process all files in a directory |
| 4 | `ingest_get_status` | Check ingestion status for one or all documents |
| 5 | `ingest_delete_document` | Remove document chunks from Qdrant and SQLite |
| 6 | `ingest_search_chunks` | Semantic search within ingested documents |
| 7 | `ingest_list_documents` | List all ingested documents |

## Supported File Types

| Type | Extensions | Parser | OCR |
|------|-----------|--------|-----|
| PDF (text) | `.pdf` | `pdf_parser.py` (PyMuPDF) | No |
| PDF (scanned) | `.pdf` | `pdf_parser.py` (hybrid) | Yes (pytesseract) |
| DOCX (text) | `.docx` | `python-docx` | No |
| DOCX (with images) | `.docx` | `python-docx` + image extraction | Yes |
| Markdown | `.md` | `text_parser.py` | No |
| Plain text | `.txt` | `text_parser.py` | No |
| Images | `.png`, `.jpg`, `.tiff` | Direct OCR | Yes (pytesseract) |

## Pipeline Stages

1. **Detect** — Classify file type and determine if OCR is needed (PyMuPDF heuristics)
2. **Extract** — Parse text from native format, or OCR if scanned/image
3. **Chunk** — Split into overlapping sections (~1500 chars target, section-aware)
4. **Embed** — Compute 384-dim vectors with `all-MiniLM-L6-v2`
5. **Upsert** — Store chunks in Qdrant `documents` collection
6. **Record** — Log ingestion metadata in SQLite (`ingestion.db`)

## Idempotency

Re-ingesting the same file (same path + content hash) updates existing chunks rather than creating duplicates. The `content_hash` field in Qdrant payload and SQLite ensures idempotent operations.

## Storage

- **Qdrant**: `documents` collection — vector embeddings + payload (document_id, chunk_index, file_type, text)
- **SQLite**: `ingestion.db` — `IngestedDocument`, `DocumentChunk`, `PageChunkReference` tables

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant-db:6334` | Qdrant REST endpoint |
| `QDRANT_COLLECTION_DOCUMENTS` | `documents` | Target Qdrant collection |
| `INGESTION_DB` | `/data/ingestion.db` | SQLite metadata database |
| `CHUNK_SIZE` | 1500 | Target characters per chunk |
| `CHUNK_OVERLAP` | 200 | Character overlap between chunks |
