# Improvements

Future enhancements and optimization opportunities for wiki-js-mcp v3.

## Short-term (quick wins)

| Improvement | Effort | Impact |
|-------------|--------|--------|
| **SSE smoke tests for all 65 tools** | Medium | Validate full tool surface via SSE (current tests use direct imports) | ✅ Completed in v3 |
| **Unit test suite** | Large | ~80 unit tests as outlined in test strategy; enables faster iteration | ✅ Completed in v3 (~109 tests) |
| **CI pipeline (GitHub Actions)** | Small | Automated test runs on PRs (workflow exists in `.github/workflows/`) | ✅ Completed in v3 |
| **SQLite indexes on BacklinkIndex** | Small | Faster BFS/graph queries at 1000+ pages | ✅ Completed in v3 |
| **Pre-download embedding model in Dockerfile** | Small | Eliminates cold start delay on first embedding call | ✅ Completed in v3 |

## Medium-term enhancements

| Enhancement | Description |
|-------------|-------------|
| **Qdrant collection replication** | Multi-node Qdrant for high availability and horizontal scaling |
| **Monitoring and metrics** | Prometheus metrics for MCP server health, Qdrant performance, ingestion throughput |
| **Webhook-driven cache invalidation** | Replace polling-based monitoring with Wiki.js webhooks for instant BacklinkIndex updates |
| **ONNX runtime for embeddings** | Replace PyTorch with ONNX for lighter Docker images and faster inference |
| **Document chunking improvements** | Section-aware chunking for all document types, semantic chunk boundaries |
| **Stale detection threshold config** | Move 90-day threshold from hardcoded to environment variable (`WIKIJS_STALE_THRESHOLD_DAYS`) |

## Long-term vision

| Vision | Description |
|--------|-------------|
| **Contradiction detection** | NLP-based check comparing pages with high similarity but opposing claims; requires LLM |
| **Automatic summary generation** | Use a local LLM (e.g. Ollama) to generate page summaries on create/update |
| **RAG pipeline integration** | Use wiki-js-mcp as a knowledge base backend for RAG (Retrieval-Augmented Generation) |
| **Multi-language OCR** | Expand Tesseract language packs beyond English and Italian |
| **Streaming MCP responses** | Use FastMCP streaming for long-running operations (ingestion, rebuild_index) |

## Features Completed in v3

These v2 roadmap items were delivered in v3:

| v2 Vision | v3 Implementation |
|-----------|-------------------|
| External vector engine (replacing SQLite) | Qdrant vector database with native KNN |
| OCR for document processing | Tesseract MCP server + Ingestion Pipeline |
| Multi-MCP architecture | 4 independent MCP servers |
| Docker image size reduction | wiki-mcp from ~1.5 GB to ~200 MB |
| Full document ingestion pipeline | Ingestion Pipeline with 7 tools |
| sqlite-vec integration | Replaced by Qdrant (superior to sqlite-vec) |

## Semantic search roadmap

See [Qdrant Enhancements](qdrant-enhancements.md) for features to enhance via Qdrant vector search.

## Related Sections

- [Architecture](../architecture/index.md) — System design and Qdrant details
- [Features](../features/index.md) — Current feature catalog
- [Migration from v2](../migration/index.md) — v2 to v3 migration steps
