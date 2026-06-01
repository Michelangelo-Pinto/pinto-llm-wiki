# Tool Structure

Every MCP tool across all 3 v4 servers follows a consistent pattern.

## Core pattern

```python
@mcp.tool()
async def tool_name(params) -> str:
    """Docstring describing args and return value."""
    try:
        # ... business logic ...
        logger.info("summary: %d items", count)
        return json.dumps(result)
    except Exception as e:
        error_msg = f"Operation failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
```

Key points:
- **Return type `str`**: JSON-encoded string, never a dict.
- **Errors as JSON**: `{"error": "..."}`, never raised to the framework.
- **Log at INFO** for completion summaries, **ERROR** for failures.

## Tool registration

### Qdrant MCP, Ingestion Pipeline, Tesseract MCP

All tools are defined as plain functions in `tools.py` and registered explicitly in `server.py`:

```python
mcp.tool()(qdrant_search)
mcp.tool()(ingest_document)
mcp.tool()(ocr_extract_text)
```

## Server-specific patterns

### Qdrant MCP

- Verifies Qdrant connectivity on startup
- Uses lazy-loaded `SentenceTransformer("all-MiniLM-L6-v2")` for embedding
- Operations: collection CRUD, vector search, upsert, scroll, delete

### Ingestion Pipeline

- Direct Qdrant + filesystem access
- Uses `pytesseract` in-process for OCR (no MCP overhead)
- SHA-256 content hash for idempotent ingestion
- SQLite tracking via `ingestion.db`

### Tesseract MCP

- Stateless — reads files from shared volume `/data/shared/`
- Default languages: `eng+ita`
- Image preprocessing pipeline: grayscale → deskew → threshold → denoise → sharpen

## JSON return format

Success:
```json
{"status": "completed", "chunks_created": 12}
```

Error:
```json
{"error": "Failed to process: ..."}
```

Every return value goes through `json.dumps(...)`. No tool returns a raw Python dict or list.

## Tool categories per server

| Server | File | Count | Purpose |
|--------|------|-------|---------|
| Qdrant MCP | `tools.py` | 8 | Collection management, vector search, upsert, scroll |
| Ingestion Pipeline | `tools.py` | 7 | Document detect, ingest, search, status, delete |
| Tesseract MCP | `tools.py` | 7 | OCR extract, confidence, preprocessing, HOCR |

See [Tool Catalog](../reference/tool-catalog.md) for all tools with full signatures.
