"""Qdrant MCP server entry point.

Registers all Qdrant tools via FastMCP and starts the SSE server.
The server wraps the Qdrant REST API as MCP tools for LLM agent use.

Usage:
    python -m qdrant_mcp.server

Environment:
    QDRANT_URL: Qdrant REST endpoint (default: http://qdrant-db:6334)
    MCP_HOST: Listen address (default: 0.0.0.0)
    MCP_PORT: Listen port (default: 8001)
"""

import json
import logging
import os
import sys

from fastmcp import FastMCP

from .tools import (
    qdrant_collection_info,
    qdrant_create_collection,
    qdrant_delete_by_filter,
    qdrant_delete_collection,
    qdrant_list_collections,
    qdrant_scroll,
    qdrant_search,
    qdrant_upsert_chunks,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("qdrant_mcp")

# Create FastMCP instance
mcp = FastMCP("Qdrant Vector Database")


# Register all tools by calling the tool decorator on imported functions
mcp.tool()(qdrant_create_collection)
mcp.tool()(qdrant_list_collections)
mcp.tool()(qdrant_collection_info)
mcp.tool()(qdrant_delete_collection)
mcp.tool()(qdrant_search)
mcp.tool()(qdrant_upsert_chunks)
mcp.tool()(qdrant_delete_by_filter)
mcp.tool()(qdrant_scroll)


def main():
    """Start the Qdrant MCP server with SSE transport."""
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8001"))

    logger.info("Starting Qdrant MCP server on %s:%s", host, port)
    logger.info("Qdrant URL: %s", os.environ.get("QDRANT_URL", "http://qdrant-db:6334"))
    logger.info("Registered tools: create_collection, list_collections, collection_info, "
                "delete_collection, search, upsert_chunks, delete_by_filter, scroll")

    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
