"""HTML parser: extract clean structured text for chunking.

Design decisions:
- BeautifulSoup + lxml for robust parsing of real-world HTML (tolerant of malformed markup)
- Tag-based structural conversion to markdown (h1-h6 → headings, li → bullets)
- Encoding fallback chain (UTF-8 → latin-1 → cp1252 → replacement) for non-standard encodings
- Strip-tag set removes non-content elements (nav, footer, scripts) that would pollute embeddings
- Block-level elements (p, div, section) emit paragraph breaks for clean chunk boundaries
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Elements whose entire content is discarded — these contain no semantic value for retrieval
_STRIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "iframe", "svg"}

# Markdown heading conversion: h1 → #, h2 → ##, etc.
_HEADING_PREFIX = {f"h{i}": "#" * i for i in range(1, 7)}


def _read_with_encoding_fallback(path: Path) -> str:
    """Read file trying common encodings before replacement fallback."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    logger.warning("HTML encoding fallback to UTF-8 replacement for %s", path)
    return path.read_bytes().decode("utf-8", errors="replace")


def _element_to_text(element, depth: int = 0) -> str:
    """Recursively convert a BeautifulSoup element to plain text."""
    from bs4 import NavigableString, Tag

    if isinstance(element, NavigableString):
        text = str(element).strip()
        return text if text else ""

    if not isinstance(element, Tag):
        return ""

    tag = element.name.lower() if element.name else ""

    if tag in _STRIP_TAGS:
        return ""

    # Block-level formatting
    if tag in _HEADING_PREFIX:
        inner = " ".join(_element_to_text(c, depth + 1) for c in element.children).strip()
        if inner:
            return f"\n\n{_HEADING_PREFIX[tag]} {inner}\n\n"
        return ""

    if tag == "li":
        inner = " ".join(_element_to_text(c, depth + 1) for c in element.children).strip()
        return f"- {inner}\n" if inner else ""

    if tag in ("pre", "code"):
        inner = element.get_text("\n", strip=False)
        if inner.strip():
            indented = "\n".join(f"    {line}" for line in inner.splitlines())
            return f"\n{indented}\n"
        return ""

    if tag == "br":
        return "\n"

    if tag in ("p", "div", "section", "article", "blockquote", "tr"):
        inner = " ".join(_element_to_text(c, depth + 1) for c in element.children).strip()
        return f"\n\n{inner}\n\n" if inner else ""

    # Inline / unknown: recurse without extra spacing
    return " ".join(_element_to_text(c, depth + 1) for c in element.children)


def extract_html(file_path: str) -> str:
    """Extract clean text from HTML preserving heading/paragraph structure.

    Encoding fallback: UTF-8 -> latin-1 -> cp1252 -> UTF-8 replacement.
    Strips script, style, nav, footer, HTML comments.
    Converts h1-h6 to markdown headings, li to bullet points.
    Preserves pre/code blocks as indented text.

    Args:
        file_path: Path to the HTML file.

    Returns:
        Structured plain text string suitable for chunking.
    """
    from bs4 import BeautifulSoup, Comment

    path = Path(file_path)
    raw = _read_with_encoding_fallback(path)

    soup = BeautifulSoup(raw, "lxml")

    # Remove comments and strip tags
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    body = soup.body if soup.body else soup
    text = _element_to_text(body)
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        logger.warning("No text extracted from HTML file: %s", file_path)
    return text
