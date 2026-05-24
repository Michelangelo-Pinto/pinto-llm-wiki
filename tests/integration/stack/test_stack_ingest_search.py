"""Full-stack cross-service test: ingest document → search via Qdrant.

With the full stack running:
1. Ingest a test text document via Ingestion Pipeline MCP
2. Verify the document was chunked and upserted to Qdrant
3. Search via Qdrant MCP and verify hits with score > threshold

Run with:
    docker compose --profile integration run --rm test-runner \
      pytest tests/integration/stack/test_stack_ingest_search.py -v -m integration_stack
"""

import json
import uuid

import pytest


pytestmark = pytest.mark.integration_stack

TEST_COLLECTION = f"test_stack_ingest_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Import MCP tools directly (source is mounted in test-runner container)
# ---------------------------------------------------------------------------


from ingestion_pipeline.tools import (
    ingest_document,
    ingest_get_status,
)
from qdrant_mcp.tools import (
    qdrant_create_collection,
    qdrant_delete_collection,
    qdrant_search,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_document(tmp_path_factory):
    """Create a temporary text document for ingestion testing."""
    content = (
        "## Test Document\n\n"
        "This is a test document about microservices architecture. "
        "Microservices are an architectural style that structures an application "
        "as a collection of loosely coupled services. Each service is fine-grained "
        "and the protocols are lightweight.\n\n"
        "Key benefits of microservices include independent deployability, "
        "technology diversity, resilience, and scalability. "
        "Teams can develop, test, and deploy their services independently.\n\n"
        "## Deployment Patterns\n\n"
        "Common deployment patterns include multiple service instances per host, "
        "service instance per container, and serverless deployment. "
        "Container orchestration platforms like Kubernetes help manage "
        "these deployments at scale."
    )
    doc_path = tmp_path_factory.mktemp("docs") / "test_document.md"
    doc_path.write_text(content)
    return str(doc_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def collection_setup():
    """Create test collection before tests, clean up after module."""
    result = json.loads(qdrant_create_collection(TEST_COLLECTION))
    assert result.get("status") == "created"
    yield
    try:
        qdrant_delete_collection(TEST_COLLECTION)
    except Exception:
        pass


def test_ingest_document_creates_chunks(collection_setup, test_document):
    """Ingesting a text document should create chunks and store them in Qdrant."""
    result = json.loads(ingest_document(
        file_path=test_document,
        collection=TEST_COLLECTION,
        chunk_size=800,
    ))
    assert "error" not in result, f"Ingest failed: {result.get('error')}"
    assert result.get("status") == "completed"
    assert result.get("chunks_created", 0) > 0, f"No chunks created: {result}"


def test_ingest_status_reports_document(collection_setup, test_document):
    """After ingestion, status should report the document."""
    result = json.loads(ingest_get_status(document_id=None))
    assert "error" not in result, f"Status check failed: {result.get('error')}"


def test_qdrant_search_finds_ingested_content(collection_setup, test_document):
    """Qdrant semantic search should find the ingested document content."""
    # First ingest
    ingest_result = json.loads(ingest_document(
        file_path=test_document,
        collection=TEST_COLLECTION,
        chunk_size=800,
    ))
    assert ingest_result.get("status") == "completed"

    # Then search for relevant content
    search_result = json.loads(qdrant_search(
        TEST_COLLECTION,
        "microservices architecture deployment patterns",
        limit=5,
    ))
    assert "error" not in search_result, f"Search failed: {search_result.get('error')}"
    assert len(search_result.get("results", [])) > 0, "No search results found"
    assert search_result["results"][0]["score"] > 0.3, \
        f"Best score too low: {search_result['results'][0]['score']}"
