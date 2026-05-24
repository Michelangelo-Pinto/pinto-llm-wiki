"""Unit tests for Qdrant MCP helper functions.

Tests pure functions that don't require a running Qdrant instance.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp-servers" / "qdrant-mcp" / "src"))

from qdrant_mcp.tools import _build_filter


# ---------------------------------------------------------------------------
# _build_filter tests
# ---------------------------------------------------------------------------


class TestBuildFilter:
    """Tests for _build_filter — Qdrant filter construction."""

    def test_simple_match_filter(self):
        filter_dict = {
            "must": [{"key": "document_id", "match": {"value": "doc-123"}}]
        }
        result = _build_filter(filter_dict)
        assert result is not None
        # Qdrant models.Filter has a 'must' attribute
        assert hasattr(result, "must")
        assert result.must is not None

    def test_multiple_must_conditions(self):
        filter_dict = {
            "must": [
                {"key": "type", "match": {"value": "pdf"}},
                {"key": "status", "match": {"value": "completed"}},
            ]
        }
        result = _build_filter(filter_dict)
        assert hasattr(result, "must")
        assert result.must is not None

    def test_range_filter(self):
        filter_dict = {
            "must": [{"key": "score", "range": {"gte": 0.5, "lte": 1.0}}]
        }
        result = _build_filter(filter_dict)
        assert result is not None
        assert hasattr(result, "must")

    def test_empty_filter(self):
        result = _build_filter({})
        assert result is not None

    def test_none_filter(self):
        result = _build_filter(None)
        assert result is not None

    def test_should_condition(self):
        filter_dict = {
            "should": [
                {"key": "tag", "match": {"value": "python"}},
                {"key": "tag", "match": {"value": "javascript"}},
            ]
        }
        result = _build_filter(filter_dict)
        assert result is not None

    def test_must_not_condition(self):
        filter_dict = {
            "must_not": [{"key": "archived", "match": {"value": True}}]
        }
        result = _build_filter(filter_dict)
        assert result is not None

    def test_combined_conditions(self):
        filter_dict = {
            "must": [{"key": "type", "match": {"value": "document"}}],
            "must_not": [{"key": "deleted", "match": {"value": True}}],
            "should": [{"key": "priority", "match": {"value": "high"}}],
        }
        result = _build_filter(filter_dict)
        assert result is not None


# ---------------------------------------------------------------------------
# compute_embedding tests (with mocked model)
# ---------------------------------------------------------------------------


class TestComputeEmbedding:
    """Tests for compute_embedding — embedding computation with mocked model."""

    def test_embedding_dimensions(self):
        from qdrant_mcp.embedder import compute_embedding

        with patch("qdrant_mcp.embedder.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.encode.return_value = [0.1] * 384
            mock_get_model.return_value = mock_model

            result = compute_embedding("test text")
            assert len(result) == 384
            mock_model.encode.assert_called_once_with("test text")

    def test_embedding_is_normalized(self):
        from qdrant_mcp.embedder import compute_embedding
        import math

        with patch("qdrant_mcp.embedder.get_model") as mock_get_model:
            mock_model = MagicMock()
            # Return a non-unit vector
            mock_model.encode.return_value = [3.0] * 384
            mock_get_model.return_value = mock_model

            result = compute_embedding("test")
            # The result should be a list of floats
            assert all(isinstance(v, float) for v in result)

    @patch("qdrant_mcp.embedder.get_model")
    def test_empty_string_embedding(self, mock_get_model):
        from qdrant_mcp.embedder import compute_embedding

        mock_model = MagicMock()
        mock_model.encode.return_value = [0.0] * 384
        mock_get_model.return_value = mock_model

        result = compute_embedding("")
        assert len(result) == 384
        mock_model.encode.assert_called_once()


class TestComputeEmbeddings:
    """Tests for compute_embeddings — batch embedding."""

    @patch("qdrant_mcp.embedder.get_model")
    def test_batch_embedding(self, mock_get_model):
        from qdrant_mcp.embedder import compute_embeddings

        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1] * 384 for _ in range(3)]
        mock_get_model.return_value = mock_model

        texts = ["text one", "text two", "text three"]
        results = compute_embeddings(texts)
        assert len(results) == 3
        for r in results:
            assert len(r) == 384

    @patch("qdrant_mcp.embedder.get_model")
    def test_single_text_batch(self, mock_get_model):
        from qdrant_mcp.embedder import compute_embeddings

        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1] * 384]
        mock_get_model.return_value = mock_model

        results = compute_embeddings(["solo"])
        assert len(results) == 1
        assert len(results[0]) == 384

    @patch("qdrant_mcp.embedder.get_model")
    def test_empty_list(self, mock_get_model):
        from qdrant_mcp.embedder import compute_embeddings

        mock_model = MagicMock()
        mock_model.encode.return_value = []
        mock_get_model.return_value = mock_model

        results = compute_embeddings([])
        assert results == []
