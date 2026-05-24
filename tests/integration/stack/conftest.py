"""Fixtures for full-stack integration tests.

These tests require the complete Docker stack to be running:
  - Wiki.js (port 3000)
  - Qdrant DB (port 6334 REST)
  - Wiki.js MCP (port 8000)
  - Qdrant MCP (port 8001)
  - Ingestion Pipeline MCP (port 8002)
  - Tesseract MCP (port 8003)

Environment variables are set in docker-compose when using profile "integration".

Run with:
    docker compose --profile integration run --rm test-runner \
      pytest tests/integration/stack/ -v -m integration_stack
"""

import os
import socket
import time

import pytest


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _tcp_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is open on the given host."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _wait_for_port(host: str, port: int, max_wait: float = 30.0) -> None:
    """Wait for a TCP port to become available."""
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if _tcp_port_open(host, port):
            return
        time.sleep(1)
    raise TimeoutError(f"Port {host}:{port} not reachable after {max_wait}s")


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def stack_env():
    """Read all stack service URLs from environment."""
    return {
        "qdrant_url": os.environ.get("QDRANT_URL", "http://qdrant-db:6334"),
        "qdrant_mcp_url": os.environ.get("QDRANT_MCP_URL", "http://qdrant-mcp:8001"),
        "ingestion_mcp_url": os.environ.get("INGESTION_MCP_URL", "http://ingestion-pipeline:8002"),
        "tesseract_mcp_url": os.environ.get("TESSERACT_MCP_URL", "http://tesseract-mcp:8003"),
        "wikijs_mcp_url": os.environ.get("WIKIJS_MCP_URL", "http://wiki-js-mcp:8000"),
        "wikijs_api_url": os.environ.get("WIKIJS_API_URL", "http://wiki:3000"),
    }


@pytest.fixture(scope="session", autouse=True)
def verify_stack_health(stack_env):
    """Verify all stack services are reachable before running tests."""
    services = [
        ("qdrant-db", "qdrant-db", 6334),
        ("qdrant-mcp", "qdrant-mcp", 8001),
        ("ingestion-pipeline", "ingestion-pipeline", 8002),
        ("tesseract-mcp", "tesseract-mcp", 8003),
        ("wiki-js-mcp", "wiki-js-mcp", 8000),
        ("wiki", "wiki", 3000),
    ]
    for name, host, port in services:
        _wait_for_port(host, port)
