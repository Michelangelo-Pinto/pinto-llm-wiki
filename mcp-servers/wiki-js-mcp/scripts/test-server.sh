#!/bin/bash

# Wiki.js MCP Server Test Script
# Run from repo root: ./mcp-servers/wiki-js-mcp/scripts/test-server.sh

set -e

echo "🚀 Testing Wiki.js MCP Server..."

MCP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MCP_ROOT"

if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found. Run ./mcp-servers/wiki-js-mcp/scripts/setup.sh first."
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "❌ Error: .env not found. Copy mcp-servers/wiki-js-mcp/config/example.env to mcp-servers/wiki-js-mcp/.env"
    exit 1
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

if [ ! -f "src/wiki_mcp_server/server.py" ]; then
    echo "❌ Error: Server package src/wiki_mcp_server/ not found."
    exit 1
fi

export PYTHONPATH="${MCP_ROOT}/src:${PYTHONPATH:-}"

echo "⚙️  Loading configuration..."
source .env

if [ -z "$WIKIJS_API_URL" ]; then
    echo "❌ Error: WIKIJS_API_URL not set in .env file"
    exit 1
fi

if [ -z "$WIKIJS_TOKEN" ] && [ -z "$WIKIJS_USERNAME" ]; then
    echo "❌ Error: Either WIKIJS_TOKEN or WIKIJS_USERNAME must be set in .env file"
    exit 1
fi

echo "✅ Configuration validated"

mkdir -p logs

echo ""
echo "📊 Server Configuration:"
echo "   API URL: $WIKIJS_API_URL"
echo "   Database: ${WIKIJS_MCP_DB:-./wikijs_mappings.db}"
echo "   Log Level: ${LOG_LEVEL:-INFO}"
echo "   Log File: ${LOG_FILE:-wikijs_mcp.log}"
echo ""

cleanup() {
    echo ""
    echo "🛑 Shutting down Wiki.js MCP Server..."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "🌟 Starting MCP server for testing..."
echo "   Press Ctrl+C to stop the server"
echo ""

if python -m wiki_mcp_server.server; then
    echo "✅ Server started successfully"
else
    echo "❌ Server failed to start. Check the logs for details:"
    echo "   Log file: ${LOG_FILE:-wikijs_mcp.log}"
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "   1. Verify Wiki.js is running and accessible"
    echo "   2. Check your API token is valid"
    echo "   3. Run ./mcp-servers/wiki-js-mcp/scripts/setup.sh"
    echo "   4. Check the log file for detailed error messages"
    exit 1
fi
