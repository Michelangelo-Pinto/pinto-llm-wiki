# OCR and Ingestion Workflows

Document processing guide for the Ingestion Pipeline and Tesseract MCP server.

## Quick Start

```bash
# Ingest a single document (via curl SSE JSON-RPC; prefer MCP client tools)
curl -X POST http://localhost:8002/sse -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ingest_document","arguments":{"file_path":"/data/shared/report.pdf"}},"id":1}'

# Or via the MCP tool in Cursor/Claude:
ingest_document(file_path="/path/to/report.pdf")
```

## Document Ingestion Pipeline

The pipeline processes documents in 6 stages:

```
detect → extract → chunk → embed → upsert → record
```

### Stage 1: Detect

PyMuPDF classifies the file type and determines if OCR is needed:

| File | Detection | OCR Needed? |
|------|-----------|-------------|
| Text PDF | PyMuPDF extracts text directly | No |
| Scanned PDF | No extractable text in pages | Yes (pytesseract) |
| DOCX (text) | python-docx extracts text | No |
| DOCX (images) | python-docx + image extraction | Yes |
| Markdown | Read directly | No |
| Plain text | Read directly | No |
| Image (PNG/JPG) | Direct OCR | Yes |

### Stage 2: Extract

Text is extracted from the native format. For scanned documents and images, pytesseract OCR runs with English and Italian language support. OCR quality is tracked per-word via confidence scores.

### Stage 3: Chunk

Section-aware recursive chunking splits text into overlapping chunks (~1500 chars target, 200 char overlap). Chunk boundaries respect paragraph and section breaks.

### Stage 4: Embed

Each chunk is converted to a 384-dimensional vector using `all-MiniLM-L6-v2`. The embedder is loaded lazily (first call ~2s, subsequent calls ~50ms).

### Stage 5: Upsert

Chunks are stored in the Qdrant `documents` collection with payload:

```json
{
  "document_id": "uuid",
  "chunk_index": 0,
  "file_type": "pdf",
  "source_path": "/data/report.pdf",
  "text": "Chunk content..."
}
```

### Stage 6: Record

Ingestion metadata is logged in SQLite (`ingestion.db`) for tracking and idempotency.

## Idempotency

Re-ingesting the same file (same path + content hash) updates existing chunks rather than creating duplicates:

```python
# Second ingest of the same file is a no-op
ingest_document(file_path="report.pdf")  # "status": "skipped" if unchanged
ingest_document(file_path="report.pdf", force=True)  # Force re-processing
```

## Agent-Facing OCR (Tesseract MCP)

For ad-hoc OCR needs, use the Tesseract MCP server directly:

```python
# Extract text from an image
ocr_extract_text(file_path="/data/scan.png", language="eng+ita")

# Detect document type
ocr_detect_document_type(file_path="/data/report.pdf")

# Get per-word confidence scores
ocr_get_confidence(file_path="/data/scan.png")

# Preprocess and extract (grayscale, deskew, denoise, OCR)
ocr_preprocess_and_extract(file_path="/data/low_quality.png")
```

The Tesseract MCP server is for agent-driven OCR. The Ingestion Pipeline uses pytesseract in-process for batch performance.

## Batch Processing

For bulk document ingestion:

```python
# Ingest a directory recursively
ingest_directory(dir_path="/data/documents/")

# Check progress
ingest_get_status()

# List all ingested documents
ingest_list_documents()
```

## Searching Ingested Content

After ingestion, search the Qdrant `documents` collection:

```python
# Direct Qdrant search
qdrant_search(
    collection_name="documents",
    query="authentication methods",
    limit=10
)

# With payload filter
qdrant_search(
    collection_name="documents",
    query="architecture",
    limit=10,
    filters={"must": [{"key": "file_type", "match": {"value": "pdf"}}]}
)
```

## Creating Wiki Pages from Documents

Chain ingestion with Wiki.js tools:

```python
# 1. Ingest document
result = ingest_document(file_path="architecture.pdf")

# 2. Search for relevant chunks
chunks = qdrant_search("documents", "microservices architecture", limit=5)

# 3. Create a wiki page from the best chunks
content = "\n\n".join(c["payload"]["text"] for c in chunks["results"])
wikijs_create_page(
    title="Architecture Overview (from architecture.pdf)",
    content=content
)
```

## Supported Languages

The default Docker images include:
- **English** (`eng`)
- **Italian** (`ita`)

Add more languages by installing additional `tesseract-ocr-*` packages in the Dockerfiles.

## Performance

| Operation | Typical Latency |
|-----------|----------------|
| Text PDF (10 pages) | ~2s |
| Scanned PDF (10 pages, OCR) | ~30s |
| DOCX (text only) | ~1s |
| Single image OCR | ~2-3s |
| Markdown file | <0.5s |
| Batch 100 text files | ~20s |

For production throughput, the Ingestion Pipeline uses pytesseract in-process. The Tesseract MCP server adds ~30ms overhead per call for SSE serialization.
