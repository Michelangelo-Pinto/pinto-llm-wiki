# Tool Catalog v4

Complete reference for all **26 MCP tools** across 4 servers. All tools return JSON strings. Exceptions are caught and returned as `{"error": "..."}`.

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

Supported formats: PDF, DOCX, MD, TXT, RST, HTML, JSON, XML, EPUB, images.

| # | Tool | Signature |
|---|------|-----------|
| 1 | `ingest_detect_type` | `(file_path)` |
| 2 | `ingest_document` | `(file_path, collection?, chunk_size?, chunk_overlap?, force?)` |
| 3 | `ingest_directory` | `(dir_path, collection?, recursive?, file_patterns?)` |
| 4 | `ingest_get_status` | `(document_id?)` |
| 5 | `ingest_delete_document` | `(document_id, collection?)` |
| 6 | `ingest_search_chunks` | `(query, collection?, limit=10, filters?)` |
| 7 | `ingest_list_documents` | — |

Payload: 5-layer schema. See [Payload Schema](payload-schema.md).

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

## Enrichment Pipeline (4 tools)

Source: [`enrichment_pipeline/tools.py`](../../mcp-servers/enrichment-pipeline/src/enrichment_pipeline/tools.py)

Post-ingestion enrichment via LangGraph. Default disabled — see `knowledge/enrichment-config.md`.

| # | Tool | Signature |
|---|------|-----------|
| 1 | `enrich_get_config` | — |
| 2 | `enrich_set_config` | `(key, value)` |
| 3 | `enrich_document` | `(document_id, collection?)` |
| 4 | `enrich_get_status` | `(document_id?)` |

Container config: [enrichment-pipeline-mcp.md](../mcp-servers/enrichment-pipeline-mcp.md)

---

## Return format

Success:
```json
{"status": "completed", "document_id": "abc123", "chunks_created": 24}
```

Error:
```json
{"error": "Failed to ingest document: ..."}
```

See [Tool Structure](../patterns/tool-structure.md) for the canonical pattern.
