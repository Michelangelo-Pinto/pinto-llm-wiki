"""Map document-level references to individual chunks via text search."""

import re
from typing import Any, Dict, List

from ..logger import StepTimer


def _ref_search_terms(ref: Dict[str, Any]) -> List[str]:
    """Build searchable strings from a reference object."""
    terms = []
    if ref.get("id"):
        terms.append(str(ref["id"]))
    if ref.get("mentioned_in_context"):
        terms.append(ref["mentioned_in_context"])
    if ref.get("article"):
        terms.append(str(ref["article"]))
    return [t for t in terms if t]


def map_references_to_chunks(state: dict) -> dict:
    """Assign references.cites to chunks that contain matching text (zero LLM)."""
    document_id = state["document_id"]
    references = state.get("references") or []

    with StepTimer(state, "map_references", document_id) as timer:
        mapped_count = 0
        for chunk in state.get("chunks", []):
            payload = chunk.setdefault("payload", {})
            refs_layer = payload.setdefault("references", {})
            cites: List[Dict[str, Any]] = []

            text = payload.get("core", {}).get("text") or payload.get("text", "")
            text_lower = text.lower()

            for ref in references:
                for term in _ref_search_terms(ref):
                    if term.lower() in text_lower or re.search(re.escape(term), text, re.I):
                        cites.append(ref)
                        mapped_count += 1
                        break

            refs_layer["cites"] = cites
            refs_layer.setdefault("cited_by", [])
            refs_layer.setdefault("entities", [])

        timer.extra["chunks_mapped"] = mapped_count
        state["status"] = "references_mapped"

    return state
