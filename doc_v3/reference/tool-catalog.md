# Tool Catalog

Complete reference for all **~65 MCP tools** across 4 servers. Wiki.js MCP tools are async; Qdrant, Ingestion, and Tesseract tools are synchronous. All return JSON strings.

## Wiki.js MCP (~43 tools)

Source: [`mcp-servers/wiki-js-mcp/src/wiki_mcp_server/`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/)

### Page Management (25 tools)

[`tools_pages.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py)

| # | Tool | Signature | Phase |
|---|------|-----------|-------|
| 1 | `wikijs_create_page` | `(title, content, space_id?, parent_id?)` | — |
| 2 | `wikijs_update_page` | `(page_id, title?, content?)` | — |
| 3 | `wikijs_get_page` | `(page_id?, slug?)` | — |
| 4 | `wikijs_search_pages` | `(query, space_id?)` | — |
| 5 | `wikijs_list_spaces` | — | — |
| 6 | `wikijs_create_space` | `(name, description?)` | — |
| 7 | `wikijs_bulk_get_pages` | `(page_ids, include_content?)` | P1 |
| 8 | `wikijs_get_backlinks` | `(page_id)` | P1 |
| 9 | `wikijs_rebuild_backlink_index` | — | P1 |
| 10 | `wikijs_get_page_stats` | `(page_id)` | P1 |
| 11 | `wikijs_bulk_get_page_stats` | `(page_ids)` | P1 |
| 12 | `wikijs_append_to_page` | `(page_id, content, position?)` | P2 |
| 13 | `wikijs_search_by_tag` | `(tag, include_subtags?)` | P2 |
| 14 | `wikijs_list_all_tags` | `(hierarchical?)` | P2 |
| 15 | `wikijs_set_page_tags` | `(page_id, tags)` | P2 |
| 16 | `wikijs_filter_pages` | `(filters)` | P2 |
| 17 | `wikijs_smart_query` | `(query, limit?, include_summaries?, include_link_context?)` | P2 |
| 18 | `wikijs_get_recent_changes` | `(limit?, since_days?, since_date?)` | P3 |
| 19 | `wikijs_wiki_stats` | — | P4 |
| 20 | `wikijs_wiki_health` | `(include_checks?, exclude_page_ids?, exclude_paths?)` | P3 |
| 21 | `wikijs_get_affected_pages` | `(page_id, max_results?, include_reasoning?)` | P4 |
| 22 | `wikijs_export_wiki` | `(output_dir, include_frontmatter?)` | — |
| 23 | `wikijs_export_page` | `(page_id, output_path?, include_frontmatter?)` | — |
| 24 | `wikijs_import_page` | `(file_path, target_path?, parent_id?, update_existing?)` | — |
| 25 | `wikijs_import_directory` | `(dir_path, base_parent_path?, update_existing?)` | — |

**Removed in v3**: `wikijs_vector_search`, `wikijs_rebuild_vector_index` — use Qdrant MCP instead.

### Graph (3 tools)

[`tools_graph.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_graph.py)

| # | Tool | Signature | Phase |
|---|------|-----------|-------|
| 26 | `wikijs_extract_page_links` | `(page_id, link_type?)` | P2 |
| 27 | `wikijs_get_page_graph` | `(page_id, depth?, direction?, max_nodes?)` | P2 |
| 28 | `wikijs_find_shortest_path` | `(from_page_id, to_page_id, max_depth?)` | P2 |

### Hierarchy (4 tools)

[`tools_hierarchy.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_hierarchy.py)

| # | Tool | Signature |
|---|------|-----------|
| 29 | `wikijs_create_repo_structure` | `(repo_name, description?, sections?)` |
| 30 | `wikijs_create_nested_page` | `(title, content, parent_path, create_parent_if_missing?)` |
| 31 | `wikijs_get_page_children` | `(page_id?, page_path?)` |
| 32 | `wikijs_create_documentation_hierarchy` | `(project_name, file_mappings, auto_organize?)` |

### File Integration (4 tools)

[`tools_files.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_files.py)

| # | Tool | Signature |
|---|------|-----------|
| 33 | `wikijs_link_file_to_page` | `(file_path, page_id, relationship?)` |
| 34 | `wikijs_sync_file_docs` | `(file_path, change_summary, snippet?)` |
| 35 | `wikijs_generate_file_overview` | `(file_path, include_functions?, include_classes?, include_dependencies?, include_examples?, target_page_id?)` |
| 36 | `wikijs_bulk_update_project_docs` | `(summary, affected_files, context, auto_create_missing?)` |

### Deletion (4 tools)

[`tools_deletion.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_deletion.py)

| # | Tool | Signature |
|---|------|-----------|
| 37 | `wikijs_delete_page` | `(page_id?, page_path?, remove_file_mapping?)` |
| 38 | `wikijs_batch_delete_pages` | `(page_ids?, page_paths?, path_pattern?, confirm_deletion, remove_file_mappings?)` |
| 39 | `wikijs_delete_hierarchy` | `(root_path, delete_mode, confirm_deletion, remove_file_mappings?)` |
| 40 | `wikijs_cleanup_orphaned_mappings` | — |

### System (3 tools)

[`tools_system.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_system.py)

| # | Tool | Signature |
|---|------|-----------|
| 41 | `wikijs_connection_status` | — |
| 42 | `wikijs_repository_context` | — |
| 43 | `wikijs_manage_collections` | `(collection_name, description?, space_ids?)` |

---

## Qdrant MCP (8 tools)

Source: [`qdrant_mcp/tools.py`](../../mcp-servers/qdrant-mcp/src/qdrant_mcp/tools.py)

| # | Tool | Signature |
|---|------|-----------|
| 1 | `qdrant_create_collection` | `(name, vector_size?, distance?)` |
| 2 | `qdrant_list_collections` | — |
| 3 | `qdrant_collection_info` | `(name)` |
| 4 | `qdrant_delete_collection` | `(name)` |
| 5 | `qdrant_search` | `(collection, query_text, limit?, filters?, score_threshold?, with_payload?)` |
| 6 | `qdrant_upsert_chunks` | `(collection, chunks)` |
| 7 | `qdrant_delete_by_filter` | `(collection, filter)` |
| 8 | `qdrant_scroll` | `(collection, limit?, offset?, with_payload?, with_vector=False)` |

Container config: [qdrant-mcp.md](../mcp-servers/qdrant-mcp.md)

---

## Ingestion Pipeline (7 tools)

Source: [`ingestion_pipeline/tools.py`](../../mcp-servers/ingestion-pipeline/src/ingestion_pipeline/tools.py)

| # | Tool | Signature |
|---|------|-----------|
| 1 | `ingest_detect_type` | `(file_path)` |
| 2 | `ingest_document` | `(file_path, collection?, chunk_size?, chunk_overlap?, force?)` |
| 3 | `ingest_directory` | `(dir_path, collection?, recursive?, file_patterns?)` |
| 4 | `ingest_get_status` | `(document_id?)` |
| 5 | `ingest_delete_document` | `(document_id, collection?)` |
| 6 | `ingest_search_chunks` | `(query, collection?, limit=10, filters?)` |
| 7 | `ingest_list_documents` | — |

Container config: [ingestion-pipeline-mcp.md](../mcp-servers/ingestion-pipeline-mcp.md)

---

## Tesseract MCP (7 tools)

Source: [`tesseract_mcp/tools.py`](../../mcp-servers/tesseract-mcp/src/tesseract_mcp/tools.py)

| # | Tool | Signature |
|---|------|-----------|
| 1 | `ocr_get_languages` | — |
| 2 | `ocr_detect_document_type` | `(input_path)` |
| 3 | `ocr_extract_text` | `(input_path, language?, output_format?, page_range?, dpi?, psm?)` |
| 4 | `ocr_extract_hocr` | `(input_path, language?, page_range?)` |
| 5 | `ocr_get_confidence` | `(input_path, language?)` |
| 6 | `ocr_process_document` | `(input_path, language?, auto_detect_type=True, preprocess=True, dpi=300)` |
| 7 | `ocr_preprocess_and_extract` | `(input_path, language?, preprocess_steps?)` |

Container config: [tesseract-mcp.md](../mcp-servers/tesseract-mcp.md)

---

## Return format

Success:
```json
{"pageId": 7, "title": "Auth", "status": "created"}
```

Error:
```json
{"error": "Failed to create page: ..."}
```

See [Tool Structure](../patterns/tool-structure.md) for the canonical pattern.
