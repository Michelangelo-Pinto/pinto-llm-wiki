# Metadata Template — Post-Ingestion / Enrichment

Template for `metadata.md` written by the **EnrichmentReviewer** subagent after ingestion/enrichment.

## File Location

```
knowledge/ingested/YYYY-MM-DD-slug/metadata.md
```

## Template

```markdown
---
title: "Document Title"
category: "ingested"
source_type: file
source_file: "original-filename.pdf"
source_name: "Human-readable name"
fetched_at: "2026-05-31"
ingestion:
  document_id: "a1b2c3d4e5f6a7b8"
  file_type: "text_pdf"
  chunks_created: 24
  needs_ocr: false
  chunk_size: 1000
  chunk_overlap: 150
  collection: "documents"
enrichment:
  strategy: "full"
  status: "completed"
  llm_calls: 2
  run_id: "uuid"
  references_found: 5
pre_ingestion:
  analyzer: "PreIngestionAnalyzer"
  category: "legal"
  language: "it"
  analysis_notes: "Legal document with article structure"
created: "2026-05-31"
updated: "2026-05-31"
---

# Ingestion Report: Document Title

## Summary

Brief description of what was ingested and why.

## Pre-Ingestion Decisions

| Decision | Value | Rationale |
|----------|-------|-----------|
| chunk_size | 1000 | Legal articles are dense |
| collection | documents | Default collection |
| category | legal | Italian administrative law |

## Ingestion Results

- **File:** original-filename.pdf
- **Type detected:** text_pdf
- **Chunks created:** 24
- **OCR needed:** No

## Enrichment Results

- **Strategy:** full
- **LLM calls:** 2
- **References extracted:** 5

### References Found

| Type | ID | Article |
|------|-----|---------|
| law | 456/2018 | Art.12 c.3 |
| eu_regulation | 2016/679 | Art.83 |

## Chunk Map

| Index | Section | Type |
|-------|---------|------|
| 0 | Preamble | preamble |
| 1-5 | Capo I | article_body |
| 6-10 | Capo II - Sanzioni | article_body |
```

## Related

- [Payload Schema](payload-schema.md)
- [Subagents — EnrichmentReviewer](../guides/subagents.md)
- [Pre-Ingestion Analysis](../guides/pre-ingestion-analysis.md)
