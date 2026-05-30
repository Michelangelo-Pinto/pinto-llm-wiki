# File Paths and Volumes

Where files go for ingestion, where export output lands, and how to move files between your host machine and the Docker containers.

## Volume Map

| Volume Name | Mount Inside Container | Purpose | Container | Access |
|-------------|----------------------|---------|-----------|--------|
| `shared_data` | `/data/shared` | Files to ingest (PDF, DOCX, images, MD) and exported `.md` files | `ingestion-pipeline`, `tesseract-mcp` | Read-only (`:ro`) |
| `ingestion_data` | `/data` | SQLite database `ingestion.db` | `ingestion-pipeline` | Read-write |
| `mcp_data` | `/data` | SQLite database `wikijs_mappings.db` | `wiki-js-mcp` | Read-write |
| `mcp_logs` | `/logs` | MCP server logs | `wiki-js-mcp` | Read-write |
| `db_data` | `/var/lib/postgresql/data` | PostgreSQL wiki content | `db` | Read-write |
| `qdrant_data` | `/qdrant/storage` | Qdrant vector embeddings | `qdrant-db` | Read-write |
| `qdrant_snapshots` | `/qdrant/snapshots` | Qdrant backups | `qdrant-db` | Read-write |

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

### Method 2: Bind mount a host directory

Edit `docker-compose.override.yml` (create if missing):

```yaml
services:
  ingestion-pipeline:
    volumes:
      - ./data/ingest:/data/shared:ro
```

Then place files in `./data/ingest/` on your host. They appear at `/data/shared/` inside the container. Run `docker compose up -d` after editing.

## Where Export Output Goes

### Wiki export (`wikijs_export_wiki`, `wikijs_export_page`)

The export tools write `.md` files inside the `wiki-js-mcp` container. The `output_dir` parameter is relative to the container filesystem, **not** your host.

**To extract exported files from the container:**

```bash
# After the agent runs:
# wikijs_export_wiki("/data/shared/wiki-export")

# Extract the exported files to your host:
docker compose cp wiki-js-mcp:/data/shared/wiki-export ./wiki-export
```

Now `./wiki-export/` on your host contains all the `.md` files.

### Ingestion output

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

## How to Load Files for Import

### Wiki import (`wikijs_import_page`, `wikijs_import_directory`)

The import tools read `.md` files from the container filesystem. First copy files into the container:

```bash
# Copy your .md files to the container
docker compose cp ./my-edited-pages/ wiki-js-mcp:/data/shared/import-pages/

# Then tell the agent:
# wikijs_import_directory("/data/shared/import-pages", update_existing=True)
```

### Full roundtrip: Edit wiki pages offline

```bash
# 1. Export from wiki (agent runs this):
# wikijs_export_wiki("/data/shared/full-export")

# 2. Extract to host
docker compose cp wiki-js-mcp:/data/shared/full-export ./full-export

# 3. Edit .md files locally (Obsidian, VS Code, etc.)

# 4. Load back into container
docker compose cp ./full-export wiki-js-mcp:/data/shared/full-export

# 5. Import back (agent runs this):
# wikijs_import_directory("/data/shared/full-export", update_existing=True)
```

## Path Summary

| Operation | Tool | Path parameter | Filesystem | How to access from host |
|-----------|------|---------------|------------|------------------------|
| Ingest a document | `ingest_document` | `/data/shared/` | Container | `docker compose cp <host_file> ingestion-pipeline:/data/shared/` |
| Ingest a directory | `ingest_directory` | `/data/shared/` | Container | `docker compose cp <host_dir> ingestion-pipeline:/data/shared/` |
| OCR a document | `ocr_extract_text` | `/data/shared/` | Container | Same as ingestion |
| Export wiki | `wikijs_export_wiki` | `/data/shared/...` | Container | `docker compose cp wiki-js-mcp:/data/shared/<dir> <host_dir>` |
| Export single page | `wikijs_export_page` | `/data/shared/...` | Container | Same as above |
| Import page | `wikijs_import_page` | `/data/shared/...` | Container | `docker compose cp <host_file> wiki-js-mcp:/data/shared/` |
| Import directory | `wikijs_import_directory` | `/data/shared/...` | Container | `docker compose cp <host_dir> wiki-js-mcp:/data/shared/` |

## Volume Persistence

| Volume | Survives `docker compose down`? | Survives `docker compose down -v`? |
|--------|-------------------------------|----------------------------------|
| `db_data` | Yes | No (deleted with `-v`) |
| `mcp_data` | Yes | No |
| `mcp_logs` | Yes | No |
| `qdrant_data` | Yes | No |
| `qdrant_snapshots` | Yes | No |
| `shared_data` | Yes | No |
| `ingestion_data` | Yes | No |

**To reset everything to a clean state:**

```bash
docker compose down -v   # Removes ALL data including PostgreSQL, Qdrant, and SQLite
```

**To reset only ingestion state (keep wiki content):**

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
