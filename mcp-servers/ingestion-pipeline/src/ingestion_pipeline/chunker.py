"""Section-aware recursive text chunking.

Two-phase strategy:
1. Split by structural boundaries (page breaks for PDF, heading boundaries for markdown)
2. Recursively split oversized sections at sentence boundaries.

Parameters:
- Target: 1500 chars (~500 tokens for all-MiniLM-L6-v2)
- Overlap: 200 chars (15%)
- Hard cap: 2500 chars
"""

import re
from typing import List

SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+')
HEADING_BOUNDARY = re.compile(r'^#{1,6}\s', re.MULTILINE)
PAGE_BOUNDARY = "\f"  # Form feed character


def chunk_document(text: str, source_type: str = "text", 
                   chunk_size: int = 1500, chunk_overlap: int = 200,
                   max_chunk_size: int = 2500) -> List[str]:
    """Split document text into overlapping chunks for embedding.

    Args:
        text: Full document text.
        source_type: Type hint for boundary detection ('pdf', 'markdown', 'docx', 'text').
        chunk_size: Target character count per chunk.
        chunk_overlap: Overlap between consecutive chunks in characters.
        max_chunk_size: Hard maximum for any single chunk.

    Returns:
        List of chunk strings.
    """
    # Phase 1: Split by structural boundaries
    if source_type in ("pdf", "docx"):
        sections = text.split(PAGE_BOUNDARY)
    elif source_type == "markdown":
        sections = _split_by_headings(text)
    else:
        sections = text.split("\n\n")

    # Phase 2: Recursively split oversized sections
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            chunks.extend(_split_section(section, chunk_size, chunk_overlap, max_chunk_size))

    return chunks


def _split_by_headings(text: str) -> List[str]:
    """Split markdown text at heading boundaries."""
    sections = []
    matches = list(HEADING_BOUNDARY.finditer(text))
    if not matches:
        return text.split("\n\n")

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[start:end])

    # Include text before the first heading
    if matches and matches[0].start() > 0:
        sections.insert(0, text[:matches[0].start()])

    return sections


def _split_section(text: str, chunk_size: int, overlap: int, max_size: int) -> List[str]:
    """Recursively split oversized text at sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    sentences = SENTENCE_BOUNDARY.split(text)
    if len(sentences) == 1:
        # No sentence boundaries found, force split at chunk_size
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]

    chunks = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) <= chunk_size:
            current += (" " if current else "") + sentence
        else:
            if len(current) > max_size:
                # Force split oversized chunk
                chunks.append(current[:chunk_size])
                chunks.append(current[chunk_size - overlap:])
            else:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks
