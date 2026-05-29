"""Tesseract OCR MCP server entry point.

Registers OCR tools via FastMCP and starts the SSE server.
The server wraps Tesseract OCR as MCP tools for LLM agent use.

Environment:
    TESSDATA_PREFIX: Path to Tesseract language data
    MCP_HOST: Listen address (default: 0.0.0.0)
    MCP_PORT: Listen port (default: 8003)
"""

import logging
import os
import sys

from fastmcp import FastMCP

from .tools import (
    ocr_detect_document_type,
    ocr_extract_hocr,
    ocr_extract_text,
    ocr_get_confidence,
    ocr_get_languages,
    ocr_preprocess_and_extract,
    ocr_process_document,
)

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("tesseract_mcp")

mcp = FastMCP("Tesseract OCR Service")

# Register tools
mcp.tool()(ocr_extract_text)
mcp.tool()(ocr_detect_document_type)
mcp.tool()(ocr_extract_hocr)
mcp.tool()(ocr_get_confidence)
mcp.tool()(ocr_get_languages)
mcp.tool()(ocr_process_document)
mcp.tool()(ocr_preprocess_and_extract)


def main():
    import pytesseract
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8003"))
    logger.info("Starting Tesseract OCR MCP server on %s:%s", host, port)
    logger.info("Available languages: %s", pytesseract.get_languages())
    logger.info("Registered tools: extract_text, detect_document_type, extract_hocr, "
                "get_confidence, get_languages, process_document, preprocess_and_extract")
    mcp.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    import pytesseract
    main()
