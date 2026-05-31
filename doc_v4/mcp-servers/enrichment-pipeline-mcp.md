# Enrichment Pipeline MCP v4

Post-ingestion payload enrichment via LangGraph workflow.

## Container

| Property | Value |
|----------|-------|
| Image | `wiki-js-enrichment-pipeline:latest` |
| Container | `wikijs_enrichment` |
| Port | 8004 |
| SSE path | `/sse` |
| Prefix | `enrich_*` |

## Tools (4)

| Tool | Description |
|------|-------------|
| `enrich_get_config` | Read `knowledge/enrichment-config.md` |
| `enrich_set_config` | Update config key (hot-reload) |
| `enrich_document` | Run LangGraph enrichment for document_id |
| `enrich_get_status` | Enrichment run status and structured logs |

## LangGraph Workflow

```
pre_analysis → [skip|basic|references_only|full]
  → classify_document (basic/full)
  → extract_references (full/references_only)
  → map_references → enrich_chunks → upsert → record_completion
```

Strategies: `skip`, `basic`, `references_only`, `full`.

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant-db:6334` | Qdrant REST |
| `QDRANT_COLLECTION_DOCUMENTS` | `documents` | Target collection |
| `ENRICHMENT_DB` | `/data/enrichment.db` | SQLite tracking |
| `ENRICHMENT_CONFIG_PATH` | `/app/knowledge/enrichment-config.md` | Config file |
| `OPENAI_API_KEY` | — | Required for LLM classification/extraction |
| `MCP_PORT` | `8004` | SSE port |

## Volumes

| Mount | Purpose |
|-------|---------|
| `./to_ingest:/data/shared:ro` | Shared files |
| `ingestion_data:/data/ingestion:ro` | Read ingestion.db |
| `enrichment_data:/data` | enrichment.db |
| `./knowledge:/app/knowledge:rw` | Config read/write |

## Related

- [Payload Schema](../reference/payload-schema.md)
- [Pre-Ingestion Analysis](../guides/pre-ingestion-analysis.md)
- [Enrichment Config](../../knowledge/enrichment-config.md)
