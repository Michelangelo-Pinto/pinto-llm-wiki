# Document Ingestion Pipeline — Deterministic Design

> **Status**: Design phase
> **Target**: Add external document (PDF, DOCX, images, text) parsing + chunking + vector embedding as new MCP tools within the existing wiki-js-mcp server.

---

## 0. Architecture Decision: CLI Tool vs New MCP Server vs Integrated Module

**Decision: Integrated Python package within the existing MCP server, exposed as new MCP tools.**

Rationale:
- The existing MCP server already runs sentence-transformers, SQLite, and vector search. No new runtime needed.
- MCP tools follow the project's existing pattern (`@mcp.tool()` async functions returning `json.dumps(...)`)
- The LLM Wiki pattern explicitly separates **Raw Sources** (human-only) from **The Wiki** (LLM-owned). External documents are raw sources — the pipeline parses them into searchable chunks, and the existing LLM Ingest workflow decides how to organize content into wiki pages.
- A separate service would add deployment complexity (another container, another process, inter-service auth) for no benefit at this scale (~200–5000 pages).

```
                         ┌─────────────────────────────────────┐
                         │         Existing MCP Server          │
                         │  (FastMCP, SSE :8000, stdio)        │
                         │                                     │
  LLM Agent ──tool call──▶  wikijs_ingest_file(path)          │
                         │  wikijs_ingest_directory(path)      │
                         │  wikijs_search_chunks(query)        │
                         │  wikijs_search_across_all(query)    │
                         │  wikijs_get_ingestion_status(...)   │
                         │  wikijs_delete_ingested_document(id)│
                         │                                     │
                         │  ┌──────────────────────────────┐   │
                         │  │  ingestion/ package (NEW)    │   │
                         │  │  ├── detector.py             │   │
                         │  │  ├── parsers/                │   │
                         │  │  │   ├── pdf.py              │   │
                         │  │  │   ├── docx.py             │   │
                         │  │  │   ├── text.py             │   │
                         │  │  │   └── image_ocr.py        │   │
                         │  │  ├── chunker.py              │   │
                         │  │  └── orchestrator.py         │   │
                         │  └──────────────────────────────┘   │
                         │                                     │
                         │  SQLite: ingestion tables (NEW)      │
                         │  ┌──────────────────────────────┐   │
                         │  │  ingested_documents           │   │
                         │  │  document_chunks (w/ vectors) │   │
                         │  │  page_chunk_references        │   │
                         │  └──────────────────────────────┘   │
                         └─────────────────────────────────────┘
```

---

## 1. File Type Detection

### Algorithm (`detector.py`)

```python
import mimetypes
from pathlib import Path
import fitz  # PyMuPDF
from docx import Document as DocxDocument

def detect_file_type(filepath: str) -> dict:
    """
    Returns:
        {
            "type": FileType enum,
            "mime": str,
            "has_embedded_images": bool | None,  # None if N/A
            "page_count": int | None,
            "confidence": float,  # 0.0–1.0
        }
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    # --- MIME detection (broad categorization) ---
    mime_type = mimetypes.guess_type(filepath)[0]

    # --- Extension + MIME routing ---
    if ext == '.pdf' or mime_type == 'application/pdf':
        return _detect_pdf_type(filepath)

    elif ext == '.docx' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        return _detect_docx_type(filepath)

    elif ext in ('.md', '.markdown', '.txt', '.rst', '.org'):
        return _detect_text_type(filepath)

    elif ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp'):
        return { "type": FileType.IMAGE, "mime": mime_type, ... }

    raise UnsupportedFileType(f"No handler for {ext}")


def _detect_pdf_type(filepath: str) -> dict:
    """
    Heuristic: open with PyMuPDF, sample first 5 pages.
    If average text length per page < ~50 chars → scanned PDF → needs OCR.
    If > 50 chars → text-based PDF → extract with PyMuPDF.
    """
    doc = fitz.open(filepath)
    page_count = len(doc)

    if page_count == 0:
        raise EmptyDocumentError("PDF has zero pages")

    sample_pages = min(5, page_count)
    total_chars = 0

    for i in range(sample_pages):
        text = doc[i].get_text()
        total_chars += len(text.strip())

    avg_chars = total_chars / sample_pages

    if avg_chars < 50:
        return {
            "type": FileType.SCANNED_PDF,
            "mime": "application/pdf",
            "has_embedded_images": True,
            "page_count": page_count,
            "confidence": 0.9,
        }
    else:
        return {
            "type": FileType.TEXT_PDF,
            "mime": "application/pdf",
            "has_embedded_images": None,  # Could check for embedded images separately
            "page_count": page_count,
            "confidence": 0.85,
        }
```

### Why Python `mimetypes` + PyMuPDF sampling
- `python-magic` (libmagic) adds a C dependency. Our file set is limited to ~7 known types — extension + MIME is sufficient.
- PDF detection via PyMuPDF text sampling is fast (reads metadata, not full pages) and deterministic.
- DOCX detection can be done by trying `python-docx.Document()`, which fails fast on non-DOCX.

---

## 2. Document Processing — Per-Type Parsers

### 2.1 Text PDF → PyMuPDF (`parsers/pdf.py`)

**Library**: PyMuPDF (`fitz`)

**Why**: Benchmarks from DocLayNet (2024) show PyMuPDF achieves 0.9825 F1 on Financial documents vs pdfplumber's 0.9568. PyMuPDF is 8–12x faster for plain text extraction (~180 pages/sec vs ~18 pages/sec).

```python
def parse_text_pdf(filepath: str) -> list[dict]:
    """
    Extract text page-by-page from a text-based PDF.

    Returns:
        [
            {
                "page_number": 1,
                "text": "full page text content...",
                "char_count": 2341,
                "metadata": { "width_pt": 612, "height_pt": 792 }
            },
            ...
        ]
    """
    doc = fitz.open(filepath)
    pages = []

    for i, page in enumerate(doc):
        text = page.get_text(sort=True)  # sort=True preserves reading order
        if text.strip():
            pages.append({
                "page_number": i + 1,
                "text": text,
                "char_count": len(text),
                "metadata": {
                    "width_pt": page.rect.width,
                    "height_pt": page.rect.height,
                }
            })

    doc.close()
    return pages
```

### 2.2 Scanned/Image-Based PDF → PaddleOCR (`parsers/image_ocr.py`)

**Library**: PaddleOCR (v2.x, CPU mode)

**Why PaddleOCR over Tesseract**: In 2025–2026 benchmarks, PaddleOCR achieves 0 character errors on clean documents (Tesseract: 3 errors), ~92–95% overall accuracy (Tesseract: 85–90%), and better handling of multi-oriented text. On CPU, PaddleOCR processes ~2–5 seconds per page — acceptable for batch ingestion. Tesseract is faster but significantly less accurate on anything beyond clean printed text.

```python
from paddleocr import PaddleOCR

# Singleton OCR engine — lazy initialized, reused across calls
_ocr_engine: PaddleOCR | None = None

def _get_ocr_engine() -> PaddleOCR:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,   # Detect and correct text orientation
            lang='en',            # Default; switch based on document metadata
            use_gpu=False,        # CPU-only for simplicity
            show_log=False,       # Suppress verbose output
        )
    return _ocr_engine


def parse_scanned_pdf(filepath: str) -> list[dict]:
    """
    Render each page as an image (300 DPI), then OCR with PaddleOCR.

    Returns same structure as parse_text_pdf.
    """
    doc = fitz.open(filepath)
    ocr = _get_ocr_engine()
    pages = []

    for i, page in enumerate(doc):
        # Render page at 300 DPI
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")

        # OCR the rendered image
        result = ocr.ocr(img_bytes, cls=True)

        if result and result[0]:
            text = "\n".join(
                line[1][0] for line in result[0]
            )
        else:
            text = ""

        pages.append({
            "page_number": i + 1,
            "text": text,
            "char_count": len(text),
            "metadata": {
                "width_pt": page.rect.width,
                "height_pt": page.rect.height,
                "ocr_engine": "paddleocr",
                "dpi": 300,
            }
        })

    doc.close()
    return pages
```

### 2.3 DOCX → python-docx + Image Detection (`parsers/docx.py`)

**Library**: `python-docx` for text, `docx.opc.constants.RELATIONSHIP_TYPE.IMAGE` for image detection.

**DOCX with embedded images**: Images are extracted via `doc.part.rels`, OCR'd with PaddleOCR, and the OCR text is inserted inline at the image's position (preserving document flow). This avoids needing an LLM Vision API and keeps the pipeline self-contained.

```python
from docx import Document as DocxDocument
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from PIL import Image
import io

def parse_docx(filepath: str) -> list[dict]:
    """
    Extract text from DOCX. Detect embedded images. If images present,
    OCR them and insert OCR text at image position.

    Returns same page list structure (DOCX has no pages, so we return
    one logical "page" with all content).
    """
    doc = DocxDocument(filepath)
    has_images = _docx_has_images(doc)
    all_text_parts = []
    image_count = 0

    for paragraph in doc.paragraphs:
        # Check if paragraph contains images via inline shapes
        images_in_para = _extract_images_from_paragraph(doc, paragraph)

        for img_data in images_in_para:
            ocr_text = _ocr_image_bytes(img_data['bytes'])
            all_text_parts.append(f"\n[Image OCR]: {ocr_text}\n")
            image_count += 1

        if paragraph.text.strip():
            all_text_parts.append(paragraph.text)

    # Also check document-level images (e.g., floating images)
    # DOCX stores images in relationships; python-docx surfaces them in paragraphs

    full_text = "\n\n".join(all_text_parts)

    return [{
        "page_number": 1,
        "text": full_text,
        "char_count": len(full_text),
        "metadata": {
            "has_images": has_images,
            "image_count": image_count,
            "paragraph_count": len(doc.paragraphs),
        }
    }]


def _docx_has_images(doc: DocxDocument) -> bool:
    """Check if DOCX contains any embedded images."""
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            return True
    return False


def _extract_images_from_paragraph(doc: DocxDocument, paragraph) -> list[dict]:
    """Extract image bytes from runs' inline shapes within a paragraph."""
    images = []
    for run in paragraph.runs:
        # Inline shapes (w:drawing elements)
        for shape in run._r.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
            blip = shape.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
            if blip is not None:
                embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if embed:
                    image_part = doc.part.related_parts[embed]
                    images.append({
                        'bytes': image_part.blob,
                        'content_type': image_part.content_type,
                    })
    return images


def _ocr_image_bytes(img_bytes: bytes) -> str:
    """Run PaddleOCR on raw image bytes."""
    from PIL import Image
    import numpy as np

    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img_array = np.array(img)

    ocr = _get_ocr_engine()
    result = ocr.ocr(img_array, cls=True)

    if result and result[0]:
        return " ".join(line[1][0] for line in result[0])
    return ""
```

**Note on alternative approach**: Microsoft's `markitdown` (with `markitdown-ocr` plugin) handles DOCX image extraction + OCR via LLM Vision API. For a deterministic, self-contained pipeline, the manual `python-docx` + PaddleOCR approach above is preferred. If an LLM Vision endpoint is configured later, it can be swapped in as the OCR backend.

### 2.4 Markdown / Plain Text → Direct (`parsers/text.py`)

```python
def parse_text_file(filepath: str) -> list[dict]:
    """
    Read .md, .txt, .rst, .org files directly.
    No transformation — raw text preserved.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    return [{
        "page_number": 1,
        "text": content,
        "char_count": len(content),
        "metadata": {
            "extension": Path(filepath).suffix,
        }
    }]
```

### 2.5 Standalone Images → PaddleOCR

```python
def parse_image_file(filepath: str) -> list[dict]:
    """
    OCR a standalone image file (PNG, JPG, etc.)
    """
    from PIL import Image
    import numpy as np

    img = Image.open(filepath).convert("RGB")
    img_array = np.array(img)

    ocr = _get_ocr_engine()
    result = ocr.ocr(img_array, cls=True)

    text = ""
    if result and result[0]:
        text = " ".join(line[1][0] for line in result[0])

    return [{
        "page_number": 1,
        "text": text,
        "char_count": len(text),
        "metadata": {
            "format": str(img.format),
            "size": img.size,
        }
    }]
```

### Parser Registry Pattern

```python
from enum import Enum
from typing import Callable

class FileType(Enum):
    TEXT_PDF = "text_pdf"
    SCANNED_PDF = "scanned_pdf"
    DOCX = "docx"
    DOCX_WITH_IMAGES = "docx_with_images"
    MARKDOWN = "markdown"
    TEXT = "text"
    IMAGE = "image"


PARSER_REGISTRY: dict[FileType, Callable] = {
    FileType.TEXT_PDF: parse_text_pdf,
    FileType.SCANNED_PDF: parse_scanned_pdf,
    FileType.DOCX: parse_docx,
    FileType.DOCX_WITH_IMAGES: parse_docx,  # Same parser, images auto-detected
    FileType.MARKDOWN: parse_text_file,
    FileType.TEXT: parse_text_file,
    FileType.IMAGE: parse_image_file,
}
```

---

## 3. Chunking Strategy

### Recommendation: Two-Phase Recursive Chunking (Hybrid)

Based on research:

| Strategy | Recall | Cost | Best For |
|----------|--------|------|----------|
| Fixed-size (400–512 tokens) | 85–90% | Low | General text |
| Semantic (sentence embedding similarity) | 91–92% | High (embed every sentence) | Premium accuracy |
| Page-level (NVIDIA 2024 winner) | 92% on PDFs | Low | Paginated docs |
| Recursive Semantic (RSC) | Best balance | Medium | Mixed content |

**Our approach**: **Section-aware recursive chunking** — a hybrid that uses markdown headings (for .md files) or page boundaries (for PDFs) as primary split points, then recursively splits oversized sections using character boundaries (paragraph → sentence). This gives us the structural awareness of semantic chunking without embedding every sentence.

```python
import hashlib
from dataclasses import dataclass, field

CHUNK_SIZE_CHARS = 1500       # ~500 tokens for English (1 token ≈ 3 chars)
CHUNK_OVERLAP_CHARS = 200     # ~15% overlap
MAX_CHUNK_SIZE_CHARS = 2500   # Hard cap — split if exceeded


@dataclass
class Chunk:
    content: str
    chunk_index: int
    page_number: int | None          # PDF pages
    section_heading: str | None       # Markdown headings or detected section
    start_char: int                   # Position in original text
    end_char: int
    content_hash: str                 # SHA-256 of content
    token_count: int                  # Estimated token count


def chunk_document(pages: list[dict], file_type: FileType) -> list[Chunk]:
    """
    Phase 1: Split by structural boundaries
      - PDF: page boundaries (each page = initial chunk)
      - Markdown: heading boundaries (### sections)
      - DOCX: paragraph boundaries (group consecutive paragraphs)
      - Text: paragraph boundaries (double-newline splits)

    Phase 2: For each initial chunk > CHUNK_SIZE_CHARS:
      - Split recursively by:
        1. Sentence boundaries (`. `, `! `, `? `, `.\n`)
        2. Word boundaries (spaces) as last resort
      - Add overlap between consecutive sub-chunks

    Phase 3: Post-process
      - Merge very short chunks (< 100 chars) with neighbors
      - Strip leading/trailing whitespace
      - Compute content hash
    """
    all_chunks = []

    if file_type in (FileType.TEXT_PDF, FileType.SCANNED_PDF):
        # Phase 1: Each page is an initial chunk
        for page in pages:
            initial_chunks = _split_page_by_paragraph_gaps(page)
            for ic in initial_chunks:
                sub_chunks = _recursive_split(ic["text"], CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)
                for sc in sub_chunks:
                    all_chunks.append(Chunk(
                        content=sc["text"],
                        chunk_index=len(all_chunks),
                        page_number=page["page_number"],
                        section_heading=_detect_section_heading(sc["text"]),
                        start_char=sc["start"],
                        end_char=sc["end"],
                        content_hash=hashlib.sha256(sc["text"].encode()).hexdigest(),
                        token_count=_estimate_tokens(sc["text"]),
                    ))

    elif file_type in (FileType.MARKDOWN, FileType.TEXT):
        # Phase 1: Split by headings or double-newlines
        full_text = pages[0]["text"]
        sections = _split_by_headings(full_text) if file_type == FileType.MARKDOWN else _split_by_paragraphs(full_text)

        for section in sections:
            sub_chunks = _recursive_split(section["text"], CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)
            for sc in sub_chunks:
                all_chunks.append(Chunk(
                    content=sc["text"],
                    chunk_index=len(all_chunks),
                    page_number=None,
                    section_heading=section.get("heading"),
                    start_char=sc["start"],
                    end_char=sc["end"],
                    content_hash=hashlib.sha256(sc["text"].encode()).hexdigest(),
                    token_count=_estimate_tokens(sc["text"]),
                ))

    elif file_type in (FileType.DOCX, FileType.DOCX_WITH_IMAGES, FileType.IMAGE):
        # Phase 1: Paragraphs as initial chunks
        full_text = pages[0]["text"]
        paragraphs = _split_by_paragraphs(full_text)

        for para in paragraphs:
            sub_chunks = _recursive_split(para["text"], CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)
            for sc in sub_chunks:
                all_chunks.append(Chunk(
                    content=sc["text"],
                    chunk_index=len(all_chunks),
                    page_number=None,
                    section_heading=None,
                    start_char=sc["start"],
                    end_char=sc["end"],
                    content_hash=hashlib.sha256(sc["text"].encode()).hexdigest(),
                    token_count=_estimate_tokens(sc["text"]),
                ))

    # Phase 3: Merge short chunks
    all_chunks = _merge_short_chunks(all_chunks, min_chars=100)

    # Re-index after merges
    for i, chunk in enumerate(all_chunks):
        chunk.chunk_index = i

    return all_chunks


def _recursive_split(text: str, target_size: int, overlap: int) -> list[dict]:
    """
    Recursively split text into chunks of approximately target_size chars.

    Split priority:
    1. Sentence boundaries (. ! ? followed by space or newline) — best semantic unit
    2. Clause boundaries (, ; : followed by space) — fallback
    3. Word boundaries (spaces) — last resort

    Each consecutive chunk shares `overlap` characters with the previous one.
    """
    if len(text) <= target_size:
        return [{"text": text, "start": 0, "end": len(text)}]

    # Find best split point within ±20% of target_size
    ideal = target_size
    lower = int(target_size * 0.8)
    upper = int(target_size * 0.95)

    split_point = _find_best_split(text, ideal, lower, upper)

    if split_point is None:
        # Can't find a good split — force split at target_size
        split_point = target_size

    first_chunk = text[:split_point]
    # Overlap: the next chunk starts `overlap` chars before this split
    remainder_start = max(0, split_point - overlap)
    remainder = text[remainder_start:]

    results = [{"text": first_chunk, "start": 0, "end": split_point}]
    results.extend(_recursive_split(remainder, target_size, overlap))

    # Adjust start/end for overlap offset
    offset = split_point - overlap
    for i, r in enumerate(results):
        if i > 0:
            r["start"] += offset
            r["end"] += offset

    return results


def _find_best_split(text: str, ideal: int, lower: int, upper: int) -> int | None:
    """Find the best sentence/clause/word boundary within [lower, upper]."""
    # Priority 1: Sentence boundary
    for pattern in ['. ', '.\n', '! ', '?\n', '? ']:
        pos = text.rfind(pattern, lower, min(upper + len(pattern), len(text)))
        if pos != -1:
            return pos + len(pattern.strip())

    # Priority 2: Clause boundary
    for pattern in [', ', '; ', ': ']:
        pos = text.rfind(pattern, lower, upper)
        if pos != -1:
            return pos + 1

    # Priority 3: Word boundary
    pos = text.rfind(' ', lower, upper)
    if pos != -1:
        return pos

    return None  # force split
```

### Why This Strategy

1. **Page boundaries for PDFs**: NVIDIA's 2024 benchmarks showed page-level chunking wins for PDFs (0.648 accuracy, lowest variance) because pages are natural semantic units. We further split oversized pages recursively.

2. **Heading boundaries for Markdown**: Headings are the most reliable structural signal in wiki-style content. A chunk that starts at a heading and contains its subsection content is self-contained and useful.

3. **Recursive sentence splitting for overflow**: When a section/page exceeds the target size, splitting at sentence boundaries preserves meaning better than character-level splits. Overlap ensures no content is lost at boundaries.

4. **1500 chars (~500 tokens)**: Research consensus across Firecrawl, Chroma, and Onsomble is that 400–512 tokens is the optimal range for mixed queries. 500 tokens balances factoid queries (favor smaller chunks) and analytical queries (favor larger chunks).

5. **200 char overlap (~15%)**: Standard practice — prevents sentences from being orphaned at chunk boundaries. "For more details, see" in one chunk connects to content in the next.

6. **Cost-effectiveness**: The NAACL 2025 paper "Is Semantic Chunking Worth the Computational Cost?" concluded: *"Just use fixed-size chunking in practice."* Semantic chunking (embedding every sentence) gives 2–3% improvement at the cost of embedding your entire document twice. For a wiki of 200–5000 pages, the simpler approach is more than sufficient.

---

## 4. Metadata Preservation per Chunk

Each chunk carries the following metadata, stored in `document_chunks.metadata_json`:

```python
@dataclass
class ChunkMetadata:
    # --- Source identity ---
    source_path: str                # Original file path
    source_filename: str            # Filename without path
    source_content_hash: str        # SHA-256 of the original file
    file_type: str                  # text_pdf, scanned_pdf, docx, etc.

    # --- Position ---
    page_number: int | None         # 1-indexed, PDFs only
    chunk_index: int                # 0-indexed within document
    total_chunks: int               # Total chunks in this document
    start_char: int                 # Byte offset in original text
    end_char: int                   # Byte offset in original text

    # --- Structure ---
    section_heading: str | None     # Nearest heading above this chunk
    section_path: list[str]         # Heading breadcrumb: ["## API", "### Auth"]

    # --- Content ---
    content_hash: str               # SHA-256 of chunk content (dedup key)
    char_count: int                 # Number of characters
    token_count: int                # Estimated token count (chars / 3)

    # --- Ingestion ---
    ingested_at: str                # ISO 8601 timestamp
    ingestion_id: str               # UUID of the ingestion run
    parser_version: str             # Version of parser used
    ocr_engine: str | None          # paddleocr / tesseract / None
    ocr_confidence: float | None    # Average OCR confidence if applicable
```
This metadata enables:
- **Source attribution**: Every search result cites its origin document and page
- **Deduplication**: Content hash prevents re-ingesting identical content
- **Reprocessing**: If a parser version changes, chunks with old parser_version can be re-ingested
- **Navigation**: Section path enables "show me everything in section X"

---

## 5. Pipeline Architecture — Detailed

### 5.1 Data Flow

```
  Input file
      │
      ▼
  ┌──────────────┐
  │  detector.py  │  → FileType, page_count, has_images
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  parsers/*.py │  → list of {page_number, text, metadata}
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  chunker.py   │  → list of Chunk objects
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐         ┌──────────────────────┐
  │  embedder.py  │ ───────▶│  document_chunks     │
  │  (reuse       │  insert │  table with vectors   │
  │   MiniLM)     │         └──────────────────────┘
  └──────────────┘
         │
         ▼
  ┌──────────────┐
  │  ingested_    │  Status: completed / partial / failed
  │  documents    │
  └──────────────┘
```

### 5.2 SQLite Schema (add to `db.py`)

```python
class IngestedDocument(Base):
    __tablename__ = "ingested_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_path = Column(String, nullable=False)
    content_hash = Column(String, nullable=False, unique=True, index=True)
    file_type = Column(String, nullable=False)
    original_filename = Column(String)
    file_size_bytes = Column(Integer)
    page_count = Column(Integer, default=0)
    image_count = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending/processing/completed/failed/partial
    error_message = Column(Text)
    metadata_json = Column(Text, default="{}")
    ingestion_id = Column(String, index=True)   # UUID for grouping batch runs
    parser_version = Column(String, default="1.0.0")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("ingested_documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False, unique=True, index=True)
    token_count = Column(Integer)
    metadata_json = Column(Text, default="{}")
    embedding_json = Column(Text)  # JSON array of 384 floats
    embedding_model = Column(String, default="all-MiniLM-L6-v2")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class PageChunkReference(Base):
    __tablename__ = "page_chunk_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(Integer, nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("page_id", "chunk_id", name="uq_page_chunk"),
    )
```

### 5.3 Orchestrator (`orchestrator.py`)

```python
import uuid
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

async def ingest_file(
    filepath: str,
    force: bool = False,
    dry_run: bool = False,
    db = Depends(get_db),
) -> dict:
    """
    Full ingestion pipeline for a single file.

    Steps:
    1. Compute content hash → check for duplicate
    2. Detect file type
    3. Parse document into pages
    4. Chunk pages
    5. Embed chunks
    6. Store in SQLite
    7. Return status
    """
    ingestion_id = str(uuid.uuid4())

    # --- Step 1: Content hash + dedup ---
    content_hash = _compute_file_hash(filepath)

    existing = db.query(IngestedDocument).filter_by(
        content_hash=content_hash
    ).first()

    if existing and not force:
        # Check if all chunks still exist
        chunk_count = db.query(DocumentChunk).filter_by(
            document_id=existing.id
        ).count()

        return {
            "status": "already_ingested",
            "document_id": existing.id,
            "content_hash": content_hash,
            "chunk_count": chunk_count,
            "ingested_at": existing.created_at.isoformat(),
            "message": "Use force=True to re-ingest"
        }

    if existing and force:
        # Delete existing chunks + document record
        db.query(DocumentChunk).filter_by(document_id=existing.id).delete()
        db.delete(existing)
        db.commit()

    # --- Step 2: Detect file type ---
    try:
        file_info = detect_file_type(filepath)
    except UnsupportedFileType as e:
        return {"status": "error", "error": str(e)}

    # --- Step 3: Parse document ---
    status = "pending"
    doc_record = IngestedDocument(
        source_path=filepath,
        content_hash=content_hash,
        file_type=file_info["type"].value,
        original_filename=Path(filepath).name,
        file_size_bytes=Path(filepath).stat().st_size,
        page_count=file_info.get("page_count", 0),
        image_count=0,
        status="processing",
        metadata_json=json.dumps({"detection_confidence": file_info["confidence"]}),
        ingestion_id=ingestion_id,
        parser_version="1.0.0",
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    try:
        pages = _parse_with_retry(filepath, file_info["type"])
    except Exception as e:
        doc_record.status = "failed"
        doc_record.error_message = str(e)
        db.commit()
        return {"status": "failed", "document_id": doc_record.id, "error": str(e)}

    # --- Step 4: Chunk ---
    chunks = chunk_document(pages, file_info["type"])

    # --- Step 5: Embed ---
    embedding_model = _get_model()  # Reuse existing MiniLM singleton

    for chunk in chunks:
        embedding = embedding_model.encode(chunk.content)
        embedding_json = json.dumps(embedding.tolist())

        total = len(chunks)
        metadata = {
            "source_path": filepath,
            "source_filename": Path(filepath).name,
            "source_content_hash": content_hash,
            "file_type": file_info["type"].value,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "total_chunks": total,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "section_heading": chunk.section_heading,
            "char_count": len(chunk.content),
            "token_count": chunk.token_count,
            "ingested_at": datetime.datetime.utcnow().isoformat(),
            "ingestion_id": ingestion_id,
            "parser_version": "1.0.0",
            "ocr_engine": ("paddleocr" if file_info["type"] in (FileType.SCANNED_PDF, FileType.IMAGE) else None),
        }

        db.add(DocumentChunk(
            document_id=doc_record.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            content_hash=chunk.content_hash,
            token_count=chunk.token_count,
            metadata_json=json.dumps(metadata),
            embedding_json=embedding_json,
            embedding_model="all-MiniLM-L6-v2",
        ))

    # --- Step 6: Finalize ---
    status = "completed"
    doc_record.status = status
    doc_record.image_count = sum(
        1 for p in pages if p["metadata"].get("ocr_engine")
    )
    db.commit()

    return {
        "status": status,
        "document_id": doc_record.id,
        "file_type": file_info["type"].value,
        "page_count": file_info.get("page_count", 1),
        "chunk_count": len(chunks),
        "content_hash": content_hash,
        "ingestion_id": ingestion_id,
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _parse_with_retry(filepath: str, file_type: FileType) -> list[dict]:
    """Parse with tenacity retries for transient errors (e.g., file lock)."""
    parser = PARSER_REGISTRY[file_type]
    return parser(filepath)
```

### 5.4 New MCP Tools

All tools follow the existing pattern:

```python
# In tools_ingestion.py

from wiki_mcp_server.server import mcp
from wiki_mcp_server.ingestion.orchestrator import ingest_file, ingest_directory

@mcp.tool()
async def wikijs_ingest_file(source_path: str, force: bool = False) -> str:
    """
    Ingest a single document file (PDF, DOCX, image, text, markdown).

    Detects file type, extracts text (with OCR if needed), chunks, embeds,
    and stores in the local document chunk index.

    Returns JSON with status, document_id, chunk_count, file_type.
    """
    try:
        db = get_db()
        result = await ingest_file(source_path, force=force, db=db)
        logger.info(f"ingest_file completed: {result['status']} for {source_path}")
        return json.dumps(result)
    except Exception as e:
        error_msg = f"Failed to ingest file: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_ingest_directory(
    directory_path: str,
    recursive: bool = True,
    force: bool = False
) -> str:
    """
    Ingest all supported files in a directory.

    Returns summary with per-file status, total files processed, failures.
    """
    try:
        db = get_db()
        results = await ingest_directory(directory_path, recursive=recursive, force=force, db=db)

        summary = {
            "total_discovered": results["total_discovered"],
            "ingested": results["ingested"],
            "skipped_duplicates": results["skipped_duplicates"],
            "failed": results["failed"],
            "errors": results["errors"],
        }
        return json.dumps(summary)
    except Exception as e:
        error_msg = f"Failed to ingest directory: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_search_chunks(query: str, limit: int = 10) -> str:
    """
    Vector search across ingested document chunks (NOT wiki pages).

    Returns chunks with source file, page number, section heading, and similarity score.
    Useful for finding raw source content before organizing into wiki pages.
    """
    try:
        db = get_db()
        query_vec = _encode(query)
        chunks = db.query(DocumentChunk).all()

        scored = []
        for chunk in chunks:
            if chunk.embedding_json:
                vec = json.loads(chunk.embedding_json)
                sim = _cosine_similarity(query_vec, vec)
                scored.append((sim, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        results = []
        for sim, chunk in top:
            meta = json.loads(chunk.metadata_json) if chunk.metadata_json else {}
            results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "source_path": meta.get("source_path"),
                "page_number": meta.get("page_number"),
                "section_heading": meta.get("section_heading"),
                "similarity": round(sim, 4),
                "content_snippet": chunk.content[:300],
                "char_count": len(chunk.content),
            })

        return json.dumps({
            "query": query,
            "total_chunks_searched": len(chunks),
            "results": results,
        })
    except Exception as e:
        error_msg = f"Failed to search chunks: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_search_across_all(query: str, limit: int = 10) -> str:
    """
    Unified vector search across BOTH wiki pages and ingested document chunks.

    Merges results with Reciprocal Rank Fusion (k=60), same as smart_query.
    """
    try:
        db = get_db()
        query_vec = _encode(query)

        # Search wiki pages
        page_vectors = db.query(PageVector).all()
        # Search document chunks
        doc_chunks = db.query(DocumentChunk).all()

        all_results = []

        for pv in page_vectors:
            vec = json.loads(pv.vector_json)
            sim = _cosine_similarity(query_vec, vec)
            all_results.append({
                "type": "wiki_page",
                "id": pv.page_id,
                "similarity": sim,
                "source": f"wiki://page/{pv.page_id}",
            })

        for chunk in doc_chunks:
            if chunk.embedding_json:
                meta = json.loads(chunk.metadata_json) if chunk.metadata_json else {}
                vec = json.loads(chunk.embedding_json)
                sim = _cosine_similarity(query_vec, vec)
                all_results.append({
                    "type": "document_chunk",
                    "id": chunk.id,
                    "document_id": chunk.document_id,
                    "similarity": sim,
                    "source": f"file://{meta.get('source_path', 'unknown')}",
                    "page": meta.get("page_number"),
                    "snippet": chunk.content[:200],
                })

        all_results.sort(key=lambda x: x["similarity"], reverse=True)

        return json.dumps({
            "query": query,
            "total_indexed": {
                "wiki_pages": len(page_vectors),
                "document_chunks": len(doc_chunks),
            },
            "results": all_results[:limit],
        })
    except Exception as e:
        error_msg = f"Failed to search across all: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_get_ingestion_status(
    document_id: int = None,
    content_hash: str = None,
    limit: int = 50,
) -> str:
    """
    Get status of ingested documents. Without arguments, lists recent documents.
    """
    try:
        db = get_db()
        if document_id:
            doc = db.query(IngestedDocument).filter_by(id=document_id).first()
            if not doc:
                return json.dumps({"error": f"Document {document_id} not found"})
            chunks = db.query(DocumentChunk).filter_by(document_id=doc.id).count()
            return json.dumps({
                "id": doc.id, "source_path": doc.source_path,
                "file_type": doc.file_type, "status": doc.status,
                "page_count": doc.page_count, "chunk_count": chunks,
                "content_hash": doc.content_hash,
                "error_message": doc.error_message,
                "created_at": doc.created_at.isoformat(),
            })
        elif content_hash:
            doc = db.query(IngestedDocument).filter_by(content_hash=content_hash).first()
            # ... same format ...
        else:
            docs = db.query(IngestedDocument).order_by(
                IngestedDocument.created_at.desc()
            ).limit(limit).all()
            return json.dumps({
                "total": len(docs),
                "documents": [{ "id": d.id, "source_path": d.source_path,
                    "status": d.status, "file_type": d.file_type,
                    "page_count": d.page_count, "created_at": d.created_at.isoformat(),
                } for d in docs],
            })
    except Exception as e:
        error_msg = f"Failed to get ingestion status: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_delete_ingested_document(document_id: int) -> str:
    """
    Remove a document and all its chunks from the ingestion index.
    """
    try:
        db = get_db()
        doc = db.query(IngestedDocument).filter_by(id=document_id).first()
        if not doc:
            return json.dumps({"error": f"Document {document_id} not found"})

        chunks_deleted = db.query(DocumentChunk).filter_by(
            document_id=doc.id
        ).delete()

        # Also clean up page_chunk_references
        chunk_ids = db.query(DocumentChunk.id).filter_by(document_id=doc.id).all()
        if chunk_ids:
            db.query(PageChunkReference).filter(
                PageChunkReference.chunk_id.in_([c[0] for c in chunk_ids])
            ).delete()

        db.delete(doc)
        db.commit()

        return json.dumps({
            "status": "deleted",
            "document_id": document_id,
            "chunks_deleted": chunks_deleted,
        })
    except Exception as e:
        error_msg = f"Failed to delete ingested document: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
```

---

## 6. Error Handling and Idempotency

### 6.1 Content Hash as Deterministic Key

Every file is identified by SHA-256 of its bytes. Before parsing, the orchestrator checks:

```python
content_hash = hashlib.sha256(Path(filepath).read_bytes()).hexdigest()
existing = db.query(IngestedDocument).filter_by(content_hash=content_hash).first()
if existing and existing.status == "completed":
    return {"status": "already_ingested", "document_id": existing.id}
```

This means:
- Same file ingested twice → second call returns "already_ingested" (no-op)
- File modified → new hash → new ingestion (old chunks preserved if different hash)
- Force re-ingestion → `force=True` deletes old chunks first

### 6.2 Idempotent Chunk Insert

Each chunk has its own content hash:

```python
chunk.content_hash = hashlib.sha256(chunk.content.encode()).hexdigest()
# UNIQUE constraint on content_hash prevents duplicate chunk insertion
```

If the orchestrator crashes mid-insertion, retrying the ingestion will skip already-inserted chunks (same hash) and only insert missing ones.

### 6.3 Transactional Status Updates

The status flow is:

```
pending → processing → completed
                     → failed (with error_message)
                     → partial (some pages failed, others succeeded)
```

Atomic transitions with DB commit after each step:

```
1. INSERT ingested_documents (status: "processing")  ← COMMIT
2. Parse document (in-memory, no DB writes)           ← no commit needed
3. Chunk (in-memory)                                  ← no commit needed
4. INSERT document_chunks one by one                  ← per-chunk COMMIT
5. UPDATE ingested_documents SET status="completed"   ← COMMIT
```

If step 4 fails mid-way, the document stays "processing" with partial chunks inserted. On retry (without force), the orchestrator detects the existing "processing" record, deletes its chunks, and starts fresh. With force=True, any prior record is cleaned up before starting.

### 6.4 Retry for Transient Errors

Uses the project's existing `tenacity` dependency:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(IOError),  # File lock, network (for future remote sources)
)
def _parse_document(filepath: str, file_type: FileType):
    return PARSER_REGISTRY[file_type](filepath)
```

### 6.5 Partial Failure for Multi-Page Documents

For scanned PDFs where some pages OCR successfully and others fail:

```python
def _parse_scanned_with_partial_fallback(doc: fitz.Document) -> tuple[list[dict], list[str]]:
    """Returns (successful_pages, error_page_numbers)."""
    successful = []
    errors = []
    for i, page in enumerate(doc):
        try:
            result = _ocr_page(page)
            successful.append(result)
        except Exception as e:
            errors.append(f"Page {i+1}: {e}")
            successful.append({
                "page_number": i + 1,
                "text": "",
                "char_count": 0,
                "metadata": {"ocr_error": str(e)},
            })
    return successful, errors
```

Result status becomes "partial" with error details in metadata.

---

## 7. Dependencies

### New packages to add

```toml
# pyproject.toml additions
[tool.poetry.dependencies]
pymupdf = "^1.25"           # PDF text extraction + page rendering → images
paddleocr = "^2.9"          # OCR engine (scanned PDFs, DOCX images, standalone images)
paddlepaddle = "^3.0"       # PaddleOCR backend (CPU version: paddlepaddle)
python-docx = "^1.1"        # DOCX text extraction + image detection
Pillow = "^11.0"            # Image loading for OCR (likely already a transitive dep)

# No new dependencies needed for:
# - Content hashing (stdlib hashlib)
# - Chunking (pure Python)
# - Embedding (reuses existing sentence-transformers)
# - MIME detection (stdlib mimetypes)
# - Markdown/text parsing (stdlib)
```

### Dependency size estimates

| Package | Install Size | Reason |
|---------|------------|--------|
| `pymupdf` | ~20 MB | C library (MuPDF), compact |
| `paddleocr` | ~30 MB | Python package + configs |
| `paddlepaddle` (CPU) | ~400 MB | Deep learning runtime |
| `python-docx` | ~5 MB | Pure Python |
| `Pillow` | ~3 MB | Likely already present |
| **Total new** | **~460 MB** | |

**Docker image impact**: The existing image already includes `torch` (~1GB via sentence-transformers). PaddlePaddle adds ~400MB. Total image ≈ 2–2.5GB — acceptable for a dedicated MCP server.

**Alternative (lighter)**: If the 400MB is too heavy, PaddleOCR supports an ONNX Runtime backend via `rapidocr-onnxruntime` (~50MB, no PyTorch/Paddle). Accuracy is slightly lower but still better than Tesseract. This is a viable tradeoff for resource-constrained deployments.

### Why not Tesseract?

Tesseract is 10MB and runs on CPU. But in 2025 benchmarks:
- Tesseract: 85–90% accuracy on clean docs, 18% character error rate on mixed text
- PaddleOCR: 92–95% accuracy, 0 character errors on clean documents
- For scanned PDFs (our primary OCR use case), Tesseract's error rate is too high for reliable wiki content

The 400MB tradeoff is worth the accuracy gain.

---

## 8. Implementation Plan (Phases)

### Phase 1: Core infrastructure (2–3 days)
1. Create `mcp-server/src/wiki_mcp_server/ingestion/` package
2. Add `IngestedDocument`, `DocumentChunk`, `PageChunkReference` to `db.py`
3. Implement `detector.py` with all file type detection
4. Implement `orchestrator.py` with idempotency + error handling
5. Implement `wikijs_ingest_file` MCP tool
6. Unit tests: detector, hash-based dedup, status transitions

### Phase 2: Parsers (2–3 days)
7. Implement `parsers/pdf.py` (text PDF via PyMuPDF)
8. Implement `parsers/image_ocr.py` (scanned PDF + images via PaddleOCR)
9. Implement `parsers/docx.py` (DOCX text + image extraction)
10. Implement `parsers/text.py` (markdown, text)
11. Integration tests: one real file of each type

### Phase 3: Chunking + embedding (2 days)
12. Implement `chunker.py` with section-aware recursive splitting
13. Reuse existing `_get_model()`, `_compute_embedding()` from `tools_pages.py`
14. Implement `document_chunks` table with embedding storage
15. Test chunk quality on real PDF and DOCX documents

### Phase 4: Search tools (1–2 days)
16. Implement `wikijs_search_chunks` MCP tool
17. Implement `wikijs_search_across_all` MCP tool
18. Implement `wikijs_get_ingestion_status` MCP tool
19. Implement `wikijs_ingest_directory` MCP tool
20. Implement `wikijs_delete_ingested_document` MCP tool

### Phase 5: Documentation + Docker (1 day)
21. Update `docker-compose.yml` for new dependencies
22. Update `pyproject.toml` and `requirements.txt`
23. Write `plans/document-ingestion/DESIGN.md` (this file)
24. Write `doc_v2/features/document-ingestion.md`
25. Update tool catalog in `doc_v2/reference/tool-catalog.md`
26. End-to-end test: ingest real document → search chunks → verify metadata

---

## 9. Pseudocode — Complete Pipeline Execution

```
FUNCTION ingest_file(filepath, force=False):
    # --- Deterministic dedup ---
    content_hash = SHA256(read_bytes(filepath))
    existing = DB.query("SELECT * FROM ingested_documents WHERE content_hash = ?", content_hash)

    IF existing AND NOT force:
        RETURN {"status": "already_ingested", "document_id": existing.id}

    IF existing AND force:
        DB.execute("DELETE FROM document_chunks WHERE document_id = ?", existing.id)
        DB.execute("DELETE FROM ingested_documents WHERE id = ?", existing.id)

    # --- File type detection ---
    info = detect_file_type(filepath)
    # info = {type: TEXT_PDF|SCANNED_PDF|DOCX|..., page_count: N, confidence: 0.9}

    # --- Create processing record ---
    ingestion_id = UUID4()
    doc = INSERT INTO ingested_documents (
        source_path, content_hash, file_type, status="processing",
        page_count, ingestion_id, parser_version="1.0.0"
    )
    COMMIT

    # --- Parse ---
    TRY:
        parser = PARSER_REGISTRY[info.type]
        pages = parser(filepath)
        # pages = [{page_number: 1, text: "...", char_count: N, metadata: {...}}, ...]
    CATCH Exception as e:
        UPDATE ingested_documents SET status="failed", error_message=e.message
        COMMIT
        RETURN {"status": "failed", "error": e.message}

    # --- Chunk ---
    TRY:
        chunks = chunk_document(pages, info.type)
        # chunks = [Chunk(content="...", chunk_index=0, page_number=1, section_heading="## Intro", ...), ...]
    CATCH Exception as e:
        UPDATE ingested_documents SET status="failed", error_message="Chunking failed: " + e.message
        COMMIT
        RETURN {"status": "failed", "error": e.message}

    # --- Embed + store ---
    model = _get_embedding_model()  # all-MiniLM-L6-v2 singleton
    success_count = 0
    error_count = 0

    FOR chunk IN chunks:
        TRY:
            embedding = model.encode(chunk.content)  # -> ndarray[384]
            metadata = BUILD_METADATA(chunk, filepath, info, ingestion_id)

            INSERT INTO document_chunks (
                document_id, chunk_index, content, content_hash,
                token_count, metadata_json, embedding_json, embedding_model
            ) VALUES (
                doc.id, chunk.chunk_index, chunk.content, chunk.content_hash,
                chunk.token_count, JSON(metadata), JSON(embedding), "all-MiniLM-L6-v2"
            )
            success_count += 1
        CATCH Exception as e:
            logger.warning(f"Chunk {chunk.chunk_index} embedding failed: {e}")
            error_count += 1

    # --- Finalize ---
    IF error_count == 0:
        UPDATE ingested_documents SET status="completed"
    ELIF success_count > 0:
        UPDATE ingested_documents SET status="partial"
        UPDATE ingested_documents SET error_message="X/Y chunks failed to embed"
    ELSE:
        UPDATE ingested_documents SET status="failed"
        UPDATE ingested_documents SET error_message="All chunks failed to embed"
    COMMIT

    RETURN {
        "status": doc.status,
        "document_id": doc.id,
        "file_type": info.type,
        "page_count": info.page_count,
        "chunk_count": success_count + error_count,
        "chunks_succeeded": success_count,
        "chunks_failed": error_count,
        "content_hash": content_hash,
        "ingestion_id": ingestion_id,
    }


FUNCTION chunk_document(pages, file_type):
    all_chunks = []

    IF file_type IN [TEXT_PDF, SCANNED_PDF]:
        FOR page IN pages:
            sections = split_by_paragraph_gaps(page.text)
            FOR section IN sections:
                sub_chunks = recursive_split(
                    section.text,
                    target_chars=1500,
                    overlap_chars=200
                )
                FOR sub IN sub_chunks:
                    all_chunks.append(Chunk(
                        content=sub.text,
                        chunk_index=len(all_chunks),
                        page_number=page.page_number,
                        section_heading=detect_heading(sub.text),
                        content_hash=SHA256(sub.text),
                        token_count=len(sub.text) / 3,
                    ))

    ELIF file_type IN [MARKDOWN, TEXT]:
        full_text = pages[0].text
        sections = split_by_headings(full_text) IF markdown ELSE split_by_paragraphs(full_text)
        FOR section IN sections:
            sub_chunks = recursive_split(
                section.text,
                target_chars=1500,
                overlap_chars=200
            )
            FOR sub IN sub_chunks:
                all_chunks.append(Chunk(...))

    # Merge short chunks (< 100 chars) with neighbors
    all_chunks = merge_short_chunks(all_chunks)

    # Re-index
    FOR i, chunk IN enumerate(all_chunks):
        chunk.chunk_index = i

    RETURN all_chunks
```

---

## 10. Integration with Existing LLM Wiki Workflow

The ingestion pipeline produces **searchable, attributed chunks**. The existing LLM Wiki Ingest workflow then consumes them:

```
┌─────────────────────────────────────────────────────────────────┐
│                     COMPLETE INGESTION FLOW                       │
│                                                                   │
│  1. wikijs_ingest_file("technical_report.pdf")                   │
│     └── Returns: {document_id: 42, chunks: 17, file_type: "text_pdf"} │
│                                                                   │
│  2. wikijs_search_chunks("authentication architecture")          │
│     └── Returns: 5 relevant chunks with page numbers, headings   │
│                                                                   │
│  3. Existing LLM Wiki Ingest workflow:                            │
│     a. wikijs_search_pages("authentication") → find existing     │
│     b. wikijs_get_page_stats(candidate_ids) → triage             │
│     c. wikijs_get_backlinks(core_page_id) → impact               │
│     d. wikijs_bulk_get_pages(affected_ids) → read current state  │
│     e. wikijs_update_page(id, content=updated + citation)        │
│     f. wikijs_append_to_page(log_id, "## [2026-05-23] ingest...")│
│                                                                   │
│  4. Optional: wikijs_link_file_to_page                           │
│     └── Map "technical_report.pdf" to the wiki page that         │
│         synthesizes it — creates a traceable link                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key design principle**: The pipeline parses and indexes raw sources. The LLM agent decides how to synthesize them into wiki pages. The pipeline does NOT create wiki pages automatically — that's the LLM's job, following the existing Ingest workflow conventions.

---

## 11. Comparison of OCR Options (Decision Record)

| Option | Accuracy | CPU Time/Page | Disk Footprint | License | Verdict |
|--------|----------|--------------|----------------|---------|---------|
| **PaddleOCR v2.9 CPU** | 92–95% | 2–5s | ~400MB | Apache 2.0 | **Selected** — best accuracy on CPU |
| Tesseract 5 | 85–90% | 0.5–1s | ~10MB | Apache 2.0 | Too inaccurate for scanned PDFs |
| PaddleOCR ONNX (rapidocr) | 88–92% | 1–2s | ~50MB | Apache 2.0 | Viable fallback for low-resource deploys |
| EasyOCR | 90–93% | 5–10s | ~1GB | Apache 2.0 | Slower, larger, no advantage |
| dots.ocr / PaddleOCR-VL | 95–97% | GPU required | ~6GB | Apache 2.0 | Best quality but needs GPU — future upgrade path |

---

## 12. Open Questions for Implementation

1. **Language detection**: Should PaddleOCR auto-detect language per page, or assume English? PaddleOCR supports `lang='en'`, `'ch'`, `'multilingual'`. Default to `'en'` with a config override.

2. **Table extraction**: PyMuPDF and pdfplumber can extract tables, but neither is great at it (PyMuPDF: 0.692 TEDS, pdfplumber: 0.847 TEDS). For high-accuracy table extraction, a dedicated tool like Docling (0.911 TEDS, MIT) could be added as a Phase 2 enhancement. For now, tables are extracted as text — potentially garbled but searchable.

3. **DOCX embedded image OCR quality**: PaddleOCR on DOCX images may struggle with diagrams that contain sparse text labels. An LLM Vision fallback (e.g., GPT-4o, Claude) would significantly improve diagram understanding. This can be added as an optional `vision_llm_client` parameter in a future version.

4. **Remote files**: Should the pipeline support URLs (HTTPS downloads)? Currently out of scope — files must be local. Adding a download step before ingestion is trivially additive.

5. **Incremental re-indexing**: If the embedding model changes (e.g., upgrading from MiniLM to a better model), chunks with the old model should be re-embedded. The `embedding_model` column tracks which model was used. A future `wikijs_rebuild_chunk_index` tool could handle this.


| Error | Detection | Action | DB Status |
|-------|-----------|--------|-----------|
| File not found | `Path(filepath).exists()` | Return error immediately | — |
| Unsupported file type | `detect_file_type()` | Return error with supported types list | — |
| Empty file | `file_size_bytes == 0` | Skip with warning | skipped |
| Corrupt PDF | `fitz.open()` fails | Return error | failed |
| Corrupt DOCX | `DocxDocument()` fails | Return error | failed |
| Encoding error (text) | `open(file, 'r')` with fallback | Try UTF-8 → latin-1 → cp1252 → error | failed |
| OCR engine crash | PaddleOCR exception | Retry 3x, then mark page as empty | partial |
| OOM during embedding | MemoryError | Stop processing, return partial results | partial |
| DB connection lost | SQLAlchemy OperationalError | Retry 3x with exponential backoff | processing |
| Duplicate file | Content hash match | Return "already_ingested" with existing doc_id | — |
| Force re-ingestion | `force=True` | Delete old chunks, re-process from scratch | completed |
