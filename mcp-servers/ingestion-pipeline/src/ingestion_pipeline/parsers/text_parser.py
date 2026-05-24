"""Plain text and markdown parser."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(file_path: str) -> str:
    """Extract text from a plain text or markdown file.

    Tries UTF-8 then latin-1 then cp1252 encoding.
    """
    path = Path(file_path)
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    # Last resort: read as bytes and decode with replacement
    return path.read_bytes().decode("utf-8", errors="replace")


def extract_markdown(file_path: str) -> str:
    """Extract text from a markdown file."""
    return extract_text(file_path)
