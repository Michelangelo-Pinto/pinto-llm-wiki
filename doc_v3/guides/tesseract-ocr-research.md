# Tesseract OCR Research (v3)

> **This is a research document** — it contains benchmarks, comparisons, and architectural tradeoffs that informed the v3 design.
> **For the actual v3 implementation**, see [Tesseract MCP](../mcp-servers/tesseract-mcp.md) (port 8003, 7 tools) and [Ingestion Pipeline Design](../architecture/ingestion-pipeline-design.md) (in-process OCR for batch).
> **For usage workflows**, see [OCR and Ingestion Workflows](ocr-and-ingestion-workflows.md).

# Tesseract OCR Research: Dockerized (v3) CPU-Only OCR Service with MCP

Detailed findings covering deployment, API, comparison with PaddleOCR, MCP server design, preprocessing, and architecture tradeoffs.

---

## 1. Tesseract Docker Deployment

### Base Image Comparison

| Base Image | Base Size | C Library | Tesseract Final (~eng+ita) | Build Complexity | Compatibility |
|---|---|---|---|---|---|
| `python:3.12-alpine` | ~60 MB | musl | ~120–150 MB | Medium (musl quirks) | Some C-ext packages need source compiles |
| `python:3.12-slim` | ~150 MB | glibc | ~200–250 MB | Low (pip wheels work) | Broad — numpy, opencv, pymupdf all have wheels |
| `alpine:3.20` (multi-stage) | ~7 MB | musl | ~450 MB (4 langs, full build deps stripped) | High | Same musl caveats |
| `tesseract-ocr/tesseract:5.5.0` | Pre-built | glibc | ~500 MB | Very low | Binary-only, no Python |

**Recommendation: `python:3.12-slim`** is the pragmatic choice for this project because:

1. **PyMuPDF** and **OpenCV** (`cv2`) both have pre-built wheels for glibc — no source compilation needed.
2. The ~50–70 MB image size penalty vs Alpine is negligible compared to the operational pain of debugging musl-specific issues.
3. `slim` ships with `apt` which makes installing `tesseract-ocr` + language packs trivial.
4. glibc compatibility means standard Python C-extension wheels install instantly via `pip`.

**Alpine is viable if you pre-build wheels in a multi-stage Dockerfile** and only need pure Python + Tesseract (no OpenCV/PyMuPDF). But for this project with PyMuPDF, slim is simpler.

### Minimal Dockerfile

```dockerfile
FROM python:3.12-slim

# Install Tesseract + English and Italian language data
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ita \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set Tesseract data path
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# Install Python dependencies
RUN pip install --no-cache-dir \
    pytesseract \
    pymupdf \
    pillow \
    opencv-python-headless \
    numpy

WORKDIR /app

# Copy application code
COPY . .

# Verify Tesseract installation
RUN tesseract --list-langs && tesseract --version

CMD ["python", "-u", "server.py"]
```

**Image size breakdown:**

| Layer | Approximate Size |
|---|---|
| `python:3.12-slim` base | 150 MB |
| `tesseract-ocr` binary + leptonica | 25 MB |
| `tesseract-ocr-eng` (English traineddata) | 12 MB (installed: ~30 MB) |
| `tesseract-ocr-ita` (Italian traineddata) | 7 MB (installed: ~15 MB) |
| `opencv-python-headless` | 25 MB |
| `pymupdf` | 35 MB |
| `pytesseract` + `pillow` + `numpy` | 15 MB |
| **Total estimated** | **~270–300 MB** |

For comparison:
- PaddleOCR Docker image: **~1.2 GB** (python:3.10-slim + paddlepaddle + paddleocr + models)
- EasyOCR Docker image: **~2.1 GB** (torch + CRAFT + recognizer)

### Language Pack Details

| Language | Alpine Package | Size (download) | Installed Size | traineddata File |
|---|---|---|---|---|
| English | `tesseract-ocr-data-eng` | ~8 MB | ~30 MB | `eng.traineddata` |
| Italian | `tesseract-ocr-data-ita` | ~6.6 MB | ~15 MB | `ita.traineddata` |

The `tessdata` repository uses three quality tiers:
- **`tessdata`** (default): Integer LSTM + legacy engine. Full support. ~12–40 MB per language.
- **`tessdata_best`**: Float LSTM, highest accuracy. ~30–80 MB per language. Slower.
- **`tessdata_fast`**: Integer LSTM only. ~4–20 MB per language. Fastest, no legacy fallback.

For this project, **`tessdata`** (the default installed by apt packages) is the right choice — it supports `--oem 0` (legacy) and `--oem 1` (LSTM) engine modes.

---

## 2. Tesseract Python API (pytesseract)

### Basic Text Extraction

```python
import pytesseract
from PIL import Image

# Simple extraction
text = pytesseract.image_to_string(Image.open("document.png"))

# With explicit engine and page segmentation mode
text = pytesseract.image_to_string(
    Image.open("document.png"),
    lang="eng+ita",
    config="--oem 3 --psm 6"
)
```

### PDF Processing (Convert Pages → Images → OCR)

pytesseract **cannot process PDFs directly**. You must convert each PDF page to an image first.

**Option A: PyMuPDF (recommended — same dep we already need)**

```python
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

def ocr_pdf_with_pymupdf(pdf_path: str, dpi: int = 300) -> list[dict]:
    """
    Convert PDF pages to images via PyMuPDF, then OCR each page.
    Returns list of {page_num, text, confidence_data}.
    """
    doc = fitz.open(pdf_path)
    results = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Render page to pixmap at target DPI
        zoom = dpi / 72  # PDF default is 72 DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # OCR the image
        text = pytesseract.image_to_string(img, lang="eng+ita")
        data = pytesseract.image_to_data(img, lang="eng+ita", output_type=pytesseract.Output.DICT)

        results.append({
            "page": page_num + 1,
            "text": text.strip(),
            "data": data,
        })

    doc.close()
    return results
```

**Option B: pdf2image (poppler-based — adds another dependency)**

```python
from pdf2image import convert_from_path

images = convert_from_path("document.pdf", dpi=300)
for i, img in enumerate(images):
    text = pytesseract.image_to_string(img, lang="eng+ita")
```

PyMuPDF is preferred since it's already a dependency for document classification.

### Detecting Scanned vs Text-Based PDF Pages

PyMuPDF provides a multi-signal approach for classifying PDF pages:

```python
import fitz

def classify_pdf_page(page: fitz.Page) -> dict:
    """
    Classify a PDF page as text-based, scanned/image-based, or mixed.
    Uses multiple signals for robust classification.
    """
    # Signal 1: Extract native text
    text = page.get_text().strip()

    # Signal 2: Get text block coverage area
    blocks = page.get_text("blocks")
    page_area = abs(page.rect)
    text_area = 0.0
    for b in blocks:
        if b[6] == 0:  # type 0 = text block
            r = fitz.Rect(b[:4])
            text_area += abs(r)
    text_coverage = text_area / page_area if page_area > 0 else 0

    # Signal 3: Count images on page
    images = page.get_images(full=True)
    image_count = len(images)

    # Signal 4: Count meaningful text characters
    char_count = sum(1 for c in text if c.isalpha())

    # Classification logic
    if char_count > 100 and text_coverage > 0.15:
        if image_count == 0:
            return {"type": "text", "confidence": "high", "text_coverage": text_coverage}
        else:
            return {"type": "mixed", "confidence": "medium", "text_coverage": text_coverage,
                    "image_count": image_count}
    elif image_count > 0:
        return {"type": "scanned", "confidence": "high" if char_count < 20 else "medium",
                "image_count": image_count, "text_coverage": text_coverage}
    else:
        return {"type": "unknown", "confidence": "low", "text_coverage": text_coverage,
                "char_count": char_count}


def classify_pdf(pdf_path: str) -> dict:
    """
    Classify entire PDF document. Returns per-page classifications
    and an overall document type.
    """
    doc = fitz.open(pdf_path)
    pages = []
    scanned_count = 0
    text_count = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        classification = classify_pdf_page(page)
        classification["page"] = page_num + 1
        pages.append(classification)

        if classification["type"] == "scanned":
            scanned_count += 1
        elif classification["type"] == "text":
            text_count += 1

    doc.close()

    total = len(pages)
    if scanned_count == total:
        doc_type = "fully_scanned"
    elif text_count == total:
        doc_type = "fully_text"
    else:
        doc_type = "mixed"

    return {
        "document_type": doc_type,
        "total_pages": total,
        "scanned_pages": scanned_count,
        "text_pages": text_count,
        "pages": pages,
    }
```

**Key principle:** A page is "scanned" when `page.get_text()` returns little to no text (most text is embedded in images). Text coverage ratio below 15% with images present is the strongest signal. PyMuPDF cannot detect "obfuscated fonts" (text rendered as glyphs by custom fonts) — those pages appear to have text but are effectively scanned.

### Multiple Language Support (English + Italian)

```python
# Combined language mode: Tesseract loads both language models simultaneously
text = pytesseract.image_to_string(
    img,
    lang="eng+ita",  # Plus-separated language codes
    config="--oem 3 --psm 6"
)
```

Tesseract loads both language models into memory and uses them jointly. This means:
- Words in either language are recognized.
- Mixed-language documents (e.g., English with Italian citations) work correctly.
- Memory usage increases: each language model is ~15–30 MB loaded.
- The `+` separator is standard — `eng+ita+fra` for three languages.

**Important performance note:** Throughput drops with more language packs loaded. Benchmark:
- English only: ~2.3 pages/sec
- 4 languages: ~1.4 pages/sec
- 10 languages: ~0.9 pages/sec

### Table Detection Capabilities

**Tesseract has NO built-in table structure detection.** It does not produce table markup, row/column boundaries, or cell-level output. However, two approaches work:

**Approach A: Bounding-box clustering (simple, for clean printed tables)**

```python
import pytesseract
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
import numpy as np

def extract_table_from_image(img, distance_threshold: float = 25):
    """
    Extract table from image by clustering OCR bounding boxes.
    Uses AgglomerativeClustering on x-coordinates for columns,
    then groups by y-coordinate proximity for rows.
    """
    # Get per-word data
    data = pytesseract.image_to_data(
        img,
        output_type=pytesseract.Output.DATAFRAME,
        config="--psm 6"
    )

    # Drop empty/low-confidence words
    data = data[(data["conf"] > 0) & (data["text"].notna())]
    data = data[data["text"].str.strip() != ""]

    # Cluster columns by x-coordinate (left edge)
    X = data[["left"]].values
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold
    )
    data["col"] = clustering.fit_predict(X)

    # Sort columns left to right
    col_medians = data.groupby("col")["left"].median().sort_values()
    col_order = {old: new for new, old in enumerate(col_medians.index)}
    data["col"] = data["col"].map(col_order)

    # Group rows by clustering top coordinates
    Y = data[["top"]].values.astype(float)
    row_clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=15
    )
    data["row"] = row_clustering.fit_predict(Y)

    # Build DataFrame
    table = data.pivot(index="row", columns="col", values="text")
    table = table.sort_index()
    table = table[sorted(table.columns)]

    return table
```

**Approach B: Preprocess with OpenCV for border-based tables**

```python
import cv2

def detect_table_grid(image_path: str):
    """Detect table structure using morphological operations on grid lines."""
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    _, thresh = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)

    # Detect horizontal lines
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    # Detect vertical lines
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    # Combine
    grid = cv2.add(h_lines, v_lines)

    # Find contours for cells
    contours, _ = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    return [cv2.boundingRect(c) for c in contours]
```

**Bottom line:** Tesseract table extraction requires custom post-processing. For complex tables (merged cells, spanning headers), this approach is fragile. PaddleOCR's layout analysis has similar limitations. For production-grade table extraction, consider:
- **Camelot** / **Tabula** (PDF text-based tables only)
- **AWS Textract** / **Azure Form Recognizer** (cloud, excellent tables)
- **IBM Docling** (open-source, has Tesseract integration and table structure awareness)

### Confidence Scores per Word/Line

```python
import pytesseract

# image_to_data returns TSV-like dict with confidence per word
data = pytesseract.image_to_data(
    img,
    lang="eng+ita",
    output_type=pytesseract.Output.DICT,
    config="--psm 6"
)

# Available fields:
# - 'conf': Confidence score 0-100 per word (-1 means no text)
# - 'text': The recognized word
# - 'left', 'top', 'width', 'height': Bounding box
# - 'level': 1=page, 2=block, 3=paragraph, 4=line, 5=word
# - 'block_num', 'par_num', 'line_num', 'word_num': Hierarchy

# Filter for word-level results with confidence
words = []
for i in range(len(data["text"])):
    if data["level"][i] == 5:  # word level
        words.append({
            "text": data["text"][i].strip(),
            "confidence": int(data["conf"][i]),
            "bbox": {
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i]
            },
            "block": data["block_num"][i],
            "line": data["line_num"][i],
        })

# Mean confidence across the page
valid_confidences = [w["confidence"] for w in words if w["confidence"] > 0]
avg_confidence = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0
print(f"Average word confidence: {avg_confidence:.1f}%")
```

### HOCR/TSV/ALTO Output Formats

```python
# HOCR output (HTML-based structured OCR — includes bounding boxes, confidences)
hocr = pytesseract.image_to_pdf_or_hocr(
    "document.png",
    extension="hocr",
    lang="eng+ita"
)
# Returns bytes containing XML/HTML with per-word positions and confidence

# Searchable PDF (embeds OCR text layer into image)
pdf = pytesseract.image_to_pdf_or_hocr(
    "document.png",
    extension="pdf",
    lang="eng+ita"
)
with open("searchable.pdf", "wb") as f:
    f.write(pdf)

# ALTO XML (library standard for OCR output)
alto_xml = pytesseract.image_to_alto_xml("document.png", lang="eng+ita")

# TSV (tab-separated values — same data as image_to_data)
tsv = pytesseract.image_to_data("document.png", output_type=pytesseract.Output.STRING)

# Multiple outputs in ONE tesseract call (saves compute):
text, hocr_bytes, tsv_str = pytesseract.run_and_get_multiple_output(
    "document.png",
    extensions=["txt", "hocr", "tsv"],
    lang="eng+ita"
)
```

**Format comparison:**

| Format | Contains | Best For |
|---|---|---|
| TXT | Plain text | Simple extraction, indexing |
| HOCR | HTML with bboxes + confidence per word | Structured data, searchable archives |
| TSV (data) | Tabular with all metadata | Programmatic processing, pandas |
| ALTO XML | Library-standard XML | Interoperability with library/digital archive tools |
| Searchable PDF | PDF with hidden text layer | Archival, human-readable with copy-paste |

---

## 3. Tesseract vs PaddleOCR Comparison

### Accuracy Comparison

| Benchmark | Tesseract 5 | PaddleOCR (PP-OCRv5) | Notes |
|---|---|---|---|
| **Clean printed text** (800 scanned docs) | CER ~0.02 (98% accuracy) | CER ~0.01 | Tesseract nearly perfect on clean scans |
| **Noisy/complex documents** (general dataset) | CER ~0.18 (82% accuracy) | CER ~0.10 (90% accuracy) | PaddleOCR 2x better on complex inputs |
| **Table/layout documents** | Partial structure | Region detection only | Neither produces structured tables out of box |
| **OCR-agnostic (OmniDocBench)** | ~55–65 composite | ~74 composite | PaddleOCR better at document understanding |

**Key insight:** On clean, high-contrast, well-aligned scanned documents, Tesseract is excellent. On photographs, low-res scans, or documents with unusual layouts, PaddleOCR significantly outperforms it.

### Feature Comparison

| Feature | Tesseract | PaddleOCR | Notes |
|---|---|---|---|
| **Layout analysis** | Page segmentation modes (PSM 1–13), block/paragraph/line/word | Built-in detection model + recognition + angle classification | PaddleOCR's layout analysis is stronger |
| **Table extraction** | None built-in; requires custom clustering | None built-in; similar custom approach needed | Neither handles complex tables well |
| **Region detection** | Via PSM modes; basic bbox clustering | Dedicated text detection model (DB/DB++) | PaddleOCR better for sparse/irregular text |
| **Angle/orientation** | `image_to_osd()` — orientation + script detection | Built-in angle classifier | Both good; PaddleOCR slightly more robust |
| **Language support** | 100+ languages (trained data packs) | 80+ languages | Tesseract has wider coverage |
| **Handwriting** | Very poor | Poor to moderate | Neither is good; consider TrOCR or cloud APIs |
| **Model size** | ~30 MB per language | ~15 MB total (PP-OCRv5 models) | PaddleOCR's compressed models are impressively small |

### Performance Comparison

| Metric | Tesseract 5 (CPU) | PaddleOCR (CPU) |
|---|---|---|
| **Cold start** | <0.3 seconds | 4.2 seconds (model loading) |
| **Per-image latency** (clean doc) | ~593 ms | ~4,850 ms |
| **Per-image latency** (GPU) | N/A (CPU only) | ~79 ms |
| **FPS on clean images** | 8.2 fps | ~3.2 fps (CPU) / 12.7 fps (GPU) |
| **RAM idle** | ~300 MB | ~450 MB |
| **RAM peak (inference)** | ~400 MB | ~680 MB |
| **Disk (models + deps)** | ~30 MB | ~220 MB |
| **Docker image size** | ~300 MB | ~1,200 MB |

**Tesseract is 6–8x faster on CPU for clean documents** but significantly less accurate on complex inputs. PaddleOCR's 4-second cold start makes it unsuitable for serverless/lambda-style deployments.

### What We Lose by Switching to Tesseract

1. **Accuracy on noisy/complex scans:** ~2x worse CER (0.18 vs 0.10). This is the biggest loss.
2. **Robust text detection:** PaddleOCR's DB detection model handles irregular layouts, curved text, and sparse text better.
3. **Angle robustness:** PaddleOCR's angle classifier is more reliable for rotated documents.
4. **Asian/CJK script quality:** PaddleOCR was originally designed for Chinese and excels at CJK.

### What We Keep or Gain

1. **Clean document accuracy:** Nearly identical (CER 0.01 vs 0.02 on clean scans).
2. **Cold-start speed:** Tesseract starts instantly vs 4+ seconds for PaddleOCR.
3. **Docker image size:** 300 MB vs 1,200 MB — a 4x reduction.
4. **CPU performance:** 6–8x faster inference per page.
5. **Operational simplicity:** No torch/paddle dependency, no GPU drivers, no model downloads at startup.
6. **Maturity:** 40 years of production use, very stable, predictable behavior.

### Compensating for Tesseract's Weaknesses

**Strategy 1: Confidence-based routing**

```python
def smart_ocr(img, lang="eng+ita"):
    """Use Tesseract first; flag low-confidence results for review/rescan."""
    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

    words = []
    low_conf_words = []
    for i in range(len(data["text"])):
        if data["text"][i].strip():
            conf = int(data["conf"][i])
            if conf < 50:  # Low confidence threshold
                low_conf_words.append(data["text"][i].strip())
            words.append(data["text"][i].strip())

    avg_conf = sum(int(data["conf"][i]) for i in range(len(data["conf"])) if
                   data["text"][i].strip() and int(data["conf"][i]) > 0)
    avg_conf = avg_conf / len(words) if words else 0

    return {
        "text": " ".join(words),
        "average_confidence": avg_conf,
        "low_confidence_count": len(low_conf_words),
        "needs_manual_review": avg_conf < 70 or len(low_conf_words) > len(words) * 0.2,
    }
```

**Strategy 2: Aggressive preprocessing** (see Section 5 below) — proper grayscale, thresholding, deskewing, and DPI upscaling can bridge much of the accuracy gap.

**Strategy 3: PSM tuning per page type** — use `--psm 3` for general pages, `--psm 6` for uniform text blocks, `--psm 4` for single-column, `--psm 11` for sparse text.

**Strategy 4: Upscale to target resolution** — Tesseract works best when lowercase x-height is ~30–33 pixels. If the input is low DPI, upscale before OCR:

```python
from PIL import Image

def upscale_for_ocr(img: Image.Image, target_dpi: int = 300) -> Image.Image:
    """Upscale image to target DPI if it's below threshold."""
    # Assume image is 72 DPI if no DPI info (common for PDF renders)
    current_dpi = img.info.get("dpi", (72, 72))[0]
    if current_dpi < target_dpi:
        scale = target_dpi / current_dpi
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)
    return img
```

---

## 4. Tesseract MCP Server Design

### v3 implementation (shipped)

The research below informed the production server at [`mcp-servers/tesseract-mcp/`](../../mcp-servers/tesseract-mcp/). **7 tools** are registered in [`tesseract_mcp/tools.py`](../../mcp-servers/tesseract-mcp/src/tesseract_mcp/tools.py):

| Tool | Purpose |
|------|---------|
| `ocr_get_languages` | List installed language packs |
| `ocr_detect_document_type` | Classify PDF pages (text/scanned/mixed) |
| `ocr_extract_text` | OCR images and PDFs |
| `ocr_extract_hocr` | Structured HOCR with bounding boxes |
| `ocr_get_confidence` | Per-word confidence scores |
| `ocr_process_document` | Hybrid: native text + OCR for scanned pages |
| `ocr_preprocess_and_extract` | Preprocessing pipeline + OCR |

**Not implemented**: `ocr_extract_tables` (Section 4 prototype below) — Tesseract has no native table support; use cloud OCR or Docling for production tables.

Transport: **SSE on port 8003** via FastMCP. Container: `wikijs_tesseract_mcp`. Shared files via `shared_data:/data/shared:ro`.

### Design rationale (from research)

The production server implements 7 tools based on the research below. Key design choices:

- **FastMCP with SSE transport** — Standard MCP transport for Cursor/Claude integration
- **In-process pytesseract** — No MCP overhead for the Ingestion Pipeline; Tesseract MCP is for agent-facing ad-hoc OCR
- **Hybrid document processing** — `ocr_process_document` auto-detects text vs scanned pages, skipping OCR where native text exists
- **No table extraction** — Tesseract has no native table support. Use cloud OCR or IBM Docling for production table extraction
- **English + Italian** — Language packs pre-installed in Docker image (~300 MB total)

For the actual implementation code, see:
- [`mcp-servers/tesseract-mcp/src/tesseract_mcp/tools.py`](../../mcp-servers/tesseract-mcp/src/tesseract_mcp/tools.py)
- [`mcp-servers/tesseract-mcp/src/tesseract_mcp/detector.py`](../../mcp-servers/tesseract-mcp/src/tesseract_mcp/detector.py)
- [`mcp-servers/tesseract-mcp/src/tesseract_mcp/preprocess.py`](../../mcp-servers/tesseract-mcp/src/tesseract_mcp/preprocess.py)


## 5. Preprocessing Best Practices

### Complete Preprocessing Pipeline

```python
import cv2
import numpy as np
from PIL import Image
from typing import Optional

def preprocess_full(
    img: Image.Image,
    target_dpi: int = 300,
    deskew: bool = True,
    denoise: bool = True,
    threshold_method: str = "adaptive",
) -> Image.Image:
    """
    Full preprocessing pipeline for Tesseract OCR.
    Order matters: DPI → grayscale → deskew → denoise → threshold.
    """
    # 1. Convert to OpenCV format
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # 2. Upscale if low DPI (Tesseract wants ~300 DPI)
    cv_img = upscale_to_target(cv_img, target_dpi)

    # 3. Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    # 4. Deskew if text is rotated
    if deskew:
        gray = deskew_image(gray)

    # 5. Denoise (remove speckle noise)
    if denoise:
        gray = cv2.medianBlur(gray, 3)

    # 6. Binarize (threshold)
    if threshold_method == "otsu":
        # Best for even lighting
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif threshold_method == "adaptive":
        # Best for uneven lighting / shadows
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,  # Block size (odd)
            2    # Constant subtracted
        )
    elif threshold_method == "sauvola":
        # Best for documents — Tesseract 5.0+ has built-in Sauvola
        # Use via Tesseract config: --thresholding_method 1
        # No preprocessing needed — let Tesseract handle it
        return img  # Return original; Sauvola is applied internally
    else:
        # No thresholding — let Tesseract's internal Otsu handle it
        binary = gray

    return Image.fromarray(binary)


def deskew_image(image: np.ndarray) -> np.ndarray:
    """
    Correct rotation in a text image.
    Uses minAreaRect on non-zero pixels to find skew angle.
    """
    coords = np.column_stack(np.where(image > 0))

    if len(coords) == 0:
        return image  # No content to deskew

    angle = cv2.minAreaRect(coords)[-1]

    # Normalize angle
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    if abs(angle) < 0.5:
        return image  # Already straight enough

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def upscale_to_target(img: np.ndarray, target_dpi: int = 300, assumed_dpi: int = 72) -> np.ndarray:
    """Upscale image if it's below target DPI."""
    if assumed_dpi >= target_dpi:
        return img
    scale = target_dpi / assumed_dpi
    new_w = int(img.shape[1] * scale)
    new_h = int(img.shape[0] * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
```

### Preprocessing Decision Matrix

| Document Type | Grayscale | Deskew | Denoise | Threshold | PSM |
|---|---|---|---|---|---|
| **Clean scan, even lighting** | Yes | Yes | Optional | Otsu | 3 |
| **Clean scan, shadows** | Yes | Yes | Yes | Adaptive | 3 |
| **Phone photo of document** | Yes | Yes (critical) | Yes | Adaptive | 6 |
| **Multi-column layout** | Yes | Yes | Yes | Otsu | 4 or 6 |
| **Receipt / sparse text** | Yes | Yes | Yes | Adaptive | 11 |
| **Low DPI (<150)** | **Upscale first** | Yes | Yes | Otsu | 3 |
| **Tesseract 5+ clean docs** | No* | No* | No* | No (let Sauvola handle it) | 3 |

\* Tesseract 5.0+ has built-in Sauvola binarization (`-c thresholding_method=1`). For clean documents, you may not need external preprocessing at all. Test both paths.

### Tesseract 5's Internal Binarization Methods

```bash
# List available thresholding parameters
tesseract --print-parameters | grep thresholding

# Use Sauvola (better for documents)
tesseract input.png output -c thresholding_method=1

# Use Adaptive Otsu
tesseract input.png output -c thresholding_method=2
```

### Quick Preprocessing Helper

```python
def quick_preprocess(img: Image.Image) -> Image.Image:
    """
    Minimal-but-effective preprocessing: grayscale + Otsu.
    Works for 80% of clean scanned documents.
    """
    import cv2, numpy as np
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binary)
```

---

## 6. Standalone MCP Server vs Embedded in Ingestion Pipeline

The user wants "tesseract mcp containerizzato" — a separate MCP server. Let's analyze both approaches.

### Architecture Options

#### Option A: Standalone Tesseract MCP Server (Recommended)

```
┌──────────────┐     MCP (stdio/HTTP)     ┌──────────────────┐
│  Ingestion   │ ──────────────────────── │  Tesseract MCP   │
│  Pipeline    │                          │  Server          │
│  (wiki-js)   │                          │  (Dockerized)    │
└──────────────┘                          └──────────────────┘
```

**Pros:**
- **Separation of concerns:** OCR is an independent service. Pipeline doesn't need OCR dependencies.
- **Independent scaling:** Scale OCR workers independently (0 when idle, 10 during bulk import).
- **MCP-native:** LLM can discover and invoke OCR tools directly via any MCP client.
- **Language-agnostic:** Any service in any language can call OCR via MCP protocol.
- **Security isolation:** OCR processes (handling untrusted PDFs) are sandboxed.
- **Reproducibility:** Docker image with pinned Tesseract version — no environment drift.
- **Reusability:** Same OCR server serves ingestion pipeline AND any MCP-aware AI agent.

**Cons:**
- ~30ms overhead per image (Docker overlay filesystem + MCP serialization)
- Network hop for each OCR call
- Requires the MCP server to be running for OCR to work
- More complex deployment (two containers instead of one)

#### Option B: Embed pytesseract in Ingestion Pipeline

```
┌──────────────────────────────────────┐
│  Ingestion Pipeline (wiki-js)        │
│  ┌─────────────────────────────────┐ │
│  │  pytesseract + PyMuPDF          │ │
│  │  (direct py bindings)           │ │
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘
```

**Pros:**
- **Zero latency overhead:** Direct Python calls, no serialization.
- **Simpler deployment:** One Docker image, one process.
- **Simpler development:** No MCP protocol to implement/debug.
- **Batch throughput:** Can parallelize with Python multiprocessing/threading within one process.

**Cons:**
- **No LLM tool discovery:** The AI agent can't independently invoke OCR — the pipeline must orchestrate it.
- **Tight coupling:** OCR dependency is baked into the pipeline. Upgrading Tesseract means rebuilding the pipeline.
- **No independent scaling:** OCR shares CPU with the pipeline. A large OCR job slows down ingestion.
- **No reuse by other services:** If you later need OCR for a different service, you're duplicating.

### Recommendation: Hybrid Architecture

**Deploy a standalone Tesseract MCP server for AI-agent-driven OCR** AND **give the ingestion pipeline direct pytesseract access for batch performance.**

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌──────────────────┐     MCP (HTTP)     ┌──────────────────┐  │
│  │  Tesseract MCP   │ ◄───────────────► │  AI Agent        │  │
│  │  Server          │                   │  (Cursor/Claude) │  │
│  │  (Docker, :8000) │                   └──────────────────┘  │
│  └────────┬─────────┘                                          │
│           │ MCP (HTTP)                                          │
│  ┌────────▼─────────┐                                          │
│  │  Ingestion       │  ← Also has direct pytesseract           │
│  │  Pipeline        │    access for batch processing           │
│  │  (wiki-js)       │                                          │
│  └──────────────────┘                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation approach:**

1. **Build the Tesseract MCP server image** (Section 1's Dockerfile).
2. **In the MCP server**, expose tools as designed above — this is the "AI-facing" OCR.
3. **In the ingestion pipeline's Docker image**, install Tesseract + pytesseract as well (same binary in both). The pipeline uses direct pytesseract for batch operations (e.g., importing 1000 PDFs) for maximum throughput with no MCP overhead.
4. **The pipeline also acts as an MCP client** — for one-off, AI-driven OCR requests (e.g., "OCR this specific page"), it calls the Tesseract MCP server instead of duplicating the orchestration logic.

This way:
- **Batch performance:** Direct pytesseract in the pipeline, no overhead, parallel processing.
- **AI tool access:** MCP server enables LLM-driven OCR workflows.
- **Single Tesseract version:** Both images use the same version, trained data, and preprocessing logic.
- **Best of both worlds:** No compromise on batch throughput or AI integration.

### Docker Compose Example (v3)

From [`docker-compose.yml`](../../docker-compose.yml):

```yaml
  tesseract-mcp:
    build:
      context: ./mcp-servers/tesseract-mcp
    image: wiki-js-tesseract-mcp:latest
    container_name: wikijs_tesseract_mcp
    ports:
      - "${TESSERACT_MCP_PORT:-8003}:8003"
    environment:
      MCP_HOST: 0.0.0.0
      MCP_PORT: 8003
      TESSDATA_PREFIX: /usr/share/tesseract-ocr/5/tessdata
    volumes:
      - shared_data:/data/shared:ro
    networks:
      - wikijs-net

  ingestion-pipeline:
    build:
      context: ./mcp-servers/ingestion-pipeline
    # Uses pytesseract in-process for batch OCR (no MCP overhead)
    volumes:
      - shared_data:/data/shared:ro
    depends_on:
      qdrant-db:
        condition: service_healthy
```

Cursor MCP config: `"tesseract": { "url": "http://localhost:8003/sse" }`. See [Multi-MCP Setup](multi-mcp-setup.md).

---

## Summary Benchmarks & Key Numbers

| Metric | Tesseract (this design) | PaddleOCR | Winner |
|---|---|---|---|
| Docker image size | ~270–300 MB | ~1,200 MB | **Tesseract (4x smaller)** |
| Cold start | <0.3s | 4.2s | **Tesseract (14x faster)** |
| Per-page CPU (clean) | ~600ms | ~4,850ms | **Tesseract (8x faster)** |
| Accuracy clean docs | CER 0.02 | CER 0.01 | Tie (both excellent) |
| Accuracy complex docs | CER 0.18 | CER 0.10 | **PaddleOCR (1.8x better)** |
| Table extraction | Manual clustering | Manual clustering | Tie (neither native) |
| Language coverage | 100+ | 80+ | **Tesseract** |
| English+Italian | Native support | Native support | Tie |
| Operational burden | Very low | Medium (torch, Paddle dep) | **Tesseract** |

**For a wiki ingestion pipeline at moderate scale (<100K pages/month):**
- Tesseract's cold-start speed and small footprint are decisive advantages.
- The accuracy gap on clean scanned documents is negligible.
- For the minority of complex/low-quality documents, confidence-based routing can flag them for manual review or a fallback cloud OCR API.
- The hybrid architecture preserves batch throughput while enabling MCP-native AI tool access.

---

## References

- [Tesseract Docker setup (Markaicode)](https://markaicode.com/integrate/tesseract-with-docker/)
- [PaddleOCR vs Tesseract benchmark (CodeSOTA)](https://www.codesota.com/ocr/paddleocr-vs-tesseract)
- [PaddleOCR vs EasyOCR vs Tesseract (TildAlice)](https://tildalice.io/ocr-tesseract-easyocr-paddleocr-benchmark/)
- [PyMuPDF text extraction docs](https://pymupdf.readthedocs.io/)
- [Tesseract ImproveQuality guide](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)
- [PyImageSearch multi-column table OCR](https://pyimagesearch.com/2022/02/28/multi-column-table-ocr/)
- [Building MCP OCR server (Upadhyay)](https://atalupadhyay.wordpress.com/2026/02/24/building-a-production-grade-mcp-ocr-server-from-scratch/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Tesseract Kubernetes stack](https://markaicode.com/stack/tesseract-docker-stack/)
