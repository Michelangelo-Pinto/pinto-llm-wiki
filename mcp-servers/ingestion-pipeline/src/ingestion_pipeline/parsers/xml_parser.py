"""XML parser: extract text with tag names as structural markers.

Design decisions:
- xml.etree.ElementTree (stdlib, no dependencies) over lxml for lighter footprint
- Namespace URI stripping: {http://www.w3.org/2005/Atom}title → title
  Rationale: namespace prefixes vary between documents (atom:, dc:, xhtml:) and add
  noise without retrieval value. The local tag name is the meaningful structural marker.
- Leaf-node text formatted as "[tag_name]: text" to preserve both content and structure
- Malformed XML falls back to regex-based raw text extraction — better to get something
  searchable than to fail entirely on a slightly invalid document
"""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

# Strip namespace prefix from tag names: {http://...}tag -> tag
_NS_RE = re.compile(r"\{[^}]+\}")


def _local_tag(tag: str) -> str:
    """Return tag name without XML namespace URI."""
    return _NS_RE.sub("", tag)


def _collect_leaf_text(element: ET.Element, lines: list) -> None:
    """Recursively collect text from leaf nodes as '[tag]: text'."""
    children = list(element)
    text = (element.text or "").strip()
    tail = (element.tail or "").strip()

    if not children:
        combined = " ".join(part for part in (text, tail) if part).strip()
        if combined:
            lines.append(f"[{_local_tag(element.tag)}]: {combined}")
        return

    if text:
        lines.append(f"[{_local_tag(element.tag)}]: {text}")

    for child in children:
        _collect_leaf_text(child, lines)


def _fallback_raw_text(path: Path) -> str:
    """Last resort: strip tags with regex when XML is malformed."""
    raw = path.read_bytes().decode("utf-8", errors="replace")
    # Remove XML declarations and tags crudely
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    logger.warning("Used raw fallback extraction for malformed XML: %s", path)
    return text


def extract_xml(file_path: str) -> str:
    """Extract text from XML preserving tag names as structural markers.

    Uses xml.etree.ElementTree. Text from leaf nodes formatted as '[tag_name]: text'.
    Handles common namespaces by stripping URI prefixes.
    Falls back to raw text extraction if XML is malformed.

    Args:
        file_path: Path to the XML file.

    Returns:
        Structured plain text.
    """
    path = Path(file_path)
    lines: list = []

    try:
        tree = ET.parse(str(path))
        root = tree.getroot()
        _collect_leaf_text(root, lines)
    except ET.ParseError as e:
        logger.error("XML parse error for %s: %s", file_path, e)
        return _fallback_raw_text(path)

    text = "\n".join(lines).strip()
    if not text:
        logger.warning("No text extracted from XML: %s", file_path)
    return text
