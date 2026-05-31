"""Pre-enrichment analysis: decide strategy before any LLM call."""

import logging
from typing import Any, Dict

from ..logger import StepTimer, append_log

logger = logging.getLogger(__name__)


def _get_routing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract routing layer from payload (nested or flat fallback)."""
    if "routing" in payload and isinstance(payload["routing"], dict):
        return payload["routing"]
    return {}


def pre_enrichment_analysis(state: dict) -> dict:
    """Decide enrichment strategy based on agent pre-classification and doc traits.

    Strategies:
        skip: Document too small; no enrichment.
        basic: Classify only (noisy OCR docs).
        references_only: Agent pre-classified; extract references only.
        full: Classify + extract references + chunk heuristics.
    """
    document_id = state["document_id"]
    chunks = state.get("chunks", [])

    with StepTimer(state, "pre_analysis", document_id) as timer:
        if not chunks:
            state["enrichment_strategy"] = "skip"
            state["status"] = "skipped"
            timer.extra["reason"] = "no_chunks"
            return state

        first_payload = chunks[0].get("payload", {})
        routing = _get_routing(first_payload)
        agent_classified = routing.get("category") is not None

        if agent_classified:
            state["enrichment_strategy"] = "references_only"
            state["classification"] = {
                "category": routing.get("category"),
                "subcategory": routing.get("subcategory"),
                "language": routing.get("language"),
                "title": first_payload.get("document", {}).get("title"),
                "doc_type": first_payload.get("document", {}).get("doc_type"),
            }
            timer.extra["strategy"] = "references_only"
            timer.extra["agent_pre_classified"] = True
            append_log(state, {
                "timestamp": timer.extra.get("timestamp"),
                "step": "pre_analysis",
                "document_id": document_id,
                "status": "ok",
                "message": "Agent pre-classified; references_only strategy",
            })
            return state

        total_chars = sum(
            len(c.get("payload", {}).get("core", {}).get("text", "")
                or c.get("payload", {}).get("text", ""))
            for c in chunks
        )
        file_type = state.get("file_type") or first_payload.get("file_type", "unknown")

        if total_chars < 5000 and len(chunks) < 5:
            state["enrichment_strategy"] = "skip"
            timer.extra["strategy"] = "skip"
            timer.extra["total_chars"] = total_chars
        elif file_type in ("scanned_pdf", "image", "mixed_docx"):
            state["enrichment_strategy"] = "basic"
            timer.extra["strategy"] = "basic"
        else:
            state["enrichment_strategy"] = "full"
            timer.extra["strategy"] = "full"

        state["status"] = "analyzed"

    return state


def route_by_strategy(state: dict) -> str:
    """Conditional router: return next node name or END sentinel."""
    strategy = state.get("enrichment_strategy", "skip")
    if strategy == "skip":
        return "skip"
    if strategy == "references_only":
        return "references_only"
    if strategy == "basic":
        return "basic"
    return "full"
