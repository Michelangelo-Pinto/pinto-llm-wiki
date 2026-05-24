"""Fixtures for E2E tests.

All fixtures operate against the running Docker stack.
Tests import MCP tool functions directly (not via SSE) since the
test-runner container has volumes mounted to source code.
"""

import json
import os
import uuid
from pathlib import Path

import pytest

# Test collection name - unique per run to avoid collisions
TEST_COLLECTION = f"test_e2e_{uuid.uuid4().hex[:8]}"

# Test data paths (mounted at /data/test-data in container)
TEST_DATA_DIR = Path("/data/test-data")


@pytest.fixture(scope="session")
def test_collection():
    """Unique collection name for this test session."""
    return TEST_COLLECTION


@pytest.fixture(scope="session")
def qdrant_url():
    """Qdrant REST endpoint URL."""
    return os.environ.get("QDRANT_URL", "http://qdrant-db:6334")


@pytest.fixture(scope="session")
def qdrant_client(qdrant_url):
    """QdrantClient connected to the running Qdrant instance."""
    from qdrant_client import QdrantClient
    return QdrantClient(url=qdrant_url)


@pytest.fixture(scope="session", autouse=True)
def setup_test_collection(qdrant_client, test_collection):
    """Create test collection before tests, clean up after."""
    from qdrant_client import models

    # Create collection
    qdrant_client.create_collection(
        collection_name=test_collection,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        on_disk_payload=True,
    )
    yield
    # Cleanup
    try:
        qdrant_client.delete_collection(collection_name=test_collection)
    except Exception:
        pass


@pytest.fixture
def test_pdf_path():
    """Path to the text-based test PDF."""
    p = TEST_DATA_DIR / "pdf" / "test_text.pdf"
    if not p.exists():
        pytest.skip(f"Test data not found: {p}")
    return str(p)


@pytest.fixture
def test_scanned_pdf_path():
    """Path to the scanned-like test PDF."""
    p = TEST_DATA_DIR / "pdf" / "test_scanned.pdf"
    if not p.exists():
        pytest.skip(f"Test data not found: {p}")
    return str(p)


@pytest.fixture
def test_docx_path():
    """Path to the text-only test DOCX."""
    p = TEST_DATA_DIR / "docx" / "test_text.docx"
    if not p.exists():
        pytest.skip(f"Test data not found: {p}")
    return str(p)


@pytest.fixture
def test_docx_images_path():
    """Path to the DOCX with embedded images."""
    p = TEST_DATA_DIR / "docx" / "test_with_images.docx"
    if not p.exists():
        pytest.skip(f"Test data not found: {p}")
    return str(p)


@pytest.fixture
def test_markdown_path():
    """Path to the test markdown file."""
    p = TEST_DATA_DIR / "markdown" / "test.md"
    if not p.exists():
        pytest.skip(f"Test data not found: {p}")
    return str(p)


@pytest.fixture
def test_text_path():
    """Path to the test plain text file."""
    p = TEST_DATA_DIR / "text" / "test.txt"
    if not p.exists():
        pytest.skip(f"Test data not found: {p}")
    return str(p)


@pytest.fixture
def test_image_path():
    """Path to the test image with text."""
    p = TEST_DATA_DIR / "images" / "test_scan.png"
    if not p.exists():
        pytest.skip(f"Test data not found: {p}")
    return str(p)


@pytest.fixture
def test_mixed_dir():
    """Path to the mixed test directory for batch tests."""
    p = TEST_DATA_DIR / "mixed"
    if not p.exists():
        pytest.skip(f"Test data not found: {p}")
    return str(p)
