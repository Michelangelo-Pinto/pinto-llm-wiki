"""PDF page classification: text-based vs scanned/image-based.

Uses PyMuPDF (fitz) to sample text and image coverage on each page.
This determines whether to extract text directly or invoke OCR.

Strategy:
1. Text extraction yield: zero text = scanned for sure
2. Text area coverage ratio: very low = image-heavy
3. Image coverage ratio: very high + short words = searchable_ocr
"""

import logging
from typing import Dict, Literal

import fitz

logger = logging.getLogger(__name__)

PageType = Literal["text", "scanned", "searchable_ocr"]


def classify_pdf_page(page) -> PageType:
    """Classify a single PyMuPDF page as text, scanned, or searchable_ocr.

    Args:
        page: A fitz.Page object from PyMuPDF.

    Returns:
        "text": Native text content, extract directly.
        "scanned": Pure image, must OCR.
        "searchable_ocr": Image with hidden OCR layer, prefer fresh OCR.
    """
    text = page.get_text().strip()
    page_area = abs(page.rect)

    # Signal 1: No text at all = definitely scanned
    if len(text) == 0:
        return "scanned"

    # Signal 2: Text area coverage ratio
    text_blocks = page.get_text("blocks")
    text_area = sum(abs(fitz.Rect(b[:4])) for b in text_blocks)
    text_ratio = text_area / page_area if page_area > 0 else 0

    # Signal 3: Image coverage ratio
    raw_dict = page.get_text("rawdict")
    image_blocks = [b for b in raw_dict["blocks"] if b.get("type") == 1]
    img_area = sum(
        (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1])
        for b in image_blocks
    )
    img_ratio = img_area / page_area if page_area > 0 else 0

    # Signal 4: OCR'd text tends to be fragmented with short words
    words = text.split()
    avg_word_len = sum(len(w) for w in words) / max(len(words), 1)

    if text_ratio < 0.005:
        return "scanned"
    elif img_ratio > 0.80 and avg_word_len < 3.5:
        return "searchable_ocr"
    elif img_ratio > 0.80:
        return "scanned"
    else:
        return "text"


def classify_pdf(file_path: str) -> Dict:
    """Classify all pages of a PDF and return overall assessment.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Dict with per-page classification, summary counts, and needs_ocr flag.
    """
    doc = fitz.open(file_path)
    pages = {}
    scanned_count = 0
    ocr_count = 0
    text_count = 0

    for i, page in enumerate(doc):
        ptype = classify_pdf_page(page)
        pages[str(i)] = ptype
        if ptype == "scanned":
            scanned_count += 1
        elif ptype == "searchable_ocr":
            ocr_count += 1
        else:
            text_count += 1

    doc.close()

    needs_ocr = (scanned_count + ocr_count) > 0
    return {
        "file": file_path,
        "total_pages": len(pages),
        "scanned_pages": scanned_count,
        "searchable_ocr_pages": ocr_count,
        "text_pages": text_count,
        "needs_ocr": needs_ocr,
        "recommendation": "ocr" if needs_ocr else "direct_extraction",
    }
