# Error Catalog v4

Organized catalog of common errors across all 4 MCP servers in wiki-js-mcp v4. Each entry includes the typical error message, likely cause, and resolution.

> For operation-level troubleshooting (containers, Docker, SSE), see [Troubleshooting](../guides/troubleshooting.md).
> For a compact view, see [Quick Reference](quick-reference.md).

## Qdrant MCP Errors (port 8001)

### Collection Management

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Collection 'X' not found"}` | Collection doesn't exist | Create it: `qdrant_create_collection(name, vector_size=384)`. Or let tools auto-create on first use |
| `{"error": "Collection 'X' already exists"}` | Duplicate collection name | Use existing collection, or delete+recreate: `qdrant_delete_collection(name)` then recreate |
| `{"error": "Invalid vector size: expected 384, got 768"}` | Wrong embedding model dimensions | Always use 384 for `all-MiniLM-L6-v2`. Recreate collection with correct size |

### Search

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Query text cannot be empty"}` | Empty query string | Provide non-empty query |
| `{"error": "No results found"}` | Score below threshold or empty collection | Lower `score_threshold` (default 0.0), check collection has points |
| `{"error": "Dimension mismatch"}` | Query vector dims don't match collection | Ensure embedding model matches. Both must be 384-dim (`all-MiniLM-L6-v2`) |
| `{"error": "Connection refused"}` | Qdrant DB container not running or not healthy | `docker compose ps`, check `qdrant-db` health. `docker compose restart qdrant-db` |

### Data Operations

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Upsert failed: payload too large"}` | Single point payload exceeds Qdrant limit | Reduce chunk text size. Qdrant max payload ~1 MB per point |
| `{"error": "Delete failed: invalid filter"}` | Malformed filter expression | Check filter syntax. Use `qdrant_scroll` first to verify filter matches expected documents |

## Ingestion Pipeline Errors (port 8002)

### File Access

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "File not found: /data/shared/..."}` | File not in shared volume | Copy file to a path under `/data/shared/` |
| `{"error": "Directory not found: ..."}` | Wrong directory path | Verify path exists and is a directory. Use absolute paths |

### Document Type

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Unsupported file type: .xyz"}` | File extension not in supported list | Supported: `.pdf`, `.docx`, `.md`, `.markdown`, `.txt`, `.rst`, `.html`, `.htm`, `.json`, `.xml`, `.epub`, `.png`, `.jpg`, `.tiff`, `.bmp`, `.gif`, `.webp` |
| `{"error": "PDF detection failed"}` | Corrupt PDF or PyMuPDF error | Check PDF integrity. Try opening with a PDF reader |

### Extraction

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "No text extracted from document"}` | Empty document or fully scanned with no OCR | Check file content. For scanned PDFs, use `ocr_extract_text` from Tesseract MCP first |
| `{"error": "DOCX parsing failed"}` | Corrupt DOCX file | Try opening in Word/LibreOffice and re-saving |

### Qdrant

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Upsert to Qdrant failed"}` | Qdrant unavailable or collection missing | Check `docker compose ps qdrant-db`. Verify `documents` collection exists |
| `{"error": "Qdrant connection refused"}` | Qdrant-db container not running | `docker compose up -d qdrant-db`. Wait for healthy status |

### Idempotency

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"status": "skipped"}` | File was already ingested and content hasn't changed | Normal behavior. Use `force=True` to re-ingest |

## Tesseract MCP Errors (port 8003)

### Language

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Language 'deu' not installed"}` | Requested language pack not in Docker image | Only `eng` and `ita` installed by default |
| `Invalid language specification` | Wrong format | Use `+` separator: `"eng+ita"`, not `"eng,ita"` |

### File Access

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "File not found: ..."}` | File not accessible to container | Copy to shared volume |
| `{"error": "Not a valid PDF file"}` | File exists but is not a valid PDF | Verify file integrity |

### OCR Quality

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"average_confidence": 12.3}` (very low) | Low-quality scan, wrong language | Use `ocr_preprocess_and_extract` for denoising+deskew. Try different `psm` mode |
| `{"error": "OCR processing failed"}` | Tesseract binary error or OOM | Check `docker compose logs tesseract-mcp` |
| `{"error": "Image decoding failed"}` | Corrupt image or unsupported format | Verify image integrity. Supported: PNG, JPG, TIFF, BMP |

## Enrichment Pipeline Errors (port 8004)

### Configuration

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Config file not found: ..."}` | `enrichment-config.md` missing or wrong path | Verify `knowledge/enrichment-config.md` exists. Check `ENRICHMENT_CONFIG_PATH` env var |
| `{"error": "Config file missing YAML frontmatter"}` | Config file has no `---` frontmatter block | Ensure the file starts with `---` delimited YAML frontmatter |

### Execution

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "No chunks found for document_id: ..."}` | Document not ingested yet or `document_id` wrong | Run `ingest_get_status(document_id)` first to verify ingestion completed |
| `{"error": "OPENAI_API_KEY not set"}` | Missing API key for LLM calls | Set `OPENAI_API_KEY` in `.env`. Without it, enrichment falls back to heuristics |
| `{"error": "Classification failed: ..."}` | OpenAI API error or invalid response | Check API key validity, rate limits. Heuristic fallback is used automatically |
| `{"error": "Enrichment failed for ...: ..."}` | Generic enrichment failure | Check `enrich_get_status(document_id)` for detailed step logs |

## Cross-Cutting Errors

### Docker / Network

| Error | Cause | Resolution |
|-------|-------|------------|
| `Connection refused` on any SSE endpoint | Container not running or crashed | `docker compose ps`, `docker compose up -d`, `docker compose logs <service>` |
| `Connection timeout` | Docker network issue or container overloaded | Check Docker network: `docker network ls` |
| `port is already allocated` | Port conflict with another process | Change port in `.env`. Or stop conflicting process: `lsof -i :8001` |

### SSE / MCP Transport

| Error | Cause | Resolution |
|-------|-------|------------|
| Cursor shows "Server not connected" | SSE endpoint not responding | `curl http://localhost:8001/sse`. Restart Cursor after fixing |
| `{"jsonrpc":"2.0","error":{"code":-32601,"message":"Method not found"}}` | Wrong tool name or server | Check tool exists on correct server |
| `Endpoint event not received` | SSE connection dropped | Cursor may need restart. Check `docker compose logs <mcp-server>` |

### Memory / Resource

| Error | Cause | Resolution |
|-------|-------|------------|
| Container OOM-killed (exit code 137) | Insufficient RAM | At least 4 GB RAM recommended for 5-container stack |
| Tesseract "Killed" during OCR | Large PDF exceeds memory | Process PDFs in smaller batches |
| Embedding model "CUDA out of memory" | GPU memory issue | Model is CPU-only by default. No GPU needed for `all-MiniLM-L6-v2` |

## Related Documents

- [Troubleshooting](../guides/troubleshooting.md) — Operational fixes for Docker, containers, Cursor config
- [Quick Reference](quick-reference.md) — Compact tool and config reference
- [Testing Guide](testing.md) — How to verify system health with tests
