# File Paths and Volumes

Where files go for ingestion, where export output lands, and how to move files between your host machine and the Docker containers.

## Volume Map

| Volume Name | Mount Inside Container | Purpose | Container | Access |
|-------------|----------------------|---------|-----------|--------|
| `shared_data` / `to_ingest/` | `/data/shared` | Files to ingest (PDF, DOCX, images, MD, HTML, JSON, XML, EPUB) | `ingestion-pipeline`, `tesseract-mcp`, `enrichment-pipeline` | Read-only (`:ro`) |
| `ingestion_data` | `/data` | SQLite database `ingestion.db` | `ingestion-pipeline` | Read-write |
| `ingestion_data` | `/data/ingestion` | Read `ingestion.db` (for enrichment tracking) | `enrichment-pipeline` | Read-only (`:ro`) |
| `enrichment_data` | `/data` | SQLite database `enrichment.db` | `enrichment-pipeline` | Read-write |
| `qdrant_data` | `/qdrant/storage` | Qdrant vector embeddings | `qdrant-db` | Read-write |
| `qdrant_snapshots` | `/qdrant/snapshots` | Qdrant backups | `qdrant-db` | Read-write |
| `./knowledge` | `/app/knowledge` | Enrichment config (read/write) | `enrichment-pipeline` | Read-write |

## How to Place Files for Ingestion

The ingestion pipeline reads files from `/data/shared/` inside the container. There are two ways to get files there:

### Method 1: `docker compose cp` (recommended)

Copy files directly into the running container:

```bash
# Copy a single file
docker compose cp report.pdf ingestion-pipeline:/data/shared/

# Copy a directory of documents
docker compose cp ./my-docs/ ingestion-pipeline:/data/shared/
```

Then ingest:

```python
# From the LLM agent (Cursor):
ingest_document(file_path="/data/shared/report.pdf")

# Or via curl (SSE JSON-RPC protocol; prefer MCP client tools):
curl -X POST http://localhost:8002/sse \
  -d '{"tool":"ingest_document","params":{"file_path":"/data/shared/report.pdf"}}'
```

### Method 2: Use the `to_ingest/` directory

The `to_ingest/` directory in the repo root is bind-mounted to `/data/shared` in the containers. Simply copy files there:

```bash
cp /path/to/your/document.pdf to_ingest/
```

Then ingest from `/data/shared/document.pdf` inside the container.

## Where Output Goes

### Ingested content

Ingested document chunks go to:
- **Qdrant**: `documents` collection (semantic search via `qdrant_search` or `ingest_search_chunks`)
- **SQLite**: `/data/ingestion.db` inside the `ingestion-pipeline` container

To inspect the ingestion database on your host:

```bash
# Copy SQLite DB to host
docker compose cp ingestion-pipeline:/data/ingestion.db ./ingestion.db

# Inspect locally
sqlite3 ./ingestion.db "SELECT document_id, source_file, status, chunks_created FROM ingested_documents;"
```

## Enrichment Output

Enrichment results are stored in:
- **Qdrant**: Enriched payload layers 3-5 (classification, references, chunk metadata)
- **SQLite**: `/data/enrichment.db` inside the `enrichment-pipeline` container

To inspect on your host:

```bash
docker compose cp enrichment-pipeline:/data/enrichment.db ./enrichment.db
sqlite3 ./enrichment.db "SELECT document_id, strategy, status, llm_calls FROM enrichment_runs;"
```

## Path Summary

| Operation | Tool | Path parameter | How to access from host |
|-----------|------|---------------|------------------------|
| Ingest a document | `ingest_document` | `/data/shared/` | Copy to `to_ingest/` dir |
| Ingest a directory | `ingest_directory` | `/data/shared/` | Copy files to `to_ingest/` dir |
| OCR a document | `ocr_extract_text` | `/data/shared/` | Same as ingestion |
| Enrich document | `enrich_document` | N/A (uses document_id) | Check `enrich_get_status(document_id)` |
| Knowledge base | `Read`/`Write`/`Grep` | `knowledge/` path | Direct filesystem access on host |

## Volume Persistence

| Volume | Survives `docker compose down`? | Survives `docker compose down -v`? |
|--------|-------------------------------|----------------------------------|
| `qdrant_data` | Yes | No |
| `qdrant_snapshots` | Yes | No |
| `ingestion_data` | Yes | No |
| `enrichment_data` | Yes | No |

**To reset everything to a clean state:**

```bash
docker compose down -v   # Removes ALL data including Qdrant vectors, ingestion SQLite, enrichment SQLite
```

**To reset only ingestion state (keep Qdrant and enrichment):**

```bash
docker compose exec ingestion-pipeline rm /data/ingestion.db
docker compose restart ingestion-pipeline
```

## Related Documents

- [System Overview](../architecture/system-overview.md) — Volume table and container topology
- [Quickstart](quickstart.md) — First-time setup
- [OCR and Ingestion Workflows](ocr-and-ingestion-workflows.md) — Document processing usage
- [Import / Export](import-export.md) — Markdown roundtrip format and workflow
- [Docker Operations](docker-operations.md) — Build, test, debug commands
