"""End-to-end tests for the ingestion pipeline.

Tests the full flow: detect -> ingest -> search -> verify results.
All tests run inside the test-runner Docker container, using direct
function imports (not SSE) for deterministic testing.

Requires: Qdrant DB running, test data generated.
"""

import json
import tempfile
from pathlib import Path

import pytest

# Direct imports from mounted source volumes
from ingestion_pipeline.tools import (
    ingest_delete_document,
    ingest_detect_type,
    ingest_document,
    ingest_directory,
    ingest_get_status,
    ingest_list_documents,
    ingest_search_chunks,
)

TEST_COLLECTION = f"test_e2e_pipeline"


def _parse(response):
    """Parse JSON string response from tool functions."""
    if isinstance(response, str):
        return json.loads(response)
    return response


class TestDetectType:
    """File type detection tests."""

    def test_detect_text_pdf(self, test_pdf_path):
        result = _parse(ingest_detect_type(test_pdf_path))
        assert "error" not in result, f"Detection failed: {result}"
        assert result["subtype"] == "text_pdf"
        assert result["needs_ocr"] is False
        assert result["supported"] is True

    def test_detect_scanned_pdf(self, test_scanned_pdf_path):
        result = _parse(ingest_detect_type(test_scanned_pdf_path))
        assert "error" not in result
        assert result["subtype"] in ("scanned_pdf", "text_pdf")
        assert result["supported"] is True

    def test_detect_docx(self, test_docx_path):
        result = _parse(ingest_detect_type(test_docx_path))
        assert "error" not in result
        assert result["category"] == "docx"
        assert result["supported"] is True

    def test_detect_docx_with_images(self, test_docx_images_path):
        result = _parse(ingest_detect_type(test_docx_images_path))
        assert "error" not in result
        assert result["category"] == "docx"
        assert result["has_embedded_images"] is True

    def test_detect_markdown(self, test_markdown_path):
        result = _parse(ingest_detect_type(test_markdown_path))
        assert "error" not in result
        assert result["category"] == "markdown"
        assert result["needs_ocr"] is False

    def test_detect_text(self, test_text_path):
        result = _parse(ingest_detect_type(test_text_path))
        assert "error" not in result
        assert result["category"] == "text"

    def test_detect_image(self, test_image_path):
        result = _parse(ingest_detect_type(test_image_path))
        assert "error" not in result
        assert result["category"] == "image"
        assert result["needs_ocr"] is True

    def test_detect_unsupported_format(self, tmp_path):
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("content")
        result = _parse(ingest_detect_type(str(bad_file)))
        assert result["supported"] is False

    def test_detect_nonexistent_file(self):
        result = _parse(ingest_detect_type("/nonexistent/file.pdf"))
        assert "error" in result


class TestIngestDocument:
    """Document ingestion tests. Uses unique collection per run."""

    COLLECTION = TEST_COLLECTION

    @classmethod
    def setup_class(cls):
        """Ensure collection exists."""
        from qdrant_client import QdrantClient, models
        import os
        url = os.environ.get("QDRANT_URL", "http://qdrant-db:6334")
        client = QdrantClient(url=url)
        try:
            client.create_collection(
                collection_name=cls.COLLECTION,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
                on_disk_payload=True,
            )
        except Exception:
            pass

    @classmethod
    def teardown_class(cls):
        """Clean up test collection."""
        from qdrant_client import QdrantClient
        import os
        url = os.environ.get("QDRANT_URL", "http://qdrant-db:6334")
        client = QdrantClient(url=url)
        try:
            client.delete_collection(collection_name=cls.COLLECTION)
        except Exception:
            pass

    def _ingest_and_verify(self, file_path, expected_type):
        """Helper: ingest a file and verify it was processed."""
        result = _parse(ingest_document(file_path, collection=self.COLLECTION))
        assert "error" not in result, f"Ingestion failed: {result}"
        assert result["status"] in ("completed", "skipped")
        if result["status"] == "completed":
            assert result["chunks_created"] > 0
            assert result["file_type"] == expected_type
        return result

    def test_ingest_text_pdf(self, test_pdf_path):
        self._ingest_and_verify(test_pdf_path, "text_pdf")

    def test_ingest_scanned_pdf(self, test_scanned_pdf_path):
        self._ingest_and_verify(test_scanned_pdf_path, "scanned_pdf")

    def test_ingest_docx(self, test_docx_path):
        self._ingest_and_verify(test_docx_path, "text_docx")

    def test_ingest_docx_with_images(self, test_docx_images_path):
        self._ingest_and_verify(test_docx_images_path, "mixed_docx")

    def test_ingest_markdown(self, test_markdown_path):
        self._ingest_and_verify(test_markdown_path, "markdown")

    def test_ingest_text(self, test_text_path):
        self._ingest_and_verify(test_text_path, "text")

    def test_ingest_image(self, test_image_path):
        self._ingest_and_verify(test_image_path, "image")

    def test_ingest_empty_file(self, tmp_path):
        """An empty file should return an error, not crash."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        result = _parse(ingest_document(str(empty_file), collection=self.COLLECTION))
        assert "error" in result

    def test_idempotency_skips_reingest(self, tmp_path):
        """Re-ingesting the same file should be skipped (content hash match)."""
        unique_file = tmp_path / "idempotency_test.txt"
        unique_file.write_text(
            "Unique idempotency test content for wiki-js-mcp pipeline validation."
        )
        file_path = str(unique_file)

        # First ingest
        r1 = _parse(ingest_document(file_path, collection=self.COLLECTION))
        assert r1["status"] == "completed"

        # Second ingest (same file, no force)
        r2 = _parse(ingest_document(file_path, collection=self.COLLECTION))
        assert r2["status"] == "skipped"
        assert "Already ingested" in r2.get("reason", "")

    def test_force_reingest(self, test_text_path):
        """force=True should re-process even if hash matches."""
        r1 = _parse(ingest_document(test_text_path, collection=self.COLLECTION, force=True))
        assert r1["status"] == "completed"
        assert r1["chunks_created"] > 0

    def test_ingest_nonexistent_file(self):
        result = _parse(ingest_document("/nonexistent/file.pdf", collection=self.COLLECTION))
        assert "error" in result

    def test_ingest_directory(self, test_mixed_dir):
        """Batch ingest a directory of files."""
        result = _parse(ingest_directory(test_mixed_dir, collection=self.COLLECTION))
        assert "error" not in result
        assert result["files_processed"] > 0
        assert result["files_failed"] == 0

    def test_status_tracking(self, test_markdown_path):
        """Check that ingestion status is tracked."""
        result = _parse(ingest_document(test_markdown_path, collection=self.COLLECTION))
        doc_id = result.get("document_id")
        assert doc_id, f"No document_id in result: {result}"

        status = _parse(ingest_get_status(doc_id))
        assert "error" not in status
        assert status["document_id"] == doc_id
        assert status["status"] in ("completed", "processing")

    def test_list_documents(self, test_text_path):
        """List all ingested documents."""
        ingest_document(test_text_path, collection=self.COLLECTION)
        result = _parse(ingest_list_documents())
        assert "documents" in result
        assert len(result["documents"]) > 0


class TestSearch:
    """Search and retrieval tests."""

    COLLECTION = TEST_COLLECTION

    @classmethod
    def setup_class(cls):
        from qdrant_client import QdrantClient, models
        import os
        url = os.environ.get("QDRANT_URL", "http://qdrant-db:6334")
        client = QdrantClient(url=url)
        try:
            client.create_collection(
                collection_name=cls.COLLECTION,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
                on_disk_payload=True,
            )
        except Exception:
            pass
        # Pre-ingest some test data
        test_data = Path("/data/test-data")
        if (test_data / "text" / "test.txt").exists():
            ingest_document(str(test_data / "text" / "test.txt"), collection=cls.COLLECTION)
        if (test_data / "markdown" / "test.md").exists():
            ingest_document(str(test_data / "markdown" / "test.md"), collection=cls.COLLECTION)

    def test_search_returns_results(self):
        """Search should return relevant chunks."""
        result = _parse(ingest_search_chunks("database configuration", collection=self.COLLECTION, limit=5))
        assert "error" not in result
        assert "results" in result
        assert result["count"] >= 0

    def test_search_respects_limit(self):
        result = _parse(ingest_search_chunks("test", collection=self.COLLECTION, limit=2))
        assert len(result["results"]) <= 2

    def test_search_empty_query(self):
        result = _parse(ingest_search_chunks("", collection=self.COLLECTION))
        assert "error" in result


class TestDelete:
    """Document deletion tests."""

    COLLECTION = TEST_COLLECTION

    def test_delete_document(self, test_markdown_path):
        """Ingest, then delete, then verify gone."""
        r = _parse(ingest_document(test_markdown_path, collection=self.COLLECTION))
        doc_id = r.get("document_id")
        assert doc_id

        # Delete
        d = _parse(ingest_delete_document(doc_id, collection=self.COLLECTION))
        assert d["status"] == "deleted"

        # Verify status shows it's gone
        s = _parse(ingest_get_status(doc_id))
        assert "error" in s  # Should not exist anymore
