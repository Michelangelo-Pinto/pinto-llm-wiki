# Troubleshooting

Common operational issues in wiki-js-mcp v4 and how to resolve them.

> For tool-specific errors (Qdrant, ingestion), see [Error Catalog](../reference/error-catalog.md).

## Container Won't Start

### Symptom: Container exits immediately or shows `unhealthy`

```bash
docker compose ps
# Shows "unhealthy" or "restarting"
```

**Resolution:**

1. Check logs for the failing service:
   ```bash
   docker compose logs <service-name> --tail 50
   ```
2. Common causes:
   - **Qdrant not healthy:** `qdrant-mcp` and `ingestion-pipeline` depend on `qdrant-db:healthy`. Wait for `healthy` status
   - **Missing `.env`:** Copy `.env.example` to `.env`
   - **Port conflict:** See [Port Conflicts](#port-conflicts)
3. Restart the specific service:
   ```bash
   docker compose restart <service-name>
   ```
4. If persistent, full rebuild:
   ```bash
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   ```

## Port Conflicts

### Symptom: `port is already allocated` or `bind: address already in use`

Ports 8001-8003 and 6333-6334 must be free.

**Resolution:**

1. Check what's using a port:
   ```bash
   ss -tlnp | grep 8001
   ```
2. Options:
   - **Stop the conflicting process:** `kill <pid>`
   - **Change ports in `.env`:**
     ```ini
     QDRANT_MCP_PORT=8006
     INGESTION_MCP_PORT=8007
     ```
     Then update Cursor `mcp.json` to match.

## Cursor Doesn't Discover MCP Servers

### Symptom: Cursor shows no tools from wiki-js-mcp v4 servers

**Resolution:**

1. Verify the Docker stack is running:
   ```bash
   docker compose ps
   ```
   All 4 containers should show `healthy` or `running`.

2. Verify SSE endpoints respond:
   ```bash
   curl http://localhost:8001/sse   # Qdrant MCP
   curl http://localhost:8002/sse   # Ingestion Pipeline
   curl http://localhost:8003/sse   # Tesseract MCP
   ```
   Each should return SSE event stream headers (or at least not `Connection refused`).

3. Check `mcp.json` URLs match `.env` ports exactly:
   ```json
   {
     "mcpServers": {
       "qdrant":      { "url": "http://localhost:8001/sse" },
       "ingestion":   { "url": "http://localhost:8002/sse" },
       "tesseract":   { "url": "http://localhost:8003/sse" }
     }
   }
   ```

4. **Restart Cursor** after changing `mcp.json`. Cursor only discovers servers on startup.

5. If still not working, check Cursor logs:
   - Cursor > Help > Toggle Developer Tools > Console
   - Look for MCP connection errors

## SSE Endpoint Not Responding

### Symptom: `curl http://localhost:800X/sse` returns `Connection refused` or times out

**Resolution:**

1. Check if container is running:
   ```bash
   docker compose ps <service-name>
   ```
2. Check container logs:
   ```bash
   docker compose logs <service-name> --tail 100
   ```
3. Common causes:
   - **Qdrant not accessible:** MCP servers connect to Qdrant on startup. Check `docker compose ps qdrant-db`
4. Restart:
   ```bash
   docker compose restart <service-name>
   ```

## Permission Denied on Shared Volume

### Symptom: `ingest_document` returns `{"error": "File not found"}` even though file exists

The `shared_data` volume is mounted read-only (`:ro`) in MCP server containers. Files must be readable by the container's user.

**Resolution:**

1. Check permissions:
   ```bash
   docker compose exec ingestion-pipeline ls -la /data/shared/
   ```
2. Ensure files are world-readable:
   ```bash
   chmod 644 /path/to/shared/files/*
   ```
3. Ensure the shared directory is correctly mounted:
   ```bash
   docker compose exec ingestion-pipeline ls /data/shared/
   ```
   If empty, check your `docker-compose.yml` volume configuration.

## Insufficient Memory

### Symptom: Containers being OOM-killed (exit code 137), or system becomes very slow

The 4-container stack requires ~4 GB RAM minimum.

**Resolution:**

1. Check memory usage:
   ```bash
   docker stats --no-stream
   ```
2. Reduce memory pressure:
   - **Increase Docker memory limit:** Docker Desktop > Settings > Resources > Memory (set to 8+ GB)
   - **Stop unused containers:** `docker compose stop <service>` (e.g., `tesseract-mcp` if not using OCR)
3. Monitor which container is using most memory — Qdrant and Tesseract are typically the heaviest.

## Ingestion Pipeline Stalls

### Symptom: `ingest_document` or `ingest_directory` hangs indefinitely

**Resolution:**

1. Check if Qdrant is healthy:
   ```bash
   curl http://localhost:6334/collections
   ```
2. Check if the file is very large (>100 MB for PDF, >10 MB for image). OCR of large scanned PDFs can take several minutes.
3. Check logs for errors:
   ```bash
   docker compose logs ingestion-pipeline --tail 50
   ```
4. If Tesseract OCR is stuck, the language pack may be missing. Verify:
   ```bash
   docker compose exec ingestion-pipeline tesseract --list-langs
   ```
   Should show `eng` and `ita`.

## Database Corruption

### Symptom: SQLite errors like `database disk image is malformed`

**Resolution:**

1. **Ingestion database:** The ingestion SQLite (`ingestion.db`) lives in the `ingestion_data` Docker volume:
   ```bash
   docker compose exec ingestion-pipeline rm /data/ingestion.db
   docker compose restart ingestion-pipeline
   ```
   Note: Deleting `ingestion.db` loses ingestion history. All Qdrant data is preserved.

## Stale Environment Variables

### Symptom: Errors mentioning v3 variables like `WIKIJS_API_URL` or `POSTGRES_PASSWORD`

Your `.env` may have old v3 variables.

**Resolution:**

1. Copy `.env.example` fresh:
   ```bash
   cp .env.example .env
   ```
2. Rebuild containers:
   ```bash
   docker compose down
   docker compose up -d
   ```

## Quick Diagnostic Commands

```bash
# Are all containers running?
docker compose ps

# Do SSE endpoints respond?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/sse
curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/sse
curl -s -o /dev/null -w "%{http_code}" http://localhost:8003/sse

# Is Qdrant accessible?
curl http://localhost:6334/collections

# Are tests passing? (fast profile)
docker compose --profile test run --rm test-runner pytest tests/ -v --tb=short -q
```

## Related Documents

- [Error Catalog](../reference/error-catalog.md) — Tool-specific errors and resolutions
- [Docker Operations](docker-operations.md) — Build, test, debug commands
- [Multi-MCP Setup](multi-mcp-setup.md) — Cursor configuration and connection issues
- [Quick Reference](../reference/quick-reference.md) — All commands at a glance
