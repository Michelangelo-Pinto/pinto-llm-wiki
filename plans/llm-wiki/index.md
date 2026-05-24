# wiki-js-mcp v3 Plans

This directory contains the complete plan system for the v3 architecture migration.

## Active Plans (v3 Migration)

| Document | Purpose |
|----------|---------|
| [ROADMAP_V3.md](ROADMAP_V3.md) | Master plan: 53 tasks across 5 phases |
| [ARCHITECTURE_V3.md](ARCHITECTURE_V3.md) | Complete v3 architecture with diagrams |
| [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) | Step-by-step v2 to v3 migration |
| [STATUS_V3.md](STATUS_V3.md) | Live progress tracker |
| [STANDARDS.md](STANDARDS.md) | Code standards, test requirements, PR checklist |
| [CHANGELOG.md](CHANGELOG.md) | Append-only change log |

## Sub-Plans

| # | Plan File | Component | Phase |
|---|-----------|-----------|-------|
| 01 | [subplans/01-qdrant-db.md](subplans/01-qdrant-db.md) | Qdrant DB Container | Phase 0 |
| 02 | [subplans/02-qdrant-mcp.md](subplans/02-qdrant-mcp.md) | Qdrant MCP Server | Phase 1 |
| 03 | [subplans/03-tesseract-mcp.md](subplans/03-tesseract-mcp.md) | Tesseract MCP Server | Phase 2a |
| 04 | [subplans/04-wikijs-update.md](subplans/04-wikijs-update.md) | Wiki.js MCP Update | Phase 2b |
| 05 | [subplans/05-ingestion-base.md](subplans/05-ingestion-base.md) | Ingestion Pipeline Base | Phase 3 |
| 06 | [subplans/06-ingestion-ocr.md](subplans/06-ingestion-ocr.md) | Ingestion OCR Routing | Phase 3 |
| 07 | [subplans/07-integration-tests.md](subplans/07-integration-tests.md) | Integration Tests | Phase 4 |
| 08 | [subplans/08-e2e-tests.md](subplans/08-e2e-tests.md) | E2E Tests | Phase 4 |
| 09 | [subplans/09-doc-v3.md](subplans/09-doc-v3.md) | doc_v3 Documentation | Phase 4 |
| 10 | [subplans/10-migration-vector-data.md](subplans/10-migration-vector-data.md) | Vector Data Migration | Phase 4 |
| 11 | [subplans/11-performance-tests.md](subplans/11-performance-tests.md) | Performance Benchmarks | Phase 4 |
| 12 | [subplans/12-cleanup.md](subplans/12-cleanup.md) | Cleanup | Phase 5 |
| 13 | [subplans/13-ci-cd.md](subplans/13-ci-cd.md) | CI/CD Pipeline | Phase 5 |

## Quick Links

- [System Architecture](../doc_v3/architecture/system-overview.md)
- [Multi-MCP Architecture](../doc_v3/architecture/multi-mcp-architecture.md)
- [Status Tracker](STATUS_V3.md)
