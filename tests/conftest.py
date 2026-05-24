"""Shared fixtures for all test suites.

Fixtures operate inside the test-runner container, which mounts:
  - /app/qdrant_mcp     (qdrant-mcp source, for direct import)
  - /app/ingestion_pipeline (ingestion source, for direct import)
  - /app/tests           (all test modules)
  - /data/test-data      (test fixtures)
"""

import os

import pytest
from qdrant_client import QdrantClient


@pytest.fixture(scope="session")
def qdrant_url():
    """Qdrant REST endpoint URL from environment."""
    return os.environ.get("QDRANT_URL", "http://qdrant-db:6334")


@pytest.fixture(scope="session")
def qdrant_client(qdrant_url):
    """Session-scoped QdrantClient connected to the running Qdrant instance."""
    return QdrantClient(url=qdrant_url)
