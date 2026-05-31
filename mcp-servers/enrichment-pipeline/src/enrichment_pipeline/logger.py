"""Structured JSON-lines logging for enrichment pipeline steps.

Output format: one JSON object per line, suitable for grep/jq analysis.

Mandatory fields per entry:
    timestamp: ISO 8601 UTC timestamp
    step: enrichment step name (pre_analysis, classify_document, etc.)
    document_id: target document UUID
    status: "ok" or "error"
    duration_ms: step wall-clock time in milliseconds

Optional per-step fields:
    llm_calls: number of LLM invocations (classify_document, extract_references)
    tokens_in / tokens_out: token usage from OpenAI response metadata
    refs_found: count of extracted references
    chunks_mapped: count of chunk-reference associations
    strategy: chosen enrichment strategy (skip/basic/references_only/full)

Error convention:
    WARNING: non-fatal issues (fallback to heuristic, missing optional data)
    ERROR: fatal step failures (classification failed, Qdrant unreachable)
    Exceptions inside StepTimer are caught and logged with status="error";
    the False return from __exit__ propagates the exception to LangGraph.

Usage:
    entry = make_log_entry("classify", doc_id, status="ok", category="legal")
    append_log(state, entry)  # appends to state["log_entries"] + emits JSON line
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def make_log_entry(
    step: str,
    document_id: str,
    status: str = "ok",
    duration_ms: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a structured log entry dict."""
    entry = {
        "timestamp": utc_now_iso(),
        "step": step,
        "document_id": document_id,
        "status": status,
    }
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms
    entry.update(extra)
    return entry


def append_log(state: dict, entry: Dict[str, Any]) -> None:
    """Append entry to state log_entries and emit JSON line to logger."""
    if "log_entries" not in state:
        state["log_entries"] = []
    state["log_entries"].append(entry)
    logger.info(json.dumps(entry, default=str))


class StepTimer:
    """Context manager to time a pipeline step and append structured log."""

    def __init__(self, state: dict, step: str, document_id: str):
        self.state = state
        self.step = step
        self.document_id = document_id
        self.start = 0.0
        self.extra: Dict[str, Any] = {}

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.perf_counter() - self.start) * 1000)
        status = "error" if exc_type else "ok"
        entry = make_log_entry(
            self.step,
            self.document_id,
            status=status,
            duration_ms=duration_ms,
            **self.extra,
        )
        if exc_type:
            entry["error"] = str(exc_val)
        append_log(self.state, entry)
        return False
