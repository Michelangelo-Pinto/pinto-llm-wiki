"""Reference extraction node — one LLM call per document.

Extraction strategy:
- Primary: LLM-based extraction via OpenAI (structured JSON output)
- Fallback: regex patterns for Italian legal references (L., D.Lgs., Art.)
  Zero LLM cost in cost_saving_mode when regex finds matches.
- Cost-saving hybrid: regex first, LLM only if regex returns nothing.
  Reduces LLM calls on legal documents where regex is highly reliable.
- Full text truncated to 12000 chars before LLM to control token cost.
- Supported reference types: law, eu_regulation, standard, paper.
  Extensible via the system prompt without code changes.
- LLM temperature set to 0.0 for deterministic structured extraction.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List

from ..config import load_config
from ..logger import StepTimer

logger = logging.getLogger(__name__)

# Italian legal reference patterns (regex fallback, zero LLM cost)
_LAW_PATTERNS = [
    re.compile(r"(?:L\.|Legge|D\.Lgs\.|D\.L\.)\s*n?\.?\s*(\d+/\d{4})", re.I),
    re.compile(r"(?:Reg\.?\s*(?:UE|CE)?|Regolamento)\s*(?:\(UE\)\s*)?(\d+/\d{4})", re.I),
    re.compile(r"Art\.?\s*(\d+[a-z]?)(?:\s*,?\s*comma\s*(\d+))?", re.I),
]


def _regex_extract_references(text: str) -> List[Dict[str, Any]]:
    """Extract legal references via regex when LLM is unavailable."""
    refs = []
    seen = set()
    for pattern in _LAW_PATTERNS:
        for match in pattern.finditer(text):
            ref_id = match.group(1) if match.lastindex else match.group(0)
            key = (pattern.pattern[:20], ref_id)
            if key not in seen:
                seen.add(key)
                refs.append({
                    "type": "law",
                    "id": ref_id,
                    "article": None,
                    "comma": None,
                    "mentioned_in_context": match.group(0),
                })
    return refs


def _llm_extract_references(full_text: str, config: dict) -> tuple:
    """Extract structured references using OpenAI."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    llm = ChatOpenAI(
        model=config.get("llm_model", "gpt-4o-mini"),
        temperature=0.0,
        max_tokens=config.get("llm_max_tokens", 2000),
        api_key=api_key,
    )
    system = (
        "Extract all normative/legal/technical cross-references from the text. "
        "Return ONLY a JSON array of objects with keys: type, id, article, comma, "
        "mentioned_in_context. type examples: law, eu_regulation, standard, paper."
    )
    # Truncate very long docs to control token cost
    sample = full_text[:12000]
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=sample),
    ])
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    refs = json.loads(content)
    usage = getattr(response, "usage_metadata", None)
    return refs if isinstance(refs, list) else [], usage


def extract_references(state: dict) -> dict:
    """Extract cross-references from full document text."""
    document_id = state["document_id"]
    config = load_config()

    full_text = "\n\n".join(
        c.get("payload", {}).get("core", {}).get("text", "")
        or c.get("payload", {}).get("text", "")
        for c in state.get("chunks", [])
    )

    with StepTimer(state, "extract_references", document_id) as timer:
        try:
            if os.environ.get("OPENAI_API_KEY") and not config.get("cost_saving_mode"):
                refs, usage = _llm_extract_references(full_text, config)
                state["llm_calls"] = state.get("llm_calls", 0) + 1
                timer.extra["llm_calls"] = 1
                if usage:
                    timer.extra["tokens_in"] = usage.get("input_tokens", 0)
                    timer.extra["tokens_out"] = usage.get("output_tokens", 0)
            else:
                refs = _regex_extract_references(full_text)
                if os.environ.get("OPENAI_API_KEY"):
                    # cost_saving_mode: try LLM only if regex found nothing
                    if not refs:
                        refs, usage = _llm_extract_references(full_text, config)
                        state["llm_calls"] = state.get("llm_calls", 0) + 1
                        timer.extra["llm_calls"] = 1
                timer.extra["source"] = "regex" if refs else "llm"
        except Exception as e:
            logger.error("Reference extraction failed: %s", e)
            refs = _regex_extract_references(full_text)
            timer.extra["fallback"] = str(e)

        state["references"] = refs
        state["status"] = "references_extracted"
        timer.extra["refs_found"] = len(refs)

    return state
