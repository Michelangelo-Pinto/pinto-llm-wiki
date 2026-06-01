# Ingestion Pipeline MCP Server

*Container: `pinto_llm_ingestion` | Port: `8002` | Transport: SSE | Tools: 7*

Document ingestion pipeline: detect → extract text (with OCR for scanned docs) → chunk → embed → upsert to Qdrant.

> **Design document:** [Ingestion Pipeline Design](../architecture/ingestion-pipeline-design.md) — full technical design of the pipeline stages, chunking algorithm, OCR routing, and state machine.

## Container

```yaml
ingestion-pipeline:
  build: ./mcp-servers/ingestion-pipeline
  image: pinto-llm-ingestion-pipeline:latest
  ports: ["8002:8002"]
  depends_on: [qdrant-db:healthy]
  environment:
    QDRANT_URL: http://qdrant-db:6334
    QDRANT_COLLECTION_DOCUMENTS: documents
    INGESTION_DB: /data/ingestion.db
```

Image size: ~1 GB (includes Tesseract binary + pre-downloaded `all-MiniLM-L6-v2` ~80 MB).

## Tool Catalog

| # | Tool | Signature | Purpose |
|---|------|-----------|---------|
| 1 | `ingest_detect_type` | `(file_path)` | Classify file type and OCR requirement |
| 2 | `ingest_document` | `(file_path, collection?, chunk_size=1500, chunk_overlap=200, force=False)` | Process a single document end-to-end |
| 3 | `ingest_directory` | `(dir_path, collection?, recursive=True, file_patterns?)` | Batch process all files in a directory |
| 4 | `ingest_get_status` | `(document_id?)` | Check ingestion status for one or all documents |
| 5 | `ingest_delete_document` | `(document_id, collection?)` | Remove document chunks from Qdrant and SQLite |
| 6 | `ingest_search_chunks` | `(query, collection?, limit=10, filters?)` | Semantic search within ingested documents |
| 7 | `ingest_list_documents` | — | List all ingested documents (alias for `ingest_get_status()`) |

## Supported File Types

| Type | Extensions | Parser | OCR | Subtype |
|------|-----------|--------|-----|---------|
| PDF (text) | `.pdf` | `pdf_parser.py` (PyMuPDF) | No | `text_pdf` |
| PDF (scanned) | `.pdf` | `pdf_parser.py` (hybrid) | Yes (pytesseract) | `scanned_pdf` |
| DOCX (text) | `.docx`, `.doc` | `python-docx` | No | `text_docx` |
| DOCX (with images) | `.docx`, `.doc` | `python-docx` + image extraction | Yes | `mixed_docx` |
| Markdown | `.md`, `.markdown` | `text_parser.py` | No | `markdown` |
| Plain text | `.txt`, `.rst` | `text_parser.py` | No | `text` |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.gif`, `.webp` | Direct OCR | Yes (pytesseract) | `image` |

## Pipeline Stages

```
detect → extract → chunk → embed → upsert → record
```

### 1. Detect (`detector.py`)

Classifies the file into a subtype and determines whether OCR is needed.

**PDF classification:** Samples first 5 pages via PyMuPDF. If average characters per page < 50 or >50% of pages are images, the PDF is classified as `scanned_pdf`.

**DOCX classification:** Checks for embedded images by inspecting `word/media/` inside the ZIP structure. If images found → `mixed_docx`.

**Images:** Always classified as `image` with `needs_ocr: true`.

### 2. Extract

- **Text PDF:** `pdf_parser.extract_text_pdf()` — PyMuPDF native text on every page
- **Scanned PDF:** `pdf_parser.extract_pdf_hybrid()` — per-page decision: native text if >100 chars and >20 words, otherwise OCR at 300 DPI
- **DOCX:** `python-docx` paragraphs; images OCR'd for `mixed_docx`
- **Text/Markdown:** `text_parser.extract_text()` with encoding fallback (UTF-8 → latin-1 → cp1252 → replacement)

### 3. Chunk (`chunker.py`)

Two-phase section-aware recursive chunking:
1. Split by structural boundaries (form feeds for PDF/DOCX, headings for markdown, paragraphs for text)
2. Split oversized sections at sentence boundaries with overlap

Parameters: `chunk_size=1500`, `chunk_overlap=200`, `max_chunk_size=2500`.

### 4. Embed (`embedder.py`)

Lazy singleton `SentenceTransformer("all-MiniLM-L6-v2")`. Encodes all chunks in a single batch. Vectors are L2-normalized. Model is pre-downloaded in Docker image (no cold start delay).

### 5. Upsert

One `PointStruct` per chunk, upserted to Qdrant `documents` collection in a single batch:

```json
{
  "id": "<uuid>",
  "vector": [0.12, -0.34, ...],
  "payload": {
    "document_id": "<content_hash[:16]>",
    "chunk_index": 0,
    "source_file": "/data/shared/report.pdf",
    "file_type": "text_pdf",
    "text": "Chunk content...",
    "content_hash": "<sha256_chunk[:16]>",
    "ingested_at": "2026-05-24T..."
  }
}
```

### 6. Record (`db.py`)

Writes `IngestedDocument` row to SQLite `ingestion.db`. SQLite failure is non-blocking (logged as warning).

## Document State Machine

Documents transition through these states:

```
pending → detecting → extracting → chunking → embedding → upserting → completed
    ↓         ↓           ↓            ↓          ↓           ↓
    └─────────┴───────────┴────────────┴──────────┴───────────→ failed
```

| State | Description |
|-------|-------------|
| `pending` | Initial state before any processing |
| `detecting` | Classifying file type and OCR needs |
| `extracting` | Parsing text from native format or OCR |
| `chunking` | Splitting text into overlapping chunks |
| `embedding` | Computing 384-dim vectors |
| `upserting` | Storing points in Qdrant |
| `completed` | All stages succeeded, SQLite recorded |
| `failed` | Any stage failed; `error_message` column captures reason |

**Current implementation:** Status is only written as `completed` at the end. Intermediate states are not persisted. If a stage fails, no SQLite row is written and `{"error": str(e)}` is returned.

## Idempotency

### File-level dedup

`_file_hash()` computes SHA-256 of the entire file (64 KB read chunks). Before processing, the hash is checked against `IngestedDocument.content_hash`:

- **Hash match, no force:** Returns `{"status": "skipped", "reason": "Already ingested (use force=True to re-ingest)"}`
- **Hash match, force=True:** Deletes existing Qdrant points and SQLite rows, re-ingests from scratch
- **No match:** Full pipeline runs

### Chunk-level dedup

Each chunk point in Qdrant includes a `content_hash` in its payload (SHA-256 of chunk text, 16 chars). This enables detecting individual chunk changes.

### Content hash computation

SHA-256 of the entire file, read in 64 KB chunks:

```python
import hashlib

def _file_hash(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
```

The `document_id` is derived from the content hash: `content_hash[:16]`.

## SQLite Schema (`ingestion.db`)

### `ingested_documents`

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer PK | Auto-increment |
| `document_id` | String(64) UNIQUE | content_hash[:16] |
| `source_file` | String | Original file path |
| `file_type` | String | Detected subtype |
| `file_size_bytes` | Integer | File size |
| `status` | String | `completed` or `failed` |
| `chunks_created` | Integer | Number of chunks |
| `error_message` | Text | Failure reason |
| `content_hash` | String(64) UNIQUE | SHA-256 of file |
| `ingested_at` | DateTime | Ingestion timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `document_chunks`

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer PK | Auto-increment |
| `document_id` | String(64) FK | → `ingested_documents.document_id` |
| `chunk_index` | Integer | Position in document |
| `chunk_hash` | String(64) | SHA-256 of chunk text |
| `page_number` | Integer (nullable) | Source page (PDF only) |
| `section_title` | String (nullable) | Section heading (markdown only) |
| `created_at` | DateTime | Creation timestamp |

Unique constraint: `(document_id, chunk_index)`.

### `page_chunk_references`

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer PK | Auto-increment |
| `wiki_page_id` | Integer | Wiki.js page ID |
| `chunk_id` | Integer FK | → `document_chunks.id` |
| `document_id` | String(64) | Redundant FK for queries |
| `linked_at` | DateTime | Link timestamp |

Unique constraint: `(wiki_page_id, chunk_id)`. Tracks which wiki pages reference ingested chunks.

## Logging

The pipeline logs at these key events:

| Event | Level | What to look for |
|-------|-------|-----------------|
| Embedding model load | INFO | `Loading embedding model: all-MiniLM-L6-v2` |
| Embedding model ready | INFO | `Embedding model loaded (384-dim)` |
| Ingestion failure | ERROR | `Ingestion failed for {path}: {error}` |
| SQLite tracking failure | WARNING | `Failed to track ingestion in SQLite: {error}` |
| PDF detection failure | ERROR | `PDF detection failed for {path}: {error}` |
| DOCX detection failure | ERROR | `DOCX detection failed for {path}: {error}` |

View logs: `docker compose logs ingestion-pipeline`

## Performance Benchmarks

| Document Type | Typical Latency | Bottleneck |
|---------------|-----------------|------------|
| Text PDF (10 pages) | ~2s | PyMuPDF extraction + embedding |
| Scanned PDF (10 pages) | ~30s | pytesseract OCR (~3s/page) |
| Text DOCX | ~1s | python-docx parsing + embedding |
| Mixed DOCX (with images) | ~5s | Image extraction + OCR |
| Markdown (< 20 KB) | <0.5s | Text reading + embedding |
| Single image | ~2-3s | pytesseract OCR |
| Batch 100 text files | ~20s | Cumulative embedding |

OCR (pytesseract in-process) is the dominant cost. The pipeline avoids MCP overhead by calling pytesseract directly.

## Batch Processing (`ingest_directory`)

Processes files sequentially (not parallel — CPU-bound). Default patterns: `*.pdf`, `*.docx`, `*.md`, `*.txt`, `*.png`, `*.jpg`, `*.jpeg`. Results truncated to 50 successes + 50 errors for readability.

Idempotency ensures re-running the directory skips already-ingested files.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant-db:6334` | Qdrant REST endpoint |
| `QDRANT_COLLECTION_DOCUMENTS` | `documents` | Target Qdrant collection |
| `INGESTION_DB` | `/data/ingestion.db` | SQLite metadata database |
| `CHUNK_SIZE` | 1500 | Target characters per chunk |
| `CHUNK_OVERLAP` | 200 | Character overlap between chunks |

## Related Documents

- [Ingestion Pipeline Design](../architecture/ingestion-pipeline-design.md) — Full technical design
- [OCR and Ingestion Workflows](../guides/ocr-and-ingestion-workflows.md) — Usage workflows
- [Qdrant Vector DB](../architecture/qdrant-vector-db.md) — Collection schema
- [Database](../architecture/database.md) — Full SQLite schema
- [Quick Reference](../reference/quick-reference.md) — All tools at a glance
