"""Full-stack health and connectivity tests.

Verifies that all containers in the "integration" profile are reachable.

Run with:
    docker compose --profile integration run --rm test-runner \
      pytest tests/integration/stack/test_stack_health.py -v -m integration_stack
"""

import socket

import httpx
import pytest


pytestmark = pytest.mark.integration_stack


# ---------------------------------------------------------------------------
# TCP connectivity
# ---------------------------------------------------------------------------


SERVICES = [
    ("qdrant-db", "qdrant-db", 6334, "Qdrant REST API"),
    ("qdrant-mcp", "qdrant-mcp", 8001, "Qdrant MCP server"),
    ("ingestion-pipeline", "ingestion-pipeline", 8002, "Ingestion Pipeline MCP"),
    ("tesseract-mcp", "tesseract-mcp", 8003, "Tesseract MCP server"),
    ("wiki-js-mcp", "wiki-js-mcp", 8000, "Wiki.js MCP server"),
    ("wiki", "wiki", 3000, "Wiki.js application"),
]


@pytest.mark.parametrize("name,host,port,description", SERVICES)
def test_service_tcp_reachable(name, host, port, description):
    """Each stack service should accept TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=5):
            assert True, f"{description} ({name}:{port}) is reachable"
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        pytest.fail(f"{description} ({name}:{port}) not reachable: {e}")


# ---------------------------------------------------------------------------
# SSE health
# ---------------------------------------------------------------------------


MCP_SSE_ENDPOINTS = [
    ("qdrant-mcp", "http://qdrant-mcp:8001/sse"),
    ("ingestion-pipeline", "http://ingestion-pipeline:8002/sse"),
    ("tesseract-mcp", "http://tesseract-mcp:8003/sse"),
    ("wiki-js-mcp", "http://wiki-js-mcp:8000/sse"),
]


@pytest.mark.parametrize("name,url", MCP_SSE_ENDPOINTS)
def test_mcp_sse_endpoint_responds(name, url):
    """Each MCP server's /sse endpoint should respond (may not complete but should connect)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            # We expect the SSE stream to start; a timeout is acceptable
            # as SSE is a long-lived connection.
            try:
                response = client.get(url, follow_redirects=True)
                # 200 or timeout during streaming are both acceptable
                assert response.status_code in (200, 302)
            except httpx.ReadTimeout:
                # SSE streams don't terminate; timeout is expected
                pass
    except httpx.ConnectError as e:
        pytest.fail(f"{name} SSE endpoint not reachable: {e}")
