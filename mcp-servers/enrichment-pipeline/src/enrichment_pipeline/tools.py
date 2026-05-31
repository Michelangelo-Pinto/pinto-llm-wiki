"""MCP tools for the enrichment pipeline."""

import json
import logging
from typing import Optional

from .config import load_config, save_config
from .db import EnrichmentRun, get_db
from .graph import run_enrichment
from .qdrant_client import fetch_document_chunks

logger = logging.getLogger(__name__)


def enrich_get_config() -> str:
    """Read current enrichment configuration from knowledge/enrichment-config.md."""
    try:
        config = load_config()
        return json.dumps({"config": config})
    except Exception as e:
        return json.dumps({"error": str(e)})


def enrich_set_config(key: str, value: str) -> str:
    """Update a single key in enrichment-config.md (hot-reload on next read).

    Common keys: enabled (true/false), llm_model, cost_saving_mode.
    """
    try:
        # Coerce boolean strings
        parsed: object = value
        if value.lower() in ("true", "false"):
            parsed = value.lower() == "true"
        elif value.isdigit():
            parsed = int(value)

        updated = save_config({key: parsed})
        return json.dumps({"status": "updated", "key": key, "value": parsed, "config": updated})
    except Exception as e:
        return json.dumps({"error": str(e)})


def enrich_document(document_id: str, collection: str = "documents") -> str:
    """Run post-ingestion enrichment for a document via LangGraph workflow.

    Fetches all chunks from Qdrant, runs classification/reference extraction,
    and upserts enriched payloads. Manual calls work even when enabled=false.
    """
    try:
        chunks = fetch_document_chunks(document_id, collection)
        if not chunks:
            return json.dumps({"error": f"No chunks found for document_id: {document_id}"})

        file_type = chunks[0]["payload"].get("file_type", "unknown")
        source_file = chunks[0]["payload"].get("source_file", "")

        result = run_enrichment(
            document_id=document_id,
            chunks=chunks,
            file_type=file_type,
            source_file=source_file,
            collection=collection,
        )

        return json.dumps({
            "status": result.get("status", "unknown"),
            "document_id": document_id,
            "strategy": result.get("enrichment_strategy"),
            "llm_calls": result.get("llm_calls", 0),
            "run_id": result.get("run_id"),
            "log_entries": result.get("log_entries", []),
        })
    except Exception as e:
        logger.error("Enrichment failed for %s: %s", document_id, e)
        return json.dumps({"error": str(e)})


def enrich_get_status(document_id: Optional[str] = None) -> str:
    """Get enrichment run status and structured logs for one or all documents."""
    db = get_db()
    try:
        if document_id:
            run = (
                db.query(EnrichmentRun)
                .filter(EnrichmentRun.document_id == document_id)
                .order_by(EnrichmentRun.created_at.desc())
                .first()
            )
            if not run:
                return json.dumps({"error": f"No enrichment run for document_id: {document_id}"})
            import json as _json
            return json.dumps({
                "run_id": run.run_id,
                "document_id": run.document_id,
                "strategy": run.strategy,
                "status": run.status,
                "llm_calls": run.llm_calls,
                "total_tokens": run.total_tokens,
                "duration_ms": run.duration_ms,
                "log_entries": _json.loads(run.log_entries or "[]"),
                "created_at": str(run.created_at),
            })

        runs = db.query(EnrichmentRun).order_by(EnrichmentRun.created_at.desc()).limit(50).all()
        return json.dumps({
            "runs": [{
                "run_id": r.run_id,
                "document_id": r.document_id,
                "strategy": r.strategy,
                "status": r.status,
                "llm_calls": r.llm_calls,
            } for r in runs],
        })
    finally:
        db.close()
