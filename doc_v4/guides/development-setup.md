# Development Setup

How to set up a development environment for contributing to wiki-js-mcp v4.

## Prerequisites

- **Python 3.12** (the base image version)
- **Docker** and Docker Compose v2
- **Git**
- ~10 GB free disk space (Docker images + test data)

## Repository Structure

```
wiki-js-mcp/
├── docker-compose.yml              # 5-container stack
├── .env.example                    # Template environment variables
├── mcp-servers/
│   ├── qdrant-mcp/                # Qdrant MCP server (8 tools)
│   │   └── src/qdrant_mcp/
│   │       ├── server.py
│   │       ├── tools.py
│   │       └── embedder.py         # Lazy SentenceTransformer singleton
│   ├── ingestion-pipeline/         # Ingestion Pipeline (7 tools)
│   │   └── src/ingestion_pipeline/
│   │       ├── server.py
│   │       ├── tools.py
│   │       ├── db.py               # SQLAlchemy models (ingestion.db)
│   │       ├── chunker.py          # Section-aware recursive chunking
│   │       ├── embedder.py         # Lazy SentenceTransformer singleton
│   │       ├── detector.py         # PyMuPDF file type detection
│   │       ├── payload.py          # 5-layer Qdrant payload builder
│   │       └── parsers/
│   │           ├── pdf_parser.py   # Hybrid PDF text extraction
│   │           ├── text_parser.py  # Text/Markdown parser
│   │           ├── html_parser.py  # HTML extraction (BeautifulSoup)
│   │           ├── json_parser.py  # JSON to structured text
│   │           ├── xml_parser.py   # XML extraction
│   │           └── epub_parser.py  # EPUB chapter extraction
│   ├── tesseract-mcp/             # Tesseract MCP server (7 tools)
│   │   └── src/tesseract_mcp/
│   │       ├── server.py
│   │       ├── tools.py
│   │       ├── detector.py         # PyMuPDF text sampling heuristic
│   │       └── preprocess.py       # OCR preprocessing pipeline
│   └── enrichment-pipeline/       # Enrichment Pipeline (4 tools)
│       └── src/enrichment_pipeline/
│           ├── server.py           # FastMCP entry point
│           ├── tools.py            # 4 enrichment tools
│           ├── graph.py            # LangGraph StateGraph
│           ├── config.py           # Hot-reload YAML frontmatter
│           ├── db.py               # SQLAlchemy models (enrichment.db)
│           ├── logger.py           # Structured JSON-lines logging
│           └── nodes/
│               ├── pre_analysis.py      # Strategy decision
│               ├── classifier.py        # Document classification (LLM)
│               ├── reference_extractor.py  # Reference extraction (LLM)
│               ├── chunk_mapper.py      # Reference→chunk mapping
│               ├── chunk_enricher.py    # Per-chunk heuristics
│               └── upsert.py            # Enriched payload upsert
├── tests/
│   ├── unit/                       # ~109 unit tests (no Docker required)
│   ├── integration/
│   │   ├── qdrant/                 # 26 Qdrant integration tests
│   │   └── stack/                  # ~10-15 full-stack tests
│   ├── e2e/                        # 27 ingestion E2E tests
│   ├── performance/                # 7 benchmarks
│   ├── smoke/                      # ~37 SSE smoke tests
│   └── regression/                 # ~10 wiki regression tests
└── doc_v3/                         # Documentation (this directory)
```

## First-Time Setup

```bash
# 1. Clone
git clone https://github.com/mikep/wiki-js-mcp.git
cd wiki-js-mcp

# 2. Configure environment
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD

# 3. Start the full stack
docker compose up -d

# 4. Verify
docker compose ps
curl http://localhost:8000/sse   # Wiki.js MCP
curl http://localhost:8001/sse   # Qdrant MCP
```

## Development Workflow

### Edit → Test → Build → Verify

#### 1. Run unit tests (fast, no Docker)

Unit tests run without any containers. Make changes, then:

```bash
PYTHONPATH="mcp-servers/qdrant-mcp/src:mcp-servers/ingestion-pipeline/src:mcp-servers/tesseract-mcp/src:mcp-servers/enrichment-pipeline/src" \
pytest tests/unit/ -v -m unit
```

This is the fastest feedback loop. Run after every change.

#### 2. Run integration tests (Qdrant only)

Requires Qdrant running. Tests import tool functions directly (no SSE).

```bash
docker compose --profile test run --rm test-runner pytest tests/integration/qdrant/ tests/e2e/ tests/performance/ -v
```

#### 3. Build and restart affected services

After code changes, rebuild and restart:

```bash
docker compose build ingestion-pipeline
docker compose up -d ingestion-pipeline
```

Or for all changed services:

```bash
docker compose build
docker compose up -d
```

#### 4. Run full-stack tests

Requires the complete 5-container stack:

```bash
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/regression/ tests/smoke/ -v
```

### Code change matrix

| Changed file(s) | What to rebuild | What to test |
|-----------------|----------------|-------------|
| `ingestion_pipeline/*.py` | `ingestion-pipeline` | unit + e2e |
| `enrichment_pipeline/*.py` | `enrichment-pipeline` | unit + integration |
| `qdrant_mcp/*.py` | `qdrant-mcp` | unit + integration/qdrant |
| `ingestion_pipeline/*.py` | `ingestion-pipeline` | unit + e2e |
| `tesseract_mcp/*.py` | `tesseract-mcp` | unit + smoke |
| `docker-compose.yml` | All | full-stack + regression |
| `.env` | All | full-stack |
| `Dockerfile` (any) | Affected image | integration + e2e |

## Running Individual Tests

```bash
# Run a single test module
docker compose --profile test run --rm test-runner \
  pytest tests/integration/qdrant/test_qdrant_mcp.py -v

# Run a single test function
docker compose --profile test run --rm test-runner \
  pytest tests/integration/qdrant/test_qdrant_mcp.py::TestSearch::test_search_returns_results -v

# Run tests matching a keyword
docker compose --profile test run --rm test-runner \
  pytest tests/ -v -k "ingest"
```

## Local Development Without Docker

For faster iteration on unit tests and pure Python logic:

```bash
# Set up venv
python3.12 -m venv venv
source venv/bin/activate

# Install test dependencies
pip install sqlalchemy qdrant-client sentence-transformers pytest pytest-mock

# Run unit tests
PYTHONPATH="mcp-servers/qdrant-mcp/src:mcp-servers/ingestion-pipeline/src:mcp-servers/tesseract-mcp/src:mcp-servers/enrichment-pipeline/src" \
pytest tests/unit/ -v -m unit
```

Module-level unit tests use `unittest.mock.patch` and `pytest-mock` to isolate pure logic from external dependencies (Qdrant client, file system, Tesseract binary).

## Debugging Inside Containers

```bash
# Access a container shell
docker compose exec ingestion-pipeline bash

# Access Qdrant directly
docker compose exec qdrant-mcp python3 -c "
from qdrant_client import QdrantClient
client = QdrantClient(url='http://qdrant-db:6334')
print(client.get_collections())
"

# Access SQLite databases
docker compose exec ingestion-pipeline sqlite3 /data/ingestion.db ".tables"
docker compose exec ingestion-pipeline sqlite3 /data/ingestion.db ".tables"

# View live logs
docker compose logs -f ingestion-pipeline
docker compose logs -f ingestion-pipeline
```

## Seeding Test Data

```bash
# Seed structured docs pages into Wiki.js
# Run ingestion on a test file
docker compose exec ingestion-pipeline python3 -c "
from ingestion_pipeline.tools import ingest_document
print(ingest_document('/data/shared/test.md'))
"

# This creates ~20 pages with cross-references for testing backlinks, graph, and search

# Generate E2E test fixtures (PDF, DOCX, images)
docker compose run --rm \
  -v ./tests/test-data:/data/test-data \
  ingestion-pipeline \
  python /data/test-data/generate_test_data.py
```

## Code Conventions

See [Patterns](../patterns/index.md) for full details:

- **Tool structure:** `@mcp.tool()` decorator, JSON return strings, `async def` for Wiki.js MCP
- **Authentication:** Double-checked locking in `client.py`
- **GraphQL queries:** Named constants (`_UPPER_CASE`), `asyncio.gather` for parallel calls
- **SQLite sessions:** `get_db()` → try/commit/rollback → `finally: db.close()`
- **Fire-and-forget hooks:** Side effects (backlinks, cache invalidation) don't fail the main operation
- **Lazy imports:** Heavy deps (SentenceTransformer, QdrantClient) imported inside functions

## CI Pipeline

GitHub Actions in `.github/workflows/test.yml`:

- **`qdrant-tests`** (fast, ~3 min): Runs on every push/PR. Requires only `qdrant-db`
- **`stack-tests`** (full-stack, ~5 min): Runs on push to `main`. Requires full 5-container stack

## Related Documents

- [Docker Operations](docker-operations.md) — Build, test, debug commands
- [Testing Guide](../reference/testing.md) — Full test pyramid and suite catalog
- [Patterns](../patterns/index.md) — Code conventions
- [Architecture](../architecture/index.md) — System design and module map
- [Troubleshooting](troubleshooting.md) — Common issues and fixes
