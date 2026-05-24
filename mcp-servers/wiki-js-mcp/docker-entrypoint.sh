#!/bin/sh
set -e

: "${WIKIJS_API_URL:=http://wiki:3000}"
: "${WIKIJS_MCP_DB:=/data/wikijs_mappings.db}"
: "${LOG_FILE:=/logs/wikijs_mcp.log}"
: "${LOG_LEVEL:=INFO}"
: "${MCP_HOST:=0.0.0.0}"
: "${MCP_PORT:=8000}"
: "${MCP_TRANSPORT:=sse}"

mkdir -p "$(dirname "$WIKIJS_MCP_DB")" "$(dirname "$LOG_FILE")"

exec "$@"
