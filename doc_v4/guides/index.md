# Guides v4

Practical guides for using wiki-js-mcp v4 across setup, workflows, and operations.

## Quick Navigation

| Document | Description | When to read |
|----------|-------------|--------------|
| [Stack Lifecycle](stack-lifecycle.md) | Build, start, stop, rebuild the 4-container stack | Before operating MCP tools or after code changes |
| [Quickstart](quickstart.md) | 4-container setup in 5 minutes | First time setup |
| [Agent Orientation](agent-orientation.md) | How to instruct the LLM agent: prompt templates, conventions, what to ask | Before first agent interaction |
| [File Paths and Volumes](file-paths-and-volumes.md) | Where to put files for ingestion, how to use docker compose cp | Before ingesting documents |
| [Docker Operations](docker-operations.md) | Build, test, debug commands | Day-to-day development |
| [Troubleshooting](troubleshooting.md) | Common operational issues: containers, ports, Cursor, memory | Something is broken and you need to fix it |
| [Development Setup](development-setup.md) | Dev environment, repo structure, local testing | Contributing to the project |
| [LLM Wiki Workflows](llm-wiki-workflows.md) | Ingest, Query, Lint, Document Processing, OCR, Web | Core agent operations |
| [OCR and Ingestion](ocr-and-ingestion-workflows.md) | Document processing workflow guide | Processing external files (PDF, DOCX, images) |
| [Tesseract OCR Research](tesseract-ocr-research.md) | Full OCR deployment, API, benchmarks, MCP design | Understanding OCR tradeoffs and internals |

## Agent Reading Order

For an LLM agent operating against wiki-js-mcp v4, read in this order:

0. **[Stack Lifecycle](stack-lifecycle.md)** — Build, start, stop, rebuild. Ensure the stack is up before any MCP workflow.
1. **[LLM Wiki Workflows](llm-wiki-workflows.md)** — The six core workflows (Ingest, Query, Lint, Document Processing, OCR, Web). This is the primary operating manual.
2. **[File Paths and Volumes](file-paths-and-volumes.md)** — Where files live in the container. Essential for ingestion.
3. **[OCR and Ingestion](ocr-and-ingestion-workflows.md)** — How to process external documents into Qdrant for semantic search.
4. **[Docker Operations](docker-operations.md)** — Tests, DB inspection, advanced debugging when things go wrong.

Setup guides ([Quickstart](quickstart.md), [Agent Orientation](agent-orientation.md)) are primarily for human operators.

## Related Sections

- [Tool Catalog](../reference/tool-catalog.md) — All 22 tools with signatures
- [MCP Servers](../mcp-servers/index.md) — Per-server documentation
- [System Overview](../architecture/system-overview.md) — 4-container architecture
