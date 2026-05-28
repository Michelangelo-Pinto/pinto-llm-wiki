# Stack Lifecycle Guide

Commands to build, start, stop, and rebuild the 8-container wiki-js-mcp v3 stack. Read this before operating MCP tools or after changing server code.

For tests, DB inspection, and advanced debugging, see [Docker Operations](docker-operations.md).

## When to Use

- **Cold start** — first time or after `docker compose down`
- **After code changes** — rebuilt MCP server images (`mcp-servers/`)
- **Before integration tests** — full stack must be running
- **Connection errors** — MCP tools fail with connection refused / timeout on ports 8000–8003

## Prerequisites

- Docker and Docker Compose installed
- `.env` file at repo root (copy from `.env.example`)
- `POSTGRES_PASSWORD` set in `.env` (required by compose)

See [Quickstart](quickstart.md) for first-time setup.

## Container Map

| Compose service | Container | Port(s) | Steady state |
|-----------------|-----------|---------|--------------|
| `db` | `wikijs_db` | internal 5432 | running |
| `wiki` | `wikijs_app` | 3000 | running |
| `setup` | `wikijs_setup` | — | **exited 0** (one-shot) |
| `wiki-js-mcp` | `wikijs_mcp` | 8000 | running |
| `qdrant-db` | `wikijs_qdrant` | 6333 gRPC, 6334 REST | running |
| `qdrant-mcp` | `wikijs_qdrant_mcp` | 8001 | running |
| `ingestion-pipeline` | `wikijs_ingestion` | 8002 | running |
| `tesseract-mcp` | `wikijs_tesseract_mcp` | 8003 | running |

**Startup order:** `db` → `wiki` → `setup` (one-shot) → `qdrant-db` → `wiki-js-mcp` → `qdrant-mcp` / `ingestion-pipeline` → `tesseract-mcp`.

Four services are built from source (`wiki-js-mcp`, `qdrant-mcp`, `ingestion-pipeline`, `tesseract-mcp`); the rest use pre-built images.

## Core Commands

All commands run from the repository root.

### Build

```bash
# Build all custom images (MCP servers + test-runner image)
docker compose build

# Build and restart a single service
docker compose build qdrant-mcp
docker compose up -d qdrant-mcp

# Full rebuild ignoring cache (dependency or model changes)
docker compose build --no-cache
docker compose up -d
```

First build may take 5–10 minutes (sentence-transformer model baked into `qdrant-mcp` and `ingestion-pipeline` images).

### Start

```bash
# Start full stack in background
docker compose up -d

# Start and rebuild in one step
docker compose up -d --build
```

### Stop

```bash
# Stop all containers (volumes preserved)
docker compose down

# Stop and delete all volumes — DESTRUCTIVE: wipes DB, Qdrant, wiki data
docker compose down -v
```

Use `down -v` only when you intentionally want a clean slate. Requires explicit user confirmation before an agent runs it.

### Restart and inspect

```bash
# Restart one service
docker compose restart wiki-js-mcp

# Container status
docker compose ps

# Follow logs
docker compose logs -f qdrant-mcp

# Last 50 lines
docker compose logs --tail 50 ingestion-pipeline
```

## Verify Stack Is Ready

After `docker compose up -d`, wait ~60 seconds for health checks, then:

```bash
# Expect 7 Up + setup Exited (0)
docker compose ps

# MCP SSE endpoints (HTTP status check)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/sse   # Wiki.js MCP
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8001/sse   # Qdrant MCP
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8002/sse   # Ingestion Pipeline
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8003/sse   # Tesseract MCP
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000       # Wiki.js UI
```

Non-200 responses on MCP ports usually mean the service is still starting — wait and retry.

Once MCP servers respond, call `wikijs_connection_status` to confirm Wiki.js and Qdrant connectivity before ingest/query workflows.

## Common Scenarios

| Situation | Action |
|-----------|--------|
| Changed Python in `qdrant-mcp` | `docker compose build qdrant-mcp && docker compose up -d qdrant-mcp` |
| Changed code in multiple MCP servers | `docker compose build && docker compose up -d` |
| Port already in use | `docker compose ps`; stop conflicting process or change port in `.env` |
| `setup` container failed | `docker compose logs setup` — often Wiki.js already initialized; check `curl http://localhost:3000` |
| Qdrant unreachable from MCP | `curl http://localhost:6334/collections`; restart with `docker compose restart qdrant-db qdrant-mcp` |
| MCP tool connection refused | `docker compose ps`; start stack with `docker compose up -d` |
| Need fresh database | `docker compose down -v` then `docker compose up -d` (data loss) |

## Agent Boundaries

| Allowed (on explicit user request) | Not allowed without confirmation |
|-------------------------------------|-----------------------------------|
| `docker compose build` | Edit `.env` or `mcp.json` |
| `docker compose up -d` | `docker compose cp` |
| `docker compose down` | `docker compose down -v` |
| `docker compose restart <service>` | Install Tesseract languages |
| `docker compose logs`, `docker compose ps` | Place raw source files in `/data/shared` |

After starting the stack, always verify health (`docker compose ps` + curl checks or `wikijs_connection_status`) before proceeding with wiki operations.

## See Also

- [Docker Operations](docker-operations.md) — testing, seed data, DB inspection
- [Troubleshooting](troubleshooting.md) — common operational issues
- [Development Setup](development-setup.md) — local dev workflow
- [Quickstart](quickstart.md) — first-time 5-minute setup
- [System Overview](../architecture/system-overview.md) — architecture and data flow
