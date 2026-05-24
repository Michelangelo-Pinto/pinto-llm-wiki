# Tool Structure

Every MCP tool across all 4 v3 servers follows a consistent pattern.

## Core pattern

```python
@mcp.tool()
async def tool_name(params) -> str:
    """Docstring describing args and return value."""
    try:
        await wikijs.authenticate()  # Wiki.js MCP only; others verify backend
        # ... business logic ...
        logger.info("summary: %d items", count)
        return json.dumps(result)
    except Exception as e:
        error_msg = f"Operation failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
```

Key points:
- **Always `async`**: Wiki.js MCP tools are `async def`. Qdrant, Ingestion, and Tesseract tools are synchronous `def` wrapped by FastMCP.
- **Return type `str`**: JSON-encoded string, never a dict.
- **Errors as JSON**: `{"error": "..."}`, never raised to the framework.
- **Log at INFO** for completion summaries, **ERROR** for failures.

## Authentication (Wiki.js MCP)

[`client.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/client.py)

Every Wiki.js tool calls `await wikijs.authenticate()` as its first meaningful action.

```python
async def authenticate(self) -> bool:
    if self.authenticated:          # Fast-path check
        return True
    async with self._auth_lock:     # Double-checked locking
        if self.authenticated:
            return True
        # ... JWT login or Bearer token ...
        self.authenticated = True
```

- **Double-checked locking**: Fast-path before lock, re-check inside lock. Prevents race on concurrent auth.
- **Two strategies**: `WIKIJS_TOKEN` / `WIKIJS_API_KEY` (preferred) or username/password login with JWT extraction.

Other servers authenticate differently:
- **Qdrant MCP**: Verifies Qdrant connectivity on startup (no user auth)
- **Ingestion Pipeline**: Direct Qdrant + filesystem access
- **Tesseract MCP**: Stateless; reads files from shared volume

## Tool registration

### Wiki.js MCP

[`server.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/server.py)

```python
mcp = FastMCP("Wiki.js Integration")

def _register_tools() -> None:
    from wiki_mcp_server import (
        tools_deletion, tools_files, tools_graph,
        tools_hierarchy, tools_pages, tools_system,
    )
```

Side-effect registration: `@mcp.tool()` decorator fires on import. `_register_tools()` just imports all modules.

### Other servers

Qdrant, Ingestion, and Tesseract register tools explicitly in `server.py`:

```python
mcp.tool()(qdrant_search)
mcp.tool()(ingest_document)
mcp.tool()(ocr_extract_text)
```

## JSON return format

Success:
```json
{"pageId": 7, "title": "Auth", "status": "created"}
```

Error:
```json
{"error": "Failed to create page: ..."}
```

Every return value goes through `json.dumps(...)`. No tool returns a raw Python dict or list.

## Tool categories (Wiki.js MCP)

| Module | File | Count | Purpose |
|--------|------|-------|---------|
| Page tools | `tools_pages.py` | 26 | CRUD, search, bulk, backlinks, stats, tags, smart_query, wiki tools, import/export |
| Graph tools | `tools_graph.py` | 3 | Link extraction, BFS, shortest path |
| Hierarchy | `tools_hierarchy.py` | 4 | Nested pages, repo structures |
| File integration | `tools_files.py` | 4 | File-to-page mapping, sync |
| Deletion | `tools_deletion.py` | 4 | Delete operations + cleanup |
| System | `tools_system.py` | 3 | Connection status, repo context, collections |

See [Tool Catalog](../reference/tool-catalog.md) for all servers.
