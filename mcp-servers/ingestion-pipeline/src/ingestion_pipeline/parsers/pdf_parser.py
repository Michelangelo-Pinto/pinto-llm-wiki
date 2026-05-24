"""PDF text extraction using PyMuPDF. Hybrid: direct text for text pages, OCR via Tesseract for scanned pages."""

import io
import logging
from pathlib import Path
from typing import Dict, List

import fitz
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)


def extract_text_pdf(file_path: str, dpi: int = 300) -> str:
    """Extract text from a text-based PDF using PyMuPDF directly."""
    doc = fitz.open(file_path)
    texts = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            texts.append(text)
    doc.close()
    return "\n\n".join(texts)


def extract_scanned_pdf(file_path: str, language: str = "eng+ita", dpi: int = 300) -> str:
    """Extract text from a scanned/image-based PDF by rendering and OCR-ing each page."""
    doc = fitz.open(file_path)
    texts = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang=language)
        if text.strip():
            texts.append(text)
    doc.close()
    return "\n\n".join(texts)


def extract_pdf_hybrid(file_path: str, language: str = "eng+ita", dpi: int = 300) -> Dict:
    """Hybrid extraction: text pages via PyMuPDF, scanned pages via Tesseract OCR.

    Args:
        file_path: Path to PDF file.
        language: Tesseract language codes.
        dpi: Rendering resolution for scanned pages.

    Returns:
        Dict with full_text and per_page breakdown.
    """
    from ..detector import _detect_pdf_type

    detection = _detect_pdf_type(Path(file_path))
    if not detection.get("needs_ocr", False):
        return {
            "file": file_path,
            "method": "direct",
            "full_text": extract_text_pdf(file_path),
        }

    doc = fitz.open(file_path)
    pages = []
    text_pages = 0
    scanned_pages = 0

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        has_enough_text = len(text) > 100 and len(text.split()) > 20

        if has_enough_text:
            text_pages += 1
            pages.append({"page": i + 1, "type": "text", "text": text})
        else:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img, lang=language)
            scanned_pages += 1
            pages.append({"page": i + 1, "type": "scanned", "text": text})

    doc.close()

    full_text = "\n\n".join(p["text"] for p in pages)
    return {
        "file": file_path,
        "method": "hybrid",
        "total_pages": len(pages),
        "text_pages": text_pages,
        "scanned_pages": scanned_pages,
        "full_text": full_text,
    }
