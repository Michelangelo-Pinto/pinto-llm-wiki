# Test Data

Pre-generated fixture files for E2E and integration tests.

## Files

| File | Content | Used By |
|------|---------|---------|
| `pdf/test_text.pdf` | Single-page text PDF (not scanned) | E2E PDF parsing |
| `pdf/test_scanned.pdf` | Scanned-image PDF (requires OCR) | E2E OCR routing |
| `docx/test_text.docx` | Text-only DOCX | E2E DOCX parsing |
| `docx/test_with_images.docx` | DOCX with embedded images | E2E DOCX image extraction |
| `markdown/test.md` | Markdown file with frontmatter | E2E markdown parsing |
| `text/test.txt` | Plain text file | E2E text parsing |
| `images/test_scan.png` | Image with text for OCR | E2E image ingestion |
| `mixed/config.txt` | Mixed directory fixture | E2E batch ingestion |
| `mixed/readme.md` | Mixed directory fixture | E2E batch ingestion |

## Regenerating Fixtures

```bash
# Build the ingestion-pipeline image (needed for generate_test_data.py)
docker compose build ingestion-pipeline

# Generate all test data
docker compose run --rm \
  -v ./tests/test-data:/data/test-data \
  ingestion-pipeline \
  python /data/test-data/generate_test_data.py
```

> **Note:** Fixtures are committed to the repo so CI and local test runs don't need regeneration. If you add new file types or modify the generator script, regenerate and commit the new fixtures.
