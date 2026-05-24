# Error Catalog

Organized catalog of common errors across all 4 MCP servers in wiki-js-mcp v3. Each entry includes the typical error message, likely cause, and resolution.

> For operation-level troubleshooting (containers, Docker, SSE), see [Troubleshooting](../guides/troubleshooting.md).
> For a compact view, see [Quick Reference](quick-reference.md).

## Wiki.js MCP Errors (port 8000)

### Authentication

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Authentication failed: ..."}` | JWT token expired or credentials wrong | Check `.env` `WIKIJS_TOKEN` or `WIKIJS_PASSWORD`. Restart `wiki-js-mcp` |
| `{"error": "Connection to Wiki.js failed"}` | Wiki.js container not healthy | `docker compose ps`, wait for `wiki` to show `healthy`. `docker compose logs wiki` |
| `GraphQL request failed: 401` | Token invalid after Wiki.js restart | Restart `wiki-js-mcp`: `docker compose restart wiki-js-mcp` |

### Page Operations

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Page not found"}` | Wrong page ID or path | Use `wikijs_search_pages` to find the correct ID. Page IDs are integers, not paths |
| `{"error": "Page with path '...' already exists"}` | Duplicate page path | Use `wikijs_update_page` instead of `create_page`, or choose a different path |
| `{"error": "Bulk get exceeded max pages (50)"}` | Requested > 50 pages in one call | Split into multiple `bulk_get_pages` calls or use `smart_query` to prioritize |
| `{"error": "Invalid page ID"}` | Passed a string instead of integer | Page IDs are integers. Convert: `int(page_id)` |

### Smart Query

| Error | Cause | Resolution |
|-------|-------|------------|
| `Keyword search failed, semantic search failed` | Both Wiki.js and Qdrant unavailable | Check `docker compose ps`. Both `wiki` and `qdrant-db` must be healthy |
| `{"error": "Qdrant collection 'wiki_pages' not found"}` | Collection never created or was deleted | Create via: `qdrant_create_collection("wiki_pages", vector_size=384)` or run `seed_wiki_docs.py` |
| `Fallback to keyword-only mode` | Qdrant is unavailable but Wiki.js OK | Check Qdrant health: `curl localhost:6334/collections`. Restart `qdrant-db` if needed |

### Backlinks / Graph

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Backlink index is empty"}` | Backlinks never built or index was cleared | Run `wikijs_rebuild_backlink_index()` first |
| `{"error": "Shortest path: max_depth exceeded"}` | No path found within 5 hops | Increase `max_depth` (max recommended: 10). Or manually inspect link graph |
| `{"error": "max_nodes limit reached (50)"}` | Graph exploration hit limit | Increase `max_nodes` or increase `depth` for more focused exploration |

### Import/Export

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Invalid YAML frontmatter"}` | Malformed `---` delimiters in .md file | Ensure frontmatter has exactly two `---` lines (opening and closing) |
| `Body contains '---' which breaks YAML parsing` | Horizontal rule in content | Use `* * *` instead of `---` for horizontal rules |
| `{"error": "No .md files found in directory"}` | Wrong directory or extension | Only `.md` files are processed. `.txt`, `.markdown` are ignored |
| `{"error": "Wiki path '...' exceeds max depth"}` | Too deep hierarchy | Wiki.js supports max 5 levels. Flatten or restructure |

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
| `{"error": "File not found: /data/shared/..."}` | File not in shared volume | Copy file to a path under `/data/shared/`. Check volume mount: `docker compose exec ingestion-pipeline ls /data/shared/` |
| `{"error": "Directory not found: ..."}` | Wrong directory path | Verify path exists and is a directory. Use absolute paths |

### Document Type

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Unsupported file type: .xyz"}` | File extension not in supported list | Supported: `.pdf`, `.docx`, `.doc`, `.md`, `.markdown`, `.txt`, `.rst`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.gif`, `.webp` |
| `{"error": "PDF detection failed"}` | Corrupt PDF or PyMuPDF error | Check PDF integrity. Try opening with a PDF reader. Logs show details |

### Extraction

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "No text extracted from document"}` | Empty document, fully scanned with no OCR, or corrupted file | Check file content. For scanned PDFs, ensure Tesseract is installed in container. Try `ocr_extract_text` from Tesseract MCP directly |
| `{"error": "DOCX parsing failed"}` | Corrupt DOCX file | Try opening in Word/LibreOffice and re-saving. Check `docker compose logs ingestion-pipeline` |

### Qdrant

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Upsert to Qdrant failed"}` | Qdrant unavailable, collection missing, or network error | Check `docker compose ps qdrant-db`. Verify `documents` collection exists. `curl localhost:6334/collections` |
| `{"error": "Qdrant connection refused"}` | Qdrant-db container not running | `docker compose up -d qdrant-db`. Wait for healthy status |

### Idempotency

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"status": "skipped"}` (not an error, but unexpected) | File was already ingested and content hasn't changed | This is normal behavior. Use `force=True` to re-ingest: `ingest_document(file_path, force=True)` |
| `{"error": "UNIQUE constraint failed: ingested_documents.content_hash"}` | Same file ingested twice without force flag (race condition) | Use `force=True` or delete first: `ingest_delete_document(document_id)` then re-ingest |

## Tesseract MCP Errors (port 8003)

### Language

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "Language 'deu' not installed"}` | Requested language pack not in Docker image | Only `eng` and `ita` are installed by default. Add more in Dockerfile: `apt-get install tesseract-ocr-deu` |
| `Invalid language specification` | Wrong format | Use `+` separator: `"eng+ita"`, not `"eng,ita"` or `"eng ita"` |

### File Access

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"error": "File not found: ..."}` | File not accessible to container | Copy to shared volume. Check `docker compose exec tesseract-mcp ls /data/shared/` |
| `{"error": "Not a valid PDF file"}` | File exists but is not a valid PDF (OCR detection) | Verify file integrity. Check file header |

### OCR Quality

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"average_confidence": 12.3}` (very low) | Low-quality scan, wrong language, or image too small | Use `ocr_preprocess_and_extract` for denoising+deskew. Try different `psm` mode. Upscale low-DPI images |
| `{"error": "OCR processing failed"}` | Tesseract binary error or OOM | Check `docker compose logs tesseract-mcp`. Low memory may cause Tesseract crash |
| `{"error": "Image decoding failed"}` | Corrupt image or unsupported format | Verify image integrity. Supported: PNG, JPG, TIFF, BMP |

## Cross-Cutting Errors

### Docker / Network

| Error | Cause | Resolution |
|-------|-------|------------|
| `Connection refused` on any SSE endpoint | Container not running or crashed | `docker compose ps`, `docker compose up -d`, `docker compose logs <service>` |
| `Connection timeout` | Docker network issue or container overloaded | Check Docker network: `docker network ls`. Restart Docker daemon if persistent |
| `port is already allocated` | Port conflict with another process | Change port in `.env`. Or stop conflicting process: `lsof -i :8000` |

### SSE / MCP Transport

| Error | Cause | Resolution |
|-------|-------|------------|
| Cursor shows "Server not connected" | SSE endpoint not responding | `curl http://localhost:8000/sse`. Restart Cursor after fixing |
| `{"jsonrpc":"2.0","error":{"code":-32601,"message":"Method not found"}}` | Wrong tool name or server | Check tool exists on correct server. Use `tools/list` to verify |
| `Endpoint event not received` | SSE connection dropped | Cursor may need restart. Check `docker compose logs <mcp-server>` |

### Memory / Resource

| Error | Cause | Resolution |
|-------|-------|------------|
| Container OOM-killed (exit code 137) | Insufficient RAM for 8 containers | At least 8 GB RAM recommended. Increase Docker memory limit. Stop unused containers |
| Tesseract "Killed" during OCR | Large PDF exceeds memory | Process PDFs in smaller batches. Consider paginating large documents |
| Embedding model "CUDA out of memory" | GPU memory issue (if using GPU) | Model is CPU-only by default. No GPU needed for `all-MiniLM-L6-v2` |

## Related Documents

- [Troubleshooting](../guides/troubleshooting.md) — Operational fixes for Docker, containers, Cursor config
- [Quick Reference](quick-reference.md) — Compact tool and config reference
- [Testing Guide](testing.md) — How to verify system health with tests
