#!/bin/bash

# Wiki.js MCP Server Start Script
# Run from repo root: ./mcp-servers/wiki-js-mcp/scripts/start-server.sh

set -e

MCP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MCP_ROOT"

if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found. Run ./mcp-servers/wiki-js-mcp/scripts/setup.sh first." >&2
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "❌ Error: .env not found. Copy mcp-servers/wiki-js-mcp/config/example.env to mcp-servers/wiki-js-mcp/.env" >&2
    exit 1
fi

source venv/bin/activate

if [ ! -f "src/wiki_mcp_server/server.py" ]; then
    echo "❌ Error: Server package src/wiki_mcp_server/ not found." >&2
    exit 1
fi

source .env

if [ -z "$WIKIJS_API_URL" ]; then
    echo "❌ Error: WIKIJS_API_URL not set in .env file" >&2
    exit 1
fi

if [ -z "$WIKIJS_TOKEN" ] && [ -z "$WIKIJS_USERNAME" ]; then
    echo "❌ Error: Either WIKIJS_TOKEN or WIKIJS_USERNAME must be set in .env file" >&2
    exit 1
fi

mkdir -p logs

export PYTHONPATH="${MCP_ROOT}/src:${PYTHONPATH:-}"
exec python -m wiki_mcp_server.server
