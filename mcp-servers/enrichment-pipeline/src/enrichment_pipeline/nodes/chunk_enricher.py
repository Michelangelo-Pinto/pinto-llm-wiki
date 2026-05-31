"""Per-chunk heuristic enrichment — zero LLM cost.

Heuristics applied:
- chunk_type detection: regex-based classification into preamble, article_body,
  annex, list, general. These are approximations — an article_body detection from
  "Art." regex may produce false positives on text discussing articles (e.g.,
  "Article 5 of the GDPR states..."). The trade-off is zero-cost classification
  vs. LLM-based with higher accuracy but token cost.
- section extraction: nearest markdown heading or first 120 chars of chunk text.
  Works well for markdown/HTML where headings are preserved. Less reliable for
  plain text PDFs where headings were lost during extraction.
- summary: truncated first 200 chars. Quick preview, not a semantic summary.
  Full LLM-based per-chunk summarization is a future optimization (gated behind
  cost_saving_mode=false).
- Layer 2-4 population: classification data from LLM output is spread across
  all chunks using setdefault() to avoid overwriting existing agent data.
"""

import re

from ..logger import StepTimer

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_ARTICLE_RE = re.compile(r"Art\.?\s*\d+", re.I)


def _detect_chunk_type(text: str, chunk_index: int) -> str:
    """Infer chunk_type from content patterns."""
    if chunk_index == 0:
        return "preamble"
    if _ARTICLE_RE.search(text):
        return "article_body"
    if "allegato" in text.lower() or "annex" in text.lower():
        return "annex"
    if text.strip().startswith("- ") or text.strip().startswith("* "):
        return "list"
    return "general"


def _extract_section(text: str) -> str:
    """Extract nearest heading or first line as section title."""
    match = _HEADING_RE.search(text)
    if match:
        return match.group(1).strip()
    first_line = text.strip().split("\n")[0]
    return first_line[:120] if first_line else ""


def enrich_chunks_heuristics(state: dict) -> dict:
    """Apply document-level classification and chunk-level heuristics to payloads."""
    document_id = state["document_id"]
    classification = state.get("classification") or {}

    with StepTimer(state, "enrich_chunks", document_id) as timer:
        enriched = []
        for chunk in state.get("chunks", []):
            payload = chunk.get("payload", {})
            text = payload.get("core", {}).get("text") or payload.get("text", "")
            chunk_index = payload.get("core", {}).get("chunk_index", payload.get("chunk_index", 0))

            # Layer 2: routing
            routing = payload.setdefault("routing", {})
            if classification.get("category"):
                routing["category"] = classification["category"]
            if classification.get("subcategory"):
                routing["subcategory"] = classification["subcategory"]
            if classification.get("language"):
                routing["language"] = classification["language"]

            # Layer 3: document (same for all chunks)
            doc_layer = payload.setdefault("document", {})
            for key in ("title", "doc_type", "date", "domain_specific"):
                if classification.get(key) is not None:
                    doc_layer[key] = classification[key]

            # Layer 4: chunk
            chunk_layer = payload.setdefault("chunk", {})
            chunk_layer["section"] = _extract_section(text)
            chunk_layer["chunk_type"] = _detect_chunk_type(text, chunk_index)
            chunk_layer["summary"] = (text[:200].strip() + "...") if len(text) > 200 else text.strip()

            # Sync legacy flat fields
            payload["document_id"] = payload.get("core", {}).get("document_id", payload.get("document_id"))
            payload["chunk_index"] = chunk_index
            payload["text"] = text
            if routing.get("category"):
                payload["category"] = routing["category"]

            enriched.append(chunk)

        state["enriched_chunks"] = enriched
        state["status"] = "enriched"
        timer.extra["chunks_enriched"] = len(enriched)

    return state
