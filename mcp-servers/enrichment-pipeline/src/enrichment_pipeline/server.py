"""Enrichment Pipeline MCP server entry point (port 8004)."""

import logging
import os
import sys

from fastmcp import FastMCP

from .tools import (
    enrich_document,
    enrich_get_config,
    enrich_get_status,
    enrich_set_config,
)

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("enrichment_pipeline")

mcp = FastMCP("Enrichment Pipeline")

mcp.tool()(enrich_get_config)
mcp.tool()(enrich_set_config)
mcp.tool()(enrich_document)
mcp.tool()(enrich_get_status)


def main():
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8004"))
    logger.info("Starting Enrichment Pipeline MCP server on %s:%s", host, port)
    logger.info("Qdrant URL: %s", os.environ.get("QDRANT_URL", "http://qdrant-db:6334"))
    logger.info("Config path: %s", os.environ.get("ENRICHMENT_CONFIG_PATH", "/app/knowledge/enrichment-config.md"))
    mcp.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    main()
