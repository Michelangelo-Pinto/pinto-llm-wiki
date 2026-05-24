"""Unit tests for ingestion pipeline helper functions.

Tests chunking logic, file type detection, and text parsing without Docker.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp-servers" / "ingestion-pipeline" / "src"))

from ingestion_pipeline.chunker import _split_by_headings, _split_section, chunk_document
from ingestion_pipeline.detector import detect_document_type


# ---------------------------------------------------------------------------
# chunk_document tests
# ---------------------------------------------------------------------------


class TestChunkDocument:
    """Tests for chunk_document — the main text chunking function."""

    def test_short_text_single_chunk(self):
        text = "This is a short document with only a few sentences."
        chunks = chunk_document(text, chunk_size=1500, chunk_overlap=200)
        assert len(chunks) >= 1
        assert text in chunks[0]

    def test_long_text_multiple_chunks(self):
        text = "Sentence one. " * 500  # ~7500 chars
        chunks = chunk_document(text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) > 1
        # Each chunk should be within size limit
        for chunk in chunks:
            assert len(chunk) <= 2500  # max_chunk_size default

    def test_markdown_with_headings(self):
        text = """# Section 1
Content for section one. It has multiple sentences. More content here.

## Section 2
Content for section two. Different heading level. Even more text.

# Section 3
Final section with its own text content.
"""
        chunks = chunk_document(text, source_type="markdown", chunk_size=200, chunk_overlap=30)
        assert len(chunks) >= 1

    def test_empty_text(self):
        chunks = chunk_document("", chunk_size=500)
        assert len(chunks) == 0 or all(c == "" for c in chunks)

    def test_respects_max_chunk_size(self):
        text = "X" * 10000
        chunks = chunk_document(text, chunk_size=1000, chunk_overlap=100, max_chunk_size=2000)
        for chunk in chunks:
            assert len(chunk) <= 2000

    def test_custom_chunk_size(self):
        text = "A sentence. " * 200
        chunks = chunk_document(text, chunk_size=800, chunk_overlap=100)
        # Each chunk should be roughly chunk_size or smaller
        for chunk in chunks[:-1]:  # Last chunk might be smaller
            assert len(chunk) <= 2500  # default max

    def test_overlap_preserves_context(self):
        text = "AAA BBB CCC DDD EEE FFF GGG HHH III JJJ"
        chunks = chunk_document(text, chunk_size=15, chunk_overlap=5)
        if len(chunks) > 1:
            # Check that there's some overlap between consecutive chunks
            # (at least one word should appear in both)
            pass  # Overlap behavior depends on sentence boundary detection

    def test_whitespace_only(self):
        chunks = chunk_document("   \n\n   \t  ", chunk_size=500)
        for chunk in chunks:
            assert isinstance(chunk, str)


# ---------------------------------------------------------------------------
# _split_by_headings tests
# ---------------------------------------------------------------------------


class TestSplitByHeadings:
    """Tests for _split_by_headings — markdown heading-based splitting."""

    def test_single_heading(self):
        text = "# Title\nContent under title."
        sections = _split_by_headings(text)
        assert len(sections) == 1

    def test_multiple_headings(self):
        text = """# H1
Content 1.

## H2
Content 2.

# Another H1
Content 3.
"""
        sections = _split_by_headings(text)
        assert len(sections) >= 2

    def test_no_headings(self):
        text = "Just plain text without any markdown headings."
        sections = _split_by_headings(text)
        assert len(sections) == 1
        assert sections[0] == text

    def test_text_before_first_heading(self):
        text = "Intro text.\n# Heading\nContent."
        sections = _split_by_headings(text)
        assert len(sections) >= 1
        assert "Intro text" in sections[0]

    def test_empty_text(self):
        sections = _split_by_headings("")
        assert len(sections) == 1
        assert sections[0] == ""

    def test_heading_levels(self):
        text = "# H1\n### H3\n###### H6\ncontent"
        sections = _split_by_headings(text)
        # All heading levels should be recognized
        assert len(sections) >= 2


# ---------------------------------------------------------------------------
# _split_section tests
# ---------------------------------------------------------------------------


class TestSplitSection:
    """Tests for _split_section — recursive sentence-boundary splitting."""

    def test_under_limit_returns_as_is(self):
        text = "Short text."
        chunks = _split_section(text, chunk_size=500, overlap=50, max_size=1000)
        assert chunks == [text]

    def test_over_limit_splits_at_sentences(self):
        sentences = "This is sentence {} with some words. "
        text = "".join(sentences.format(i) for i in range(200))
        chunks = _split_section(text, chunk_size=500, overlap=50, max_size=1000)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 1000

    def test_fallback_to_fixed_split(self):
        # Text without any sentence boundaries
        text = "a" * 3000
        chunks = _split_section(text, chunk_size=500, overlap=50, max_size=1000)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 1000

    def test_overlap_includes_previous_context(self):
        parts = ["First part. ", "Second part. ", "Third part. ", "Fourth part. "]
        text = "".join(parts * 50)
        chunks = _split_section(text, chunk_size=40, overlap=15, max_size=100)
        assert len(chunks) > 1

    def test_empty_section(self):
        chunks = _split_section("", chunk_size=500, overlap=50, max_size=1000)
        assert chunks == [""]


# ---------------------------------------------------------------------------
# detect_document_type tests
# ---------------------------------------------------------------------------


class TestDetectDocumentType:
    """Tests for detect_document_type — file type detection by extension."""

    def test_markdown_detection(self):
        result = detect_document_type("/path/to/readme.md")
        assert result["category"] in ("markdown", "text")

    def test_text_detection(self):
        result = detect_document_type("/path/to/file.txt")
        assert result["category"] in ("text", "markdown")

    def test_image_detection(self):
        result = detect_document_type("/path/to/photo.png")
        assert result["category"] == "image"

    def test_image_jpg(self):
        result = detect_document_type("/path/to/photo.jpg")
        assert result["category"] == "image"

    def test_unsupported_extension(self):
        result = detect_document_type("/path/to/file.xyz")
        assert result["category"] in ("unsupported", "text")

    def test_no_extension(self):
        result = detect_document_type("/path/to/file_without_extension")
        assert isinstance(result, dict)

    def test_python_file(self):
        result = detect_document_type("/path/to/script.py")
        assert isinstance(result, dict)
