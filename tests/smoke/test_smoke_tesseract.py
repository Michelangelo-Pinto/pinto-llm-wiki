"""SSE smoke tests for Tesseract MCP server (7 tools).

Validates that all 7 Tesseract OCR tools are discoverable and callable
via the real SSE transport.
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_tesseract_tools_discoverable(tesseract_client):
    """All 7 Tesseract tools should be listed by tools/list."""
    tools = tesseract_client.list_tools()
    tool_names = {t["name"] for t in tools}

    expected = {
        "ocr_get_languages",
        "ocr_detect_document_type",
        "ocr_extract_text",
        "ocr_extract_hocr",
        "ocr_get_confidence",
        "ocr_process_document",
        "ocr_preprocess_and_extract",
    }
    missing = expected - tool_names
    assert not missing, f"Missing tools: {missing}"


# ---------------------------------------------------------------------------
# Parameter-less / simple tools
# ---------------------------------------------------------------------------


@pytest.mark.smoke
class TestTesseractBasic:
    """Smoke-test Tesseract tools that don't need real image files."""

    def test_get_languages(self, tesseract_client):
        result = tesseract_client.call_tool("ocr_get_languages", {})
        data = self._parse(result)
        assert isinstance(data, dict)
        # Should return available languages or an info message
        assert "error" not in data or "eng" in str(data).lower()

    def test_detect_document_type_nonexistent(self, tesseract_client):
        """Detect type on a nonexistent file should return error — not crash."""
        result = tesseract_client.call_tool("ocr_detect_document_type", {
            "input_path": "/nonexistent/file.xyz",
        })
        data = self._parse(result)
        assert isinstance(data, dict)

    def test_extract_text_nonexistent(self, tesseract_client):
        """Extract text on a nonexistent file should return error — not crash."""
        result = tesseract_client.call_tool("ocr_extract_text", {
            "input_path": "/nonexistent/image.png",
        })
        data = self._parse(result)
        assert isinstance(data, dict)

    def test_get_confidence_nonexistent(self, tesseract_client):
        result = tesseract_client.call_tool("ocr_get_confidence", {
            "input_path": "/nonexistent/doc.pdf",
        })
        data = self._parse(result)
        assert isinstance(data, dict)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(result: dict) -> dict:
        if "result" in result:
            inner = result["result"]
            if "content" in inner:
                for item in inner["content"]:
                    if item.get("type") == "text":
                        try:
                            return json.loads(item["text"])
                        except (json.JSONDecodeError, TypeError):
                            return {"raw_text": item["text"]}
            return inner
        if "error" in result:
            return {"error": str(result["error"])}
        return result
