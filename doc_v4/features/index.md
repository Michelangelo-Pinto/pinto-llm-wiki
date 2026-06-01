# Features

Tool features organized by MCP server in wiki-js-mcp v4.

## Qdrant MCP (8 tools)

- **Collection management**: Create, list, inspect, delete collections
- **Vector search**: Semantic search with score threshold and payload filtering
- **Vector upsert**: Batch insert embedding chunks
- **Filtered deletion**: Delete points by filter criteria
- **Scroll pagination**: Iterate over collection points

## Ingestion Pipeline (7 tools)

- **File type detection**: Identify PDF, DOCX, Markdown, text, images
- **Document ingestion**: Full pipeline (detect → extract → chunk → embed → upsert)
- **Directory ingestion**: Batch process multiple files
- **Chunk search**: Search within ingested document chunks
- **Status tracking**: Monitor ingestion progress and document list

## Tesseract MCP (7 tools)

- **OCR extraction**: Extract text from images and scanned PDFs
- **HOCR output**: Structured OCR with positional data
- **Confidence scoring**: Per-page OCR quality assessment
- **Image preprocessing**: Deskew, denoise, threshold for accuracy improvement
- **Language support**: English + Italian (`eng+ita`)

## Knowledge Base (file-system)

In v4, knowledge lives as markdown files in `knowledge/`:

- **Content creation**: Agent writes `.md` files with `Write`
- **Keyword search**: `Grep` across `knowledge/**/*.md`
- **Semantic search**: `qdrant_search` via Qdrant MCP
- **Routing**: Every directory has `index.md` with file listings
- **Diagrams**: Mermaid and other markdown-renderable formats

## Related Documents

- [Tool Catalog](../reference/tool-catalog.md) — All 22 tools with full signatures
- [MCP Servers](../mcp-servers/index.md) — Per-server documentation
- [LLM Wiki Workflows](../guides/llm-wiki-workflows.md) — Operating workflows
