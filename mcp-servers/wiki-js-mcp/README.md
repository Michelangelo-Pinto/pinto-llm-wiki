# Wiki.js MCP Server

Python MCP server for Wiki.js (SSE/stdio). All MCP-related code, config, and Docker build live in this directory.

## Quick start (local)

```bash
cp config/example.env .env
# edit .env with WIKIJS_API_URL and WIKIJS_TOKEN

./scripts/setup.sh
./scripts/start-server.sh
```

## Docker

Built from repo root:

```bash
cd ..
cp .env.example .env
docker compose up -d --build
```

## Cursor MCP

See [config-mcp.json](config-mcp.json). Full documentation: [../README.md](../README.md).

## Docs

- [Documentation v2](../doc_v2/index.md) — complete technical reference
- [Architecture](../doc_v2/architecture/index.md) — system design and module map
