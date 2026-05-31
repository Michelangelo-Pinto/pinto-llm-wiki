# Guides v4

Practical guides for using wiki-js-mcp v4 across setup, workflows, and operations.

## Quick Navigation

| Document | Description | When to read |
|----------|-------------|--------------|
| [Stack Lifecycle](stack-lifecycle.md) | Build, start, stop, rebuild the 5-container stack | Before operating MCP tools or after code changes |
| [Quickstart](quickstart.md) | 5-container setup in 5 minutes | First time setup |
| [Agent Orientation](agent-orientation.md) | How to instruct the LLM agent: prompt templates, conventions, what to ask | Before first agent interaction |
| [File Paths and Volumes](file-paths-and-volumes.md) | Where to put files for ingestion, how to use docker compose cp | Before ingesting documents |
| [Docker Operations](docker-operations.md) | Build, test, debug commands | Day-to-day development |
| [Troubleshooting](troubleshooting.md) | Common operational issues: containers, ports, Cursor, memory | Something is broken and you need to fix it |
| [Development Setup](development-setup.md) | Dev environment, repo structure, local testing | Contributing to the project |
| [LLM Wiki Workflows](llm-wiki-workflows.md) | Ingest, Query, Lint, Document Processing, OCR, Web, Multi-Hop, Enrichment | Core agent operations |
| [OCR and Ingestion](ocr-and-ingestion-workflows.md) | Document processing workflow guide | Processing external files (PDF, DOCX, images) |
| [Pre-Ingestion Analysis](pre-ingestion-analysis.md) | How the agent analyzes documents before ingestion | Before running ingest_document |
| [Multi-Hop Retrieval](multi-hop-retrieval.md) | Multi-pass semantic retrieval strategy | Complex cross-domain queries |
| [Subagents](subagents.md) | 4 subagent definitions (PreIngestion, EnrichmentReviewer, QueryPlanner, LintAuditor) | Delegating complex tasks |
| [Tesseract OCR Research](tesseract-ocr-research.md) | Full OCR deployment, API, benchmarks, MCP design | Understanding OCR tradeoffs and internals |

## Agent Reading Order

For an LLM agent operating against wiki-js-mcp v4, read in this order:

0. **[Stack Lifecycle](stack-lifecycle.md)** — Build, start, stop, rebuild. Ensure the stack is up before any MCP workflow.
1. **[LLM Wiki Workflows](llm-wiki-workflows.md)** — The eight core workflows (Ingest, Query, Lint, Document Processing, OCR, Web, Multi-Hop, Enrichment). This is the primary operating manual.
2. **[File Paths and Volumes](file-paths-and-volumes.md)** — Where files live in the container. Essential for ingestion.
3. **[Pre-Ingestion Analysis](pre-ingestion-analysis.md)** — How to analyze documents before ingestion and choose optimal parameters.
4. **[OCR and Ingestion](ocr-and-ingestion-workflows.md)** — How to process external documents into Qdrant for semantic search.
5. **[Multi-Hop Retrieval](multi-hop-retrieval.md)** — Multi-pass retrieval strategy for complex queries.
6. **[Subagents](subagents.md)** — 4 specialized subagents for delegation.
7. **[Docker Operations](docker-operations.md)** — Tests, DB inspection, advanced debugging when things go wrong.

Setup guides ([Quickstart](quickstart.md), [Agent Orientation](agent-orientation.md)) are primarily for human operators.

## Related Sections

- [Tool Catalog](../reference/tool-catalog.md) — All 26 tools with signatures
- [MCP Servers](../mcp-servers/index.md) — Per-server documentation
- [System Overview](../architecture/system-overview.md) — 5-container architecture
