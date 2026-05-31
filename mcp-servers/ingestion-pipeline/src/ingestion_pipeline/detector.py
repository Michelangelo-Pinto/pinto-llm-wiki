"""File type detection for document ingestion pipeline.

Classifies documents into: text_pdf, scanned_pdf, text_docx, mixed_docx,
markdown, text, html, json, xml, epub, image. Uses file extension and
content sampling via PyMuPDF for PDF classification.
"""

import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# Mapping from file extensions to types
EXTENSION_MAP = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".rst": "text",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".tif": "image",
    ".bmp": "image",
    ".gif": "image",
    ".webp": "image",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".xml": "xml",
    ".epub": "epub",
}

SUPPORTED_EXTENSIONS = set(EXTENSION_MAP.keys())


def detect_document_type(file_path: str) -> Dict:
    """Detect the document type and determine processing strategy.

    Args:
        file_path: Absolute or relative path to the document.

    Returns:
        Dict with keys:
        - file_path: Original path
        - extension: File extension (lowercase)
        - category: Broad category (pdf, docx, markdown, text, image)
        - subtype: Fine-grained type (text_pdf, scanned_pdf, text_docx,
                   mixed_docx, markdown, text, image)
        - needs_ocr: Whether OCR is required
        - supported: Whether the file type is supported
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        return {
            "file_path": str(path),
            "extension": suffix,
            "category": "unknown",
            "subtype": "unsupported",
            "needs_ocr": False,
            "supported": False,
            "error": f"Unsupported file type: {suffix}",
        }

    category = EXTENSION_MAP[suffix]

    if category == "pdf":
        return _detect_pdf_type(path)
    elif category == "docx":
        return _detect_docx_type(path)
    elif category == "image":
        return {
            "file_path": str(path),
            "extension": suffix,
            "category": "image",
            "subtype": "image",
            "needs_ocr": True,
            "supported": True,
        }
    else:
        # markdown or text — no OCR needed
        return {
            "file_path": str(path),
            "extension": suffix,
            "category": category,
            "subtype": category,
            "needs_ocr": False,
            "supported": True,
        }


def _detect_pdf_type(path: Path) -> Dict:
    """Classify a PDF as text-based or scanned by sampling first 5 pages."""
    import fitz

    try:
        doc = fitz.open(str(path))
        total_pages = len(doc)
        pages_to_check = min(5, total_pages)

        text_chars = 0
        image_pages = 0

        for i in range(pages_to_check):
            page = doc[i]
            text = page.get_text().strip()
            text_chars += len(text)

            # Check image coverage on this page
            page_area = abs(page.rect)
            raw_dict = page.get_text("rawdict")
            image_blocks = [b for b in raw_dict["blocks"] if b.get("type") == 1]
            img_area = sum(
                (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1])
                for b in image_blocks
            )
            img_ratio = img_area / page_area if page_area > 0 else 0
            if img_ratio > 0.80:
                image_pages += 1

        doc.close()

        avg_chars_per_page = text_chars / pages_to_check
        image_ratio = image_pages / pages_to_check

        # Heuristic: < 50 chars per page average = scanned
        #            > 80% pages are images = scanned
        is_scanned = avg_chars_per_page < 50 or image_ratio > 0.5

        return {
            "file_path": str(path),
            "extension": ".pdf",
            "category": "pdf",
            "subtype": "scanned_pdf" if is_scanned else "text_pdf",
            "needs_ocr": is_scanned,
            "supported": True,
            "total_pages": total_pages,
            "avg_chars_per_page": round(avg_chars_per_page, 1),
            "image_page_ratio": round(image_ratio, 2),
        }
    except Exception as e:
        logger.error("PDF detection failed for %s: %s", path, e)
        return {
            "file_path": str(path),
            "extension": ".pdf",
            "category": "pdf",
            "subtype": "text_pdf",
            "needs_ocr": False,
            "supported": True,
            "error": str(e),
        }


def _detect_docx_type(path: Path) -> Dict:
    """Check if a DOCX has embedded images that need OCR."""
    try:
        import zipfile
        has_images = False
        with zipfile.ZipFile(str(path)) as z:
            media_files = [n for n in z.namelist() if n.startswith("word/media/")]
            has_images = len(media_files) > 0
        return {
            "file_path": str(path),
            "extension": ".docx",
            "category": "docx",
            "subtype": "mixed_docx" if has_images else "text_docx",
            "needs_ocr": has_images,
            "supported": True,
            "has_embedded_images": has_images,
        }
    except Exception as e:
        logger.error("DOCX detection failed for %s: %s", path, e)
        return {
            "file_path": str(path),
            "extension": ".docx",
            "category": "docx",
            "subtype": "text_docx",
            "needs_ocr": False,
            "supported": True,
            "error": str(e),
        }
