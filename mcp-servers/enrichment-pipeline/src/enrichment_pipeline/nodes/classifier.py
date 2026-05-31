"""Document classification node — one LLM call per document.

Classification strategy:
- 5000 char sample (configurable via enrichment-config.md): enough for reliable
  topic detection without hitting token limits. Longer samples don't improve
  accuracy for domain-level classification but increase cost linearly.
- System prompt constrains output to known categories (legal, software-engineering,
  data-science, operations, ingested) to maintain consistent routing filter values.
- Heuristic fallback detects Italian legal text by keyword ("articolo", "legge",
  "decreto") — covers the most common case when OPENAI_API_KEY is unavailable.
- LLM errors fall back to heuristics rather than failing the entire pipeline.
"""

import json
import logging
import os
from typing import Any, Dict, List

from ..config import load_config
from ..logger import StepTimer

logger = logging.getLogger(__name__)


def _sample_text(chunks: List[dict], max_chars: int) -> str:
    """Concatenate chunk text up to max_chars for classification sample."""
    parts = []
    total = 0
    for chunk in chunks:
        payload = chunk.get("payload", {})
        text = payload.get("core", {}).get("text") or payload.get("text", "")
        if total + len(text) > max_chars:
            parts.append(text[: max_chars - total])
            break
        parts.append(text)
        total += len(text)
    return "\n\n".join(parts)


def _heuristic_classify(sample: str, file_type: str) -> Dict[str, Any]:
    """Fallback classification without LLM when API key is unavailable."""
    language = "it" if any(w in sample.lower() for w in ("articolo", "legge", "decreto")) else "en"
    category = "legal" if "legge" in sample.lower() or "art." in sample.lower() else "ingested"
    return {
        "category": category,
        "subcategory": None,
        "language": language,
        "title": None,
        "doc_type": file_type.split("_")[0] if file_type else "unknown",
        "domain_specific": {},
        "_source": "heuristic",
    }


def _llm_classify(sample: str, config: dict) -> Dict[str, Any]:
    """Classify document using OpenAI via LangChain."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set; cannot run LLM classification")

    llm = ChatOpenAI(
        model=config.get("llm_model", "gpt-4o-mini"),
        temperature=config.get("llm_temperature", 0.1),
        max_tokens=config.get("llm_max_tokens", 2000),
        api_key=api_key,
    )

    system = (
        "You classify documents for a knowledge base. "
        "Return ONLY valid JSON with keys: category, subcategory, language, "
        "title, doc_type, domain_specific (object). "
        "category examples: legal, software-engineering, data-science, operations, ingested."
    )
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Classify this document sample:\n\n{sample[:8000]}"),
    ])
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    result = json.loads(content)
    result["_source"] = "llm"
    usage = getattr(response, "usage_metadata", None) or {}
    return result, usage


def classify_document(state: dict) -> dict:
    """Classify document category, language, title (1 LLM call or heuristic fallback)."""
    document_id = state["document_id"]
    config = load_config()
    sample_chars = int(config.get("sample_chars_for_classification", 5000))
    sample = _sample_text(state.get("chunks", []), sample_chars)
    file_type = state.get("file_type", "unknown")

    with StepTimer(state, "classify_document", document_id) as timer:
        try:
            if os.environ.get("OPENAI_API_KEY"):
                classification, usage = _llm_classify(sample, config)
                state["llm_calls"] = state.get("llm_calls", 0) + 1
                timer.extra["llm_calls"] = 1
                if usage:
                    timer.extra["tokens_in"] = usage.get("input_tokens", 0)
                    timer.extra["tokens_out"] = usage.get("output_tokens", 0)
            else:
                classification = _heuristic_classify(sample, file_type)
                timer.extra["llm_calls"] = 0
                logger.warning("No OPENAI_API_KEY; using heuristic classification")
        except Exception as e:
            logger.error("Classification failed: %s", e)
            classification = _heuristic_classify(sample, file_type)
            timer.extra["fallback"] = str(e)

        state["classification"] = classification
        state["status"] = "classified"
        timer.extra["category"] = classification.get("category")

    return state
