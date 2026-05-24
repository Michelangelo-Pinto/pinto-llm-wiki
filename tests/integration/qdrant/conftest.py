"""Fixtures for Qdrant MCP integration tests.

These tests import Qdrant MCP tool functions directly (not via SSE)
for determinism and speed. They require qdrant-db to be running.

Run with:
    docker compose --profile test run --rm test-runner pytest tests/integration/qdrant/ -v -m integration
"""

import json

import pytest

from qdrant_mcp.tools import (
    qdrant_create_collection,
    qdrant_delete_collection,
)

TEST_COLLECTION = "test_qdrant_mcp_integration"


@pytest.fixture(autouse=True)
def clean_collection():
    """Ensure a clean test collection for each test function."""
    try:
        qdrant_delete_collection(TEST_COLLECTION)
    except Exception:
        pass
    result = json.loads(qdrant_create_collection(TEST_COLLECTION))
    assert result.get("status") == "created"
    yield
    try:
        qdrant_delete_collection(TEST_COLLECTION)
    except Exception:
        pass
