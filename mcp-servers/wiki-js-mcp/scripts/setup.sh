#!/bin/bash

# Wiki.js MCP Server Setup Script
# Run from repo root: ./mcp-servers/wiki-js-mcp/scripts/setup.sh

set -e

echo "🚀 Setting up Wiki.js MCP Server..."

MCP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MCP_ROOT"

echo "📋 Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python is not installed or not in PATH"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 12 ]; }; then
    echo "❌ Error: Python 3.12+ is required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"

if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    echo "✅ Virtual environment created"
else
    echo "📦 Virtual environment already exists"
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "⬆️  Upgrading pip..."
pip install --upgrade pip

echo "📚 Installing dependencies..."
if [ -f "pyproject.toml" ] && command -v poetry &> /dev/null; then
    echo "📖 Using Poetry for dependency management..."
    poetry install
elif [ -f "requirements.txt" ]; then
    echo "📖 Using pip for dependency management..."
    pip install -r requirements.txt
else
    echo "❌ Error: No pyproject.toml or requirements.txt found"
    exit 1
fi

if [ ! -f ".env" ] && [ -f "config/example.env" ]; then
    echo "⚙️  Creating .env file from example..."
    cp config/example.env .env
    echo "✅ .env file created. Please edit it with your Wiki.js credentials."
else
    echo "⚙️  .env file already exists"
fi

echo "📁 Creating necessary directories..."
mkdir -p logs

echo "🔐 Setting executable permissions..."
chmod +x scripts/setup.sh scripts/start-server.sh scripts/test-server.sh

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Edit mcp-servers/wiki-js-mcp/.env with your Wiki.js credentials"
echo "2. Test: ./mcp-servers/wiki-js-mcp/scripts/start-server.sh"
echo "3. Cursor MCP: see mcp-servers/wiki-js-mcp/config-mcp.json"
echo ""
echo "📖 For more information, see README.md"
