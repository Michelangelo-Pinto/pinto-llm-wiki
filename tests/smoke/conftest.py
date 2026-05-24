"""Shared fixtures for SSE smoke tests.

Provides an MCP SSE client helper and server URL fixtures for each
of the 4 MCP servers. Smoke tests validate that tools are discoverable
and callable via the real SSE transport (not direct Python imports).
"""

import json
import os
import time

import httpx
import pytest


# ---------------------------------------------------------------------------
# MCP SSE Client — implements the MCP JSON-RPC 2.0 protocol over SSE
# ---------------------------------------------------------------------------


class McpSseClient:
    """Minimal MCP client for smoke testing FastMCP SSE servers.

    Connects to a FastMCP server's SSE endpoint and provides:
    - list_tools() — discover all registered tools
    - call_tool(name, arguments) — invoke a tool via JSON-RPC
    - close() — clean up the connection
    """

    def __init__(self, base_url: str, timeout: float = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._message_endpoint = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def connect(self) -> None:
        """Establish the SSE connection and discover the message endpoint."""
        resp = self._client.get(
            f"{self.base_url}/sse",
            headers={"Accept": "text/event-stream"},
        )
        resp.raise_for_status()
        # FastMCP's sse-starlette sends an 'endpoint' event with the POST URL
        for line in resp.text.splitlines():
            if line.startswith("event: endpoint"):
                continue
            if line.startswith("data: "):
                endpoint_path = line[6:].strip()
                # The endpoint path may be relative (e.g., "/messages?session_id=abc")
                if endpoint_path.startswith("/"):
                    # Extract the base (scheme + host) from base_url
                    from urllib.parse import urlparse
                    parsed = urlparse(self.base_url)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    self._message_endpoint = base + endpoint_path
                else:
                    self._message_endpoint = f"{self.base_url}/{endpoint_path}"
                break

        # Fallback: some FastMCP versions also accept POST directly to /sse
        if not self._message_endpoint:
            self._message_endpoint = f"{self.base_url}/sse"

    def _send(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and return the parsed response."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._next_id(),
        }
        resp = self._client.post(
            self._message_endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        try:
            return resp.json()
        except Exception:
            return {"error": f"Invalid JSON response: {resp.text[:200]}"}

    def list_tools(self) -> list[dict]:
        """Return the list of tools from tools/list."""
        result = self._send("tools/list")
        if "error" in result:
            raise RuntimeError(f"tools/list failed: {result['error']}")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """Invoke a tool and return the parsed result."""
        result = self._send("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        return result

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


# ---------------------------------------------------------------------------
# Server URL fixtures — read from environment with sensible defaults
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qdrant_mcp_url() -> str:
    return os.environ.get("QDRANT_MCP_URL", "http://qdrant-mcp:8001")


@pytest.fixture(scope="session")
def ingestion_mcp_url() -> str:
    return os.environ.get("INGESTION_MCP_URL", "http://ingestion-pipeline:8002")


@pytest.fixture(scope="session")
def tesseract_mcp_url() -> str:
    return os.environ.get("TESSERACT_MCP_URL", "http://tesseract-mcp:8003")


@pytest.fixture(scope="session")
def wikijs_mcp_url() -> str:
    return os.environ.get("WIKIJS_MCP_URL", "http://wiki-js-mcp:8000")


# ---------------------------------------------------------------------------
# Client fixtures — one per server
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qdrant_client(qdrant_mcp_url):
    """MCP SSE client connected to Qdrant MCP."""
    client = McpSseClient(qdrant_mcp_url)
    client.connect()
    yield client
    client.close()


@pytest.fixture(scope="module")
def ingestion_client(ingestion_mcp_url):
    """MCP SSE client connected to Ingestion Pipeline."""
    client = McpSseClient(ingestion_mcp_url)
    client.connect()
    yield client
    client.close()


@pytest.fixture(scope="module")
def tesseract_client(tesseract_mcp_url):
    """MCP SSE client connected to Tesseract MCP."""
    client = McpSseClient(tesseract_mcp_url)
    client.connect()
    yield client
    client.close()


@pytest.fixture(scope="module")
def wikijs_client(wikijs_mcp_url):
    """MCP SSE client connected to Wiki.js MCP."""
    # Wiki.js MCP needs the full stack — may fail if Wiki.js is not set up
    client = McpSseClient(wikijs_mcp_url, timeout=10)
    try:
        client.connect()
    except Exception:
        pytest.skip("Wiki.js MCP SSE endpoint not reachable (full stack required)")
    yield client
    client.close()
