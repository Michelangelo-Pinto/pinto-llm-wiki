"""Ingestion Pipeline MCP server entry point."""

import logging
import os
import sys

from fastmcp import FastMCP

from .tools import (
    ingest_delete_document,
    ingest_detect_type,
    ingest_document,
    ingest_directory,
    ingest_get_status,
    ingest_list_documents,
    ingest_search_chunks,
)

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("ingestion_pipeline")

mcp = FastMCP("Document Ingestion Pipeline")

mcp.tool()(ingest_detect_type)
mcp.tool()(ingest_document)
mcp.tool()(ingest_directory)
mcp.tool()(ingest_get_status)
mcp.tool()(ingest_delete_document)
mcp.tool()(ingest_search_chunks)
mcp.tool()(ingest_list_documents)


def main():
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8002"))
    logger.info("Starting Ingestion Pipeline MCP server on %s:%s", host, port)
    logger.info("Qdrant URL: %s", os.environ.get("QDRANT_URL", "http://qdrant-db:6334"))
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
