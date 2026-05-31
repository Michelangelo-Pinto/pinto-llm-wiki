"""Qdrant payload builder for 5-layer schema."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def build_chunk_payload(
    *,
    document_id: str,
    chunk_index: int,
    chunk_text: str,
    source_file: str,
    file_type: str,
    source_type: str = "file",
    routing_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a 5-layer Qdrant payload for one chunk.

    Layer 1 (core) and partial Layer 2 (routing) are populated by ingestion.
    Layers 3-5 are empty placeholders filled by pre-ingestion agent or enrichment.

    Args:
        document_id: SHA-256 prefix identifying the source document.
        chunk_index: Zero-based chunk position.
        chunk_text: Raw chunk text (also embedded separately as vector input).
        source_file: Original file path.
        file_type: Detected subtype (e.g. text_pdf, html, json).
        source_type: Origin of content (file, web, agent).
        routing_overrides: Optional pre-classification from agent (category, etc.).

    Returns:
        Nested dict matching the 5-layer payload schema.
    """
    routing = {
        "category": None,
        "subcategory": None,
        "language": None,
        "source_type": source_type,
    }
    if routing_overrides:
        for key in ("category", "subcategory", "language", "source_type"):
            if routing_overrides.get(key) is not None:
                routing[key] = routing_overrides[key]

    return {
        "core": {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": chunk_text,
            "chunk_hash": hashlib.sha256(chunk_text.encode()).hexdigest()[:16],
        },
        "routing": routing,
        "document": {},
        "chunk": {},
        "references": {},
        # Legacy flat fields for backward-compatible filters and search tools
        "document_id": document_id,
        "chunk_index": chunk_index,
        "source_file": source_file,
        "file_type": file_type,
        "text": chunk_text,
        "content_hash": hashlib.sha256(chunk_text.encode()).hexdigest()[:16],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def chunk_source_type(subtype: str) -> str:
    """Map document subtype to chunker source_type hint."""
    base = subtype.split("_")[0]
    # HTML parser emits markdown-style headings; use markdown chunk boundaries
    if base == "html":
        return "markdown"
    return base
