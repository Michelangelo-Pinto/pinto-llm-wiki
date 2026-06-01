# Tesseract MCP Server

*Container: `pinto_llm_tesseract_mcp` | Port: `8003` | Transport: SSE | Tools: 7*

MCP server for OCR text extraction and document type detection using Tesseract.

> **Note:** The Ingestion Pipeline uses `pytesseract` in-process for batch document processing. The Tesseract MCP server is for **agent-facing** OCR — when an LLM agent needs to extract text from an image or classify a document on demand.

## Container

```yaml
tesseract-mcp:
  build: ./mcp-servers/tesseract-mcp
  image: pinto-llm-tesseract-mcp:latest
  ports: ["8003:8003"]
  environment:
    MCP_HOST: 0.0.0.0
    MCP_PORT: 8003
    TESSDATA_PREFIX: /usr/share/tesseract-ocr/5/tessdata
```

Image size: ~300 MB (python:3.12-slim + tesseract-ocr eng+ita).

## Tool Catalog

| # | Tool | Purpose |
|---|------|---------|
| 1 | `ocr_extract_text` | OCR text extraction from images and PDFs |
| 2 | `ocr_detect_document_type` | Classify document type (text, scanned, mixed) |
| 3 | `ocr_extract_hocr` | Extract text with positional HOCR output |
| 4 | `ocr_get_confidence` | Get per-word OCR confidence scores |
| 5 | `ocr_get_languages` | List available Tesseract language packs |
| 6 | `ocr_process_document` | Hybrid document processing (native text + OCR) |
| 7 | `ocr_preprocess_and_extract` | Preprocess image then OCR |

## Document Type Detection

The `ocr_detect_document_type` tool uses a PyMuPDF-based heuristic:

- **Text PDFs**: Detected by sampling text content from the first few pages
- **Scanned PDFs**: No extractable text → requires OCR
- **Images**: Always routed to OCR

## Preprocessing Pipeline

The `ocr_preprocess_and_extract` tool applies:
1. Grayscale conversion
2. Deskew (straighten rotated text)
3. Adaptive thresholding (binarization)
4. Denoising
5. Sharpening

This improves OCR accuracy on low-quality scans.

## Supported Languages

The default Docker image includes:
- `eng` — English
- `ita` — Italian

Add more language packs in the Dockerfile:
```dockerfile
RUN apt-get install -y tesseract-ocr-fra tesseract-ocr-deu
```
