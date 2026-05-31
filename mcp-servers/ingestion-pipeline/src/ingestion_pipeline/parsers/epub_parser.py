"""EPUB parser: extract chapter text from EPUB archives (ZIP + XHTML).

Design decisions:
- EPUB is a ZIP archive containing XHTML/HTML content files organized by an OPF manifest
- Spine order from the OPF file determines chapter sequence (preserves book structure)
- Dual namespace fallback in container.xml parsing: tries OPF namespace first,
  then falls back to wildcard namespace — real-world EPUBs vary in namespace usage
- If spine parsing fails entirely, falls back to all HTML/XHTML files in the archive
  sorted alphabetically — imperfect but ensures content extraction succeeds
- BeautifulSoup strips script/style from each chapter before text extraction
- Chapter markers ([Chapter: 1]) are injected for structural awareness during chunking
"""

import logging
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_content_paths(epub_zip: zipfile.ZipFile) -> list:
    """Locate spine content file paths via META-INF/container.xml."""
    container_xml = epub_zip.read("META-INF/container.xml")
    root = ET.fromstring(container_xml)
    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    opf_path = root.find(".//c:rootfile", ns)
    if opf_path is None:
        # Fallback without namespace
        opf_path = root.find(".//{*}rootfile")
    if opf_path is None:
        raise ValueError("Cannot find rootfile in EPUB container.xml")

    opf_file = opf_path.get("full-path", "")
    opf_dir = str(Path(opf_file).parent) if "/" in opf_file else ""

    opf_root = ET.fromstring(epub_zip.read(opf_file))
    opf_ns = {"opf": "http://www.idpf.org/2007/opf"}

    # Map id -> href from manifest
    id_to_href = {}
    for item in opf_root.findall(".//opf:manifest/opf:item", opf_ns):
        item_id = item.get("id")
        href = item.get("href")
        if item_id and href:
            id_to_href[item_id] = href

    # Spine order
    content_paths = []
    for itemref in opf_root.findall(".//opf:spine/opf:itemref", opf_ns):
        ref_id = itemref.get("idref")
        if ref_id and ref_id in id_to_href:
            href = id_to_href[ref_id]
            full_path = f"{opf_dir}/{href}" if opf_dir else href
            content_paths.append(full_path.replace("\\", "/"))

    if not content_paths:
        # Fallback: all HTML/XHTML in archive
        content_paths = [
            n for n in epub_zip.namelist()
            if n.lower().endswith((".xhtml", ".html", ".htm"))
            and not n.startswith("META-INF/")
        ]

    return content_paths


def _html_to_plain(html_bytes: bytes) -> str:
    """Extract plain text from XHTML/HTML bytes using BeautifulSoup."""
    from bs4 import BeautifulSoup

    raw = html_bytes.decode("utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def extract_epub(file_path: str) -> str:
    """Extract text from EPUB by reading spine content files.

    Opens EPUB as ZIP, reads META-INF/container.xml for OPF path,
    follows spine order, extracts text from each XHTML/HTML chapter.

    Args:
        file_path: Path to the .epub file.

    Returns:
        Concatenated chapter text with [Chapter: N] markers.
    """
    path = Path(file_path)
    chapters: list = []

    with zipfile.ZipFile(str(path), "r") as zf:
        try:
            content_paths = _find_content_paths(zf)
        except Exception as e:
            logger.error("Failed to parse EPUB structure for %s: %s", file_path, e)
            content_paths = [
                n for n in zf.namelist()
                if n.lower().endswith((".xhtml", ".html", ".htm"))
            ]

        for i, content_path in enumerate(content_paths, start=1):
            try:
                html_bytes = zf.read(content_path)
                chapter_text = _html_to_plain(html_bytes)
                if chapter_text.strip():
                    chapters.append(f"[Chapter: {i}]\n{chapter_text}")
            except KeyError:
                logger.warning("Missing EPUB content file: %s", content_path)
            except Exception as e:
                logger.warning("Failed to extract EPUB chapter %s: %s", content_path, e)

    text = "\n\n".join(chapters).strip()
    if not text:
        logger.warning("No text extracted from EPUB: %s", file_path)
    return text
