"""JSON parser: convert JSON documents to chunkable plain text.

Design decisions:
- Arrays of objects rendered as "key: value" blocks separated by "---" for clean chunk boundaries
- Nesting flattened only to depth 2 — deeper structures serialized as compact JSON strings
  to avoid path explosion (e.g., deeply nested config files with hundreds of keys)
- Flat scalar arrays preserve index notation ([0], [1]) for structure awareness
- 100 MB threshold triggers a warning but loads the full file (iterative streaming via ijson
  is a future optimization for very large JSON datasets)
"""

import json
import logging
from pathlib import Path
from typing import Any, List

logger = logging.getLogger(__name__)

# Maximum nesting depth before falling back to compact JSON serialization.
# Depth 2 means we get "parent.child: value" but deeper nests become JSON strings.
# Rationale: chunking deep trees line-by-line creates unreadable payloads with
# hundreds of dotted keys that add no retrieval value.
_MAX_FLATTEN_DEPTH = 2

# Files above this size trigger a memory warning. ijson streaming parser would be
# the proper solution for production, but adds complexity for the common case (< 100 MB).
_LARGE_FILE_BYTES = 100 * 1024 * 1024  # 100 MB


def _flatten(obj: Any, prefix: str = "", depth: int = 0) -> List[str]:
    """Flatten nested dict/list to 'key: value' lines (max depth 2)."""
    lines: List[str] = []

    if isinstance(obj, dict):
        if depth >= _MAX_FLATTEN_DEPTH:
            lines.append(f"{prefix}: {json.dumps(obj, ensure_ascii=False)}")
            return lines
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, (dict, list)):
                lines.extend(_flatten(value, full_key, depth + 1))
            else:
                lines.append(f"{full_key}: {value}")
    elif isinstance(obj, list):
        if depth >= _MAX_FLATTEN_DEPTH:
            lines.append(f"{prefix}: {json.dumps(obj, ensure_ascii=False)}")
            return lines
        for i, item in enumerate(obj):
            item_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
            if isinstance(item, (dict, list)):
                lines.extend(_flatten(item, item_key, depth + 1))
            else:
                lines.append(f"{item_key}: {item}")
    else:
        lines.append(f"{prefix}: {obj}" if prefix else str(obj))

    return lines


def _render_value(data: Any) -> str:
    """Render parsed JSON as structured plain text."""
    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
        # Array of objects: separate records with ---
        blocks = []
        for obj in data:
            lines = _flatten(obj)
            blocks.append("\n".join(lines))
        return "\n---\n".join(blocks)

    if isinstance(data, dict):
        return "\n".join(_flatten(data))

    if isinstance(data, list):
        return "\n".join(_flatten(data))

    return str(data)


def extract_json(file_path: str) -> str:
    """Convert JSON to structured plain text for chunking.

    Arrays of objects: each object as 'key: value' lines, separated by '---'.
    Nested objects flattened to depth 2 with dot-notation keys.
    Scalar values converted directly to text.
    Encoding: UTF-8 per JSON spec.

    Args:
        file_path: Path to the JSON file.

    Returns:
        Chunkable text preserving JSON structure.
    """
    path = Path(file_path)
    size = path.stat().st_size

    if size > _LARGE_FILE_BYTES:
        logger.warning(
            "Large JSON file (%d bytes) at %s; loading entire file into memory",
            size,
            file_path,
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning("JSON file %s is not valid UTF-8; using replacement", file_path)
        raw = path.read_bytes().decode("utf-8", errors="replace")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", file_path, e)
        raise ValueError(f"Invalid JSON: {e}") from e

    text = _render_value(data)
    if not text.strip():
        logger.warning("Empty text after JSON conversion: %s", file_path)
    return text
