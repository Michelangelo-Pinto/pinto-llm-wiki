"""FastMCP server instance and SSE entrypoint."""

import asyncio

from fastmcp import FastMCP

from wiki_mcp_server.client import wikijs
from wiki_mcp_server.config import logger, settings

mcp = FastMCP("Wiki.js Integration")


def _register_tools() -> None:
    """Import tool modules so @mcp.tool decorators run."""
    from wiki_mcp_server import (  # noqa: F401
        tools_deletion,
        tools_files,
        tools_graph,
        tools_hierarchy,
        tools_pages,
        tools_system,
    )


def main() -> None:
    """Main entry point for the MCP server."""
    _register_tools()

    async def on_startup() -> None:
        await wikijs.authenticate()
        logger.info(
            "Wiki.js MCP Server starting (transport=%s, host=%s, port=%s)",
            settings.MCP_TRANSPORT,
            settings.MCP_HOST,
            settings.MCP_PORT,
        )

    asyncio.run(on_startup())

    if settings.MCP_TRANSPORT.lower() == "sse":
        mcp.run(
            transport="sse",
            host=settings.MCP_HOST,
            port=settings.MCP_PORT,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
