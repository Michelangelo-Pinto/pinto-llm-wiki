"""MCP tools for Tesseract OCR operations.

Tools provide:
- Text extraction from images and PDFs
- Document type detection (text vs scanned)
- HOCR output with bounding boxes and confidence
- Preprocessing pipeline for low-quality scans
- Hybrid document processing (direct text + OCR)
"""

import io
import json
import logging
import os
from pathlib import Path
from typing import List, Literal, Optional

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from .detector import classify_pdf
from .preprocess import preprocess_for_ocr

logger = logging.getLogger(__name__)


def ocr_get_languages() -> str:
    """List installed Tesseract language packs.

    Returns:
        JSON with list of available language codes (e.g., ["eng", "ita"]).
    """
    try:
        langs = pytesseract.get_languages()
        return json.dumps({"languages": langs, "count": len(langs)})
    except Exception as e:
        return json.dumps({"error": str(e)})


def ocr_detect_document_type(input_path: str) -> str:
    """Analyze a PDF to determine if pages are text-based or scanned.

    Uses PyMuPDF text sampling to classify each page. Text pages can be
    read directly; scanned pages must go through OCR.

    Args:
        input_path: Path to the PDF file.

    Returns:
        JSON with per-page classification, summary, and recommendation.
    """
    path = Path(input_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {input_path}"})
    if path.suffix.lower() != ".pdf":
        return json.dumps({"error": "Only PDF files are supported for type detection"})

    try:
        result = classify_pdf(str(path))
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Document type detection failed: {e}"})


def ocr_extract_text(
    input_path: str,
    language: str = "eng+ita",
    output_format: Literal["text", "detailed", "tsv"] = "text",
    page_range: Optional[str] = None,
    dpi: int = 300,
    psm: int = 3,
) -> str:
    """Extract text from an image or PDF using Tesseract OCR.

    For PDFs, each page is rendered at the specified DPI then OCR'd.
    Text-based PDFs should use ocr_process_document for hybrid extraction.

    Args:
        input_path: Path to image or PDF file.
        language: Tesseract language codes joined by '+' (e.g., "eng+ita").
        output_format: "text" for plain text, "detailed" for per-page JSON,
                       "tsv" for tab-separated confidence data.
        page_range: Page range for PDFs (e.g., "1-5"). None = all pages.
        dpi: Rendering resolution for PDF pages (default 300).
        psm: Page Segmentation Mode (default 3 = auto).
             Common: 3=auto, 6=uniform block, 11=sparse text, 13=raw line.

    Returns:
        Extracted text in the requested format.
    """
    path = Path(input_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {input_path}"})

    config = f"--psm {psm}"
    if output_format == "tsv":
        config += " tsv"

    try:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return _ocr_pdf(path, language, output_format, page_range, dpi, psm)
        else:
            return _ocr_image(input_path, language, output_format, psm)
    except Exception as e:
        return json.dumps({"error": f"OCR failed: {e}"})


def _ocr_pdf(pdf_path, language, output_format, page_range, dpi, psm):
    """OCR each page of a PDF by rendering to image first."""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    start_page = 0
    end_page = total_pages
    if page_range:
        parts = page_range.split("-")
        start_page = int(parts[0]) - 1
        end_page = int(parts[1]) if len(parts) > 1 else start_page + 1
        start_page = max(0, start_page)
        end_page = min(total_pages, end_page)

    pages_text = []
    for i in range(start_page, end_page):
        page = doc[i]
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        text = pytesseract.image_to_string(img, lang=language, config=f"--psm {psm}")
        if output_format == "detailed":
            data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data["conf"] if c != "-1"]
            pages_text.append({
                "page": i + 1,
                "text": text,
                "confidence": round(sum(confs) / len(confs), 1) if confs else 0,
            })
        else:
            pages_text.append(text)

    doc.close()

    if output_format == "text":
        return "\n\n".join(pages_text)
    return json.dumps({"pages": pages_text, "total_pages": len(pages_text)})


def _ocr_image(image_path, language, output_format, psm):
    """OCR a single image file."""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang=language, config=f"--psm {psm}")
    return text


def ocr_extract_hocr(
    input_path: str,
    language: str = "eng+ita",
    page_range: Optional[str] = None,
) -> str:
    """Extract HOCR (HTML+OCR) with bounding boxes and confidence scores.

    HOCR is a standard format embedding recognized text, bounding box
    coordinates, and per-word confidence in HTML markup.

    Args:
        input_path: Path to image or PDF.
        language: Tesseract language codes.
        page_range: Page range for PDFs.

    Returns:
        HOCR XML/HTML string with structural metadata.
    """
    path = Path(input_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {input_path}"})

    try:
        if path.suffix.lower() == ".pdf":
            doc = fitz.open(path)
            total_pages = len(doc)
            start = 0
            end = total_pages
            if page_range:
                parts = page_range.split("-")
                start = int(parts[0]) - 1
                end = int(parts[1]) if len(parts) > 1 else start + 1

            results = []
            for i in range(start, end):
                pix = doc[i].get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                hocr = pytesseract.image_to_pdf_or_hocr(img, lang=language, extension="hocr")
                results.append(hocr.decode("utf-8") if isinstance(hocr, bytes) else hocr)
            doc.close()
            return "\n".join(results)
        else:
            hocr = pytesseract.image_to_pdf_or_hocr(str(path), lang=language, extension="hocr")
            return hocr.decode("utf-8") if isinstance(hocr, bytes) else hocr
    except Exception as e:
        return json.dumps({"error": f"HOCR extraction failed: {e}"})


def ocr_get_confidence(input_path: str, language: str = "eng+ita") -> str:
    """Return per-word confidence scores for an image or PDF page.

    Args:
        input_path: Path to image or PDF.
        language: Tesseract language codes.

    Returns:
        JSON with per-word confidences and overall average.
    """
    path = Path(input_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {input_path}"})

    try:
        img = Image.open(path)
        data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)

        word_confidences = []
        for i, word in enumerate(data["text"]):
            if word.strip() and data["conf"][i] != "-1":
                word_confidences.append({
                    "word": word,
                    "confidence": int(data["conf"][i]),
                })

        avg_conf = round(
            sum(w["confidence"] for w in word_confidences) / len(word_confidences), 1
        ) if word_confidences else 0

        return json.dumps({
            "word_count": len(word_confidences),
            "average_confidence": avg_conf,
            "words": word_confidences[:20],  # First 20 words for inspection
            "truncated": len(word_confidences) > 20,
        })
    except Exception as e:
        return json.dumps({"error": f"Confidence extraction failed: {e}"})


def ocr_process_document(
    input_path: str,
    language: str = "eng+ita",
    auto_detect_type: bool = True,
    preprocess: bool = True,
    dpi: int = 300,
) -> str:
    """Full document OCR with intelligent routing.

    Text-based PDF pages are read directly via PyMuPDF (fast).
    Scanned/image pages are rendered at DPI and OCR'd via Tesseract.
    This hybrid approach minimizes OCR overhead for mixed documents.

    Args:
        input_path: Path to the document (PDF or image).
        language: Tesseract language codes.
        auto_detect_type: If True, classify each page and route accordingly.
        preprocess: If True, apply grayscale+deskew+threshold before OCR.
        dpi: Resolution for rendering PDF pages.

    Returns:
        JSON with full text, per-page breakdown, and processing summary.
    """
    path = Path(input_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {input_path}"})

    try:
        suffix = path.suffix.lower()
        if suffix != ".pdf":
            # Single image: OCR directly
            text = ocr_extract_text(input_path, language, "text", dpi=dpi)
            return json.dumps({
                "file": str(path),
                "type": "image",
                "total_pages": 1,
                "text_pages": 0,
                "scanned_pages": 1,
                "full_text": text,
            })

        doc = fitz.open(path)
        total_pages = len(doc)
        text_pages = 0
        scanned_pages = 0
        pages = []

        for i, page in enumerate(doc):
            if auto_detect_type:
                from .detector import classify_pdf_page
                ptype = classify_pdf_page(page)
            else:
                ptype = "scanned"  # Force OCR

            if ptype == "text":
                text = page.get_text()
                text_pages += 1
                pages.append({"page": i + 1, "type": "text", "text": text})
            else:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                if preprocess:
                    import numpy as np
                    img_np = np.array(img)
                    img_np = preprocess_for_ocr(img_np, ["grayscale", "deskew", "threshold"])
                    img = Image.fromarray(img_np)
                text = pytesseract.image_to_string(img, lang=language)
                scanned_pages += 1
                pages.append({"page": i + 1, "type": ptype, "text": text})

        doc.close()

        full_text = "\n\n".join(p["text"] for p in pages)
        return json.dumps({
            "file": str(path),
            "total_pages": total_pages,
            "text_pages": text_pages,
            "scanned_pages": scanned_pages,
            "pages": pages,
            "full_text": full_text,
        })
    except Exception as e:
        return json.dumps({"error": f"Document processing failed: {e}"})


def ocr_preprocess_and_extract(
    input_path: str,
    language: str = "eng+ita",
    preprocess_steps: List[str] = None,
) -> str:
    """Apply image preprocessing then OCR.

    For low-quality scanned documents where standard OCR produces poor
    results. Applies configurable preprocessing steps before Tesseract.

    Args:
        input_path: Path to image file.
        language: Tesseract language codes.
        preprocess_steps: Steps to apply. Default: ["grayscale","deskew","threshold"].
                         Options: grayscale, deskew, threshold, denoise, sharpen.

    Returns:
        Extracted text after preprocessing.
    """
    if preprocess_steps is None:
        preprocess_steps = ["grayscale", "deskew", "threshold"]

    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(input_path))
        if img is None:
            return json.dumps({"error": f"Cannot read image: {input_path}"})

        processed = preprocess_for_ocr(img, preprocess_steps)
        text = pytesseract.image_to_string(processed, lang=language)

        return text
    except Exception as e:
        return json.dumps({"error": f"Preprocessing + OCR failed: {e}"})
