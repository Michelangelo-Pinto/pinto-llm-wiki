#!/usr/bin/env python3
"""Backward-compatible entry point; use `python -m wiki_mcp_server.server` in Docker."""

from wiki_mcp_server.server import main

if __name__ == "__main__":
    main()
