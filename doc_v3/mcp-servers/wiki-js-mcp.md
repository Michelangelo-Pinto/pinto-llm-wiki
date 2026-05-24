# Wiki.js MCP Server

*Container: `wikijs_mcp` | Port: `8000` | Transport: SSE | Tools: ~43*

Primary MCP server wrapping Wiki.js GraphQL API with semantic search via Qdrant.

## Container

```yaml
wiki-js-mcp:
  build: ./mcp-servers/wiki-js-mcp
  image: wiki-js-mcp:latest
  ports: ["8000:8000"]
  depends_on: [setup:completed, wiki:healthy]
  environment:
    WIKIJS_API_URL: http://wiki:3000
    QDRANT_URL: http://qdrant-db:6334
```

## Tool Catalog

### Page Management (26 tools)

| Tool | Purpose |
|------|---------|
| `wikijs_create_page` | Create a new wiki page |
| `wikijs_update_page` | Update page title or content |
| `wikijs_get_page` | Get page by ID or slug |
| `wikijs_search_pages` | Full-text keyword search |
| `wikijs_list_spaces` | List all wiki spaces |
| `wikijs_create_space` | Create a new space container |
| `wikijs_bulk_get_pages` | Get multiple pages in one call |
| `wikijs_get_backlinks` | Get pages linking to this page |
| `wikijs_rebuild_backlink_index` | Rebuild the backlink index |
| `wikijs_get_page_stats` | Word count, tags, link stats |
| `wikijs_bulk_get_page_stats` | Batch page statistics |
| `wikijs_append_to_page` | Append/prepend content to a page |
| `wikijs_search_by_tag` | Search pages by tag (with subtag support) |
| `wikijs_list_all_tags` | List all tags (flat or hierarchical) |
| `wikijs_set_page_tags` | Replace tags on a page |
| `wikijs_filter_pages` | Multi-facet filter (tag, isPublished, etc.) |
| `wikijs_smart_query` | Hybrid search: keyword + semantic (Qdrant) |
| `wikijs_get_recent_changes` | Recently modified pages |
| `wikijs_wiki_stats` | Total pages, most linked, etc. |
| `wikijs_wiki_health` | 7 health checks (orphans, untagged, etc.) |
| `wikijs_get_affected_pages` | Pages semantically related + linked |
| `wikijs_export_wiki` | Export all pages to markdown directory |
| `wikijs_export_page` | Export single page to markdown |
| `wikijs_import_page` | Import markdown file as wiki page |
| `wikijs_import_directory` | Import directory tree as wiki pages |

### Graph Analysis (3 tools)

| Tool | Purpose |
|------|---------|
| `wikijs_extract_page_links` | Internal and external links from a page |
| `wikijs_get_page_graph` | Link graph around a page (configurable depth) |
| `wikijs_find_shortest_path` | Shortest link path between two pages |

### Hierarchy (4 tools)

| Tool | Purpose |
|------|---------|
| `wikijs_create_repo_structure` | Create docs/sections structure |
| `wikijs_create_nested_page` | Create child page under parent path |
| `wikijs_get_page_children` | List child pages |
| `wikijs_create_documentation_hierarchy` | Auto-organize file mappings |

### File Integration (4 tools)

| Tool | Purpose |
|------|---------|
| `wikijs_link_file_to_page` | Map a source file to a wiki page |
| `wikijs_sync_file_docs` | Sync file changes to wiki documentation |
| `wikijs_generate_file_overview` | Generate AST/code overview from file |
| `wikijs_bulk_update_project_docs` | Batch sync multiple files |

### Deletion (4 tools)

| Tool | Purpose |
|------|---------|
| `wikijs_delete_page` | Delete a single page |
| `wikijs_batch_delete_pages` | Delete multiple pages |
| `wikijs_delete_hierarchy` | Delete page hierarchy (children_only/full) |
| `wikijs_cleanup_orphaned_mappings` | Clean up stale file mappings |

### System (3 tools)

| Tool | Purpose |
|------|---------|
| `wikijs_connection_status` | Wiki.js and Qdrant connectivity |
| `wikijs_repository_context` | Git repository context |
| `wikijs_manage_collections` | Manage wiki page collections |

## Smart Query

`wikijs_smart_query` is the primary search tool. It combines:

1. **Full-text search** via Wiki.js GraphQL (keyword match)
2. **Semantic search** via Qdrant (vector similarity)
3. **RRF fusion** (Reciprocal Rank Fusion) of both result sets
4. **Fallback** to keyword-only if Qdrant is unavailable

Parameters:
- `query` — Search query string
- `limit` — Max results (default 10)
- `include_summaries` — Include content snippets
- `include_link_context` — Include inbound link counts

## v3 Changes

| Removed (v2) | Replacement (v3) |
|--------------|-----------------|
| `wikijs_vector_search` | `wikijs_smart_query` (semantic path via Qdrant) |
| `wikijs_rebuild_vector_index` | Qdrant handles indexing automatically |
| `PageVector` SQLite model | Qdrant `wiki_pages` collection |
| Embedded sentence-transformers | Qdrant MCP `compute_embedding` |
