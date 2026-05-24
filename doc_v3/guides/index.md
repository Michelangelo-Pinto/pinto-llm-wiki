# Guides

Practical guides for using wiki-js-mcp v3 across setup, workflows, and operations.

## Quick Navigation

| Document | Description | When to read |
|----------|-------------|--------------|
| [Quickstart](quickstart.md) | 8-container setup in 5 minutes | First time setup |
| [Multi-MCP Setup](multi-mcp-setup.md) | Cursor configuration for 4 MCP servers | After Quickstart, before using tools |
| [Docker Operations](docker-operations.md) | Build, test, debug commands | Day-to-day development |
| [Troubleshooting](troubleshooting.md) | Common operational issues: containers, ports, Cursor, memory | Something is broken and you need to fix it |
| [Development Setup](development-setup.md) | Dev environment, repo structure, local testing | Contributing to the project |
| [LLM Wiki Workflows](llm-wiki-workflows.md) | Ingest, Query, Lint, Navigation, Document Processing | Core agent operations |
| [OCR and Ingestion](ocr-and-ingestion-workflows.md) | Document processing workflow guide | Processing external files (PDF, DOCX, images) |
| [Import / Export](import-export.md) | Markdown roundtrip with YAML frontmatter | Offline editing, backups, bulk refactoring |
| [Tesseract OCR Research](tesseract-ocr-research.md) | Full OCR deployment, API, benchmarks, MCP design | Understanding OCR tradeoffs and internals |

## Agent Reading Order

For an LLM agent operating against wiki-js-mcp v3, read in this order:

1. **[LLM Wiki Workflows](llm-wiki-workflows.md)** — The four core workflows (Ingest, Query, Lint, Document Processing). This is the primary operating manual.
2. **[OCR and Ingestion](ocr-and-ingestion-workflows.md)** — How to process external documents into Qdrant for semantic search.
3. **[Import / Export](import-export.md)** — Markdown format spec and roundtrip procedures.
4. **[Docker Operations](docker-operations.md)** — Build/test/debug commands when things go wrong.

Setup guides ([Quickstart](quickstart.md), [Multi-MCP Setup](multi-mcp-setup.md)) are for human operators, not agents.

## Related Sections

- [Tool Catalog](../reference/tool-catalog.md) — All ~65 tools with signatures
- [MCP Servers](../mcp-servers/index.md) — Per-server documentation
- [Features](../features/index.md) — Feature catalog by priority
- [Migration from v2](../migration/index.md) — v2 to v3 migration steps
