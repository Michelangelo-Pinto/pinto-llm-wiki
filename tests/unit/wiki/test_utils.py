"""Unit tests for wiki-js-mcp helper functions.

Tests pure functions that don't require Docker, Wiki.js, or any external service.
"""

import json
import tempfile
from pathlib import Path

import pytest

# Import testable helpers from the wiki-js-mcp server
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp-servers" / "wiki-js-mcp" / "src"))

from wiki_mcp_server.tools_pages import _extract_links
from wiki_mcp_server.tools_graph import _extract_external_links
from wiki_mcp_server.utils import extract_code_structure, get_file_hash, markdown_to_html


# ---------------------------------------------------------------------------
# _extract_links tests
# ---------------------------------------------------------------------------


class TestExtractLinks:
    """Tests for _extract_links — markdown link extraction."""

    def test_simple_link(self):
        links = _extract_links("[Hello](hello-world)")
        assert len(links) == 1
        assert links[0]["link_text"] == "Hello"
        assert links[0]["target_path"] == "hello-world"
        assert links[0]["position"] == 0

    def test_multiple_links(self):
        content = "[Page 1](page-1)\n[Page 2](page-2)\n[Page 3](page-3)"
        links = _extract_links(content)
        assert len(links) == 3
        assert links[0]["target_path"] == "page-1"
        assert links[1]["target_path"] == "page-2"
        assert links[2]["target_path"] == "page-3"

    def test_ignores_image_links(self):
        links = _extract_links("![Image](image.png)")
        assert len(links) == 0

    def test_ignores_external_urls(self):
        links = _extract_links("[Google](https://google.com)")
        assert len(links) == 0

    def test_ignores_anchor_links(self):
        links = _extract_links("[Section](#section-1)")
        assert len(links) == 0

    def test_mixed_content(self):
        content = """
# Title
Some text with [a link](target) and ![an image](img.png).
Also [external](https://example.com) and [another](other).
"""
        links = _extract_links(content)
        assert len(links) == 2
        targets = {l["target_path"] for l in links}
        assert targets == {"target", "other"}

    def test_empty_content(self):
        links = _extract_links("")
        assert len(links) == 0

    def test_no_links(self):
        links = _extract_links("Just plain text without any links.")
        assert len(links) == 0

    def test_link_with_spaces(self):
        links = _extract_links("[Page Title](page-title)")
        assert len(links) == 1
        assert links[0]["link_text"] == "Page Title"

    def test_special_characters_in_path(self):
        links = _extract_links("[Path](path/with/slashes-and-dashes)")
        assert len(links) == 1
        assert links[0]["target_path"] == "path/with/slashes-and-dashes"

    def test_empty_link_text(self):
        links = _extract_links("[](empty-text-link)")
        assert len(links) == 1
        assert links[0]["link_text"] == ""

    def test_position_tracking(self):
        content = "Before [Link A](a) middle [Link B](b) after"
        links = _extract_links(content)
        assert len(links) == 2
        # Position should increase for later links
        assert links[0]["position"] < links[1]["position"]


# ---------------------------------------------------------------------------
# _extract_external_links tests
# ---------------------------------------------------------------------------


class TestExtractExternalLinks:
    """Tests for _extract_external_links — external URL extraction."""

    def test_simple_external_link(self):
        links = _extract_external_links("[Google](https://google.com)")
        assert len(links) == 1
        assert links[0]["link_text"] == "Google"
        assert links[0]["url"] == "https://google.com"

    def test_multiple_external_links(self):
        content = "[A](https://a.com)\n[B](https://b.com)"
        links = _extract_external_links(content)
        assert len(links) == 2
        assert links[0]["url"] == "https://a.com"
        assert links[1]["url"] == "https://b.com"

    def test_ignores_wiki_internal_links(self):
        links = _extract_external_links("[Internal](local-page)")
        assert len(links) == 0

    def test_ignores_image_links(self):
        links = _extract_external_links("![Image](https://example.com/img.png)")
        assert len(links) == 0

    def test_http_and_https(self):
        content = "[HTTP](http://example.com) [HTTPS](https://example.com)"
        links = _extract_external_links(content)
        assert len(links) == 2

    def test_empty_content(self):
        links = _extract_external_links("")
        assert len(links) == 0


# ---------------------------------------------------------------------------
# markdown_to_html tests
# ---------------------------------------------------------------------------


class TestMarkdownToHtml:
    """Tests for markdown_to_html — markdown to HTML conversion."""

    def test_basic_paragraph(self):
        html = markdown_to_html("Hello world")
        assert "<p>" in html
        assert "Hello world" in html

    def test_headings(self):
        html = markdown_to_html("# Title\n\n## Section")
        assert "<h1>" in html or "Title" in html
        assert "<h2>" in html or "Section" in html

    def test_code_blocks(self):
        html = markdown_to_html("```python\nprint('hello')\n```")
        assert "print" in html or "<code>" in html or "<pre>" in html

    def test_bold_and_italic(self):
        html = markdown_to_html("**bold** and *italic*")
        assert "<strong>" in html or "<em>" in html

    def test_links(self):
        html = markdown_to_html("[Link](http://example.com)")
        assert '<a href' in html
        assert 'Link' in html

    def test_empty_string(self):
        html = markdown_to_html("")
        assert isinstance(html, str)

    def test_tables(self):
        html = markdown_to_html("| A | B |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in html or "<th>" in html


# ---------------------------------------------------------------------------
# get_file_hash tests (needs temp file)
# ---------------------------------------------------------------------------


class TestGetFileHash:
    """Tests for get_file_hash — SHA-256 file hashing."""

    def test_known_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            h = get_file_hash(f.name)
        Path(f.name).unlink()
        assert len(h) == 64  # SHA-256 hex
        # "hello world" SHA-256
        assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            f.flush()
            h = get_file_hash(f.name)
        Path(f.name).unlink()
        # Empty file SHA-256
        assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_nonexistent_file(self):
        h = get_file_hash("/nonexistent/path/file.txt")
        assert h == ""

    def test_different_content_produces_different_hash(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1:
            f1.write("content A")
            f1.flush()
            h1 = get_file_hash(f1.name)
            p1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f2:
            f2.write("content B")
            f2.flush()
            h2 = get_file_hash(f2.name)
            p2 = f2.name

        Path(p1).unlink()
        Path(p2).unlink()
        assert h1 != h2

    def test_same_content_produces_same_hash(self):
        content = "identical content"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1:
            f1.write(content)
            f1.flush()
            h1 = get_file_hash(f1.name)
            p1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f2:
            f2.write(content)
            f2.flush()
            h2 = get_file_hash(f2.name)
            p2 = f2.name

        Path(p1).unlink()
        Path(p2).unlink()
        assert h1 == h2


# ---------------------------------------------------------------------------
# extract_code_structure tests (needs temp .py file)
# ---------------------------------------------------------------------------


class TestExtractCodeStructure:
    """Tests for extract_code_structure — Python AST parsing."""

    def test_simple_function(self):
        code = "def foo():\n    pass\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            result = extract_code_structure(f.name)
        Path(f.name).unlink()
        funcs = result.get("functions", [])
        names = {f["name"] for f in funcs}
        assert "foo" in names

    def test_class_with_method(self):
        code = "class MyClass:\n    def method(self):\n        pass\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            result = extract_code_structure(f.name)
        Path(f.name).unlink()
        classes = result.get("classes", [])
        class_names = {c["name"] for c in classes}
        assert "MyClass" in class_names

    def test_imports(self):
        code = "import os\nfrom sys import path\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            result = extract_code_structure(f.name)
        Path(f.name).unlink()
        imports = result.get("imports", [])
        assert len(imports) >= 1

    def test_empty_file(self):
        code = ""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            result = extract_code_structure(f.name)
        Path(f.name).unlink()
        assert isinstance(result, dict)
        assert "functions" in result
        assert "classes" in result

    def test_nonexistent_file(self):
        result = extract_code_structure("/nonexistent/file.py")
        assert isinstance(result, dict)
        # Should handle gracefully
        assert "functions" in result or "error" in str(result).lower()
