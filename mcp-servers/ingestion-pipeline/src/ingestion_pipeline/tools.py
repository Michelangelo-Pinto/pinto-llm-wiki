"""MCP tools for the ingestion pipeline.

Pipeline: detect → extract → chunk → embed → upsert → track (SQLite).

Payload architecture — 5-layer design:
    Layer 1 (core):     Populated here — document_id, chunk_index, text, chunk_hash
    Layer 2 (routing):  null placeholders — populated by agent pre-ingestion or enrichment
    Layer 3 (document): empty dict — populated by enrichment (doc-level metadata)
    Layer 4 (chunk):    empty dict — populated by enrichment (per-chunk heuristics)
    Layer 5 (references): empty dict — populated by enrichment (cross-references)

Why 5 separate layers instead of flat fields:
- Layer separation allows independent population: the agent can fill routing metadata
  without touching document/chunk/references fields
- Enrichment can run conditionally (skip/basic/full) and only populate the layers
  appropriate for the chosen strategy
- Qdrant filter performance: nested key filters (routing.category) are efficient
  because they target a specific sub-object, not the entire payload
- Backward compatibility: legacy flat fields (document_id, text, etc.) are
  duplicated at the payload root so existing filters continue to work

Idempotency: content hash (SHA-256) prevents duplicate ingestion. force=True
clears existing data and re-ingests from scratch.
"""

import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient, models

from .chunker import chunk_document
from .db import DocumentChunk, IngestedDocument, get_db
from .detector import detect_document_type
from .embedder import embed_chunks
from .parsers.pdf_parser import extract_pdf_hybrid
from .parsers.text_parser import extract_text
from .parsers.html_parser import extract_html
from .parsers.json_parser import extract_json
from .parsers.xml_parser import extract_xml
from .parsers.epub_parser import extract_epub
from .payload import build_chunk_payload, chunk_source_type

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = os.environ.get("QDRANT_COLLECTION_DOCUMENTS", "documents")


def _get_qdrant() -> QdrantClient:
    url = os.environ.get("QDRANT_URL", "http://qdrant-db:6334")
    return QdrantClient(url=url)


def _file_hash(file_path: str) -> str:
    """SHA-256 hash of file contents for dedup."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_detect_type(file_path: str) -> str:
    """Detect the type of a document file.

    Returns classification including whether OCR is needed.
    """
    if not Path(file_path).exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    try:
        result = detect_document_type(file_path)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def ingest_document(
    file_path: str,
    collection: str = DEFAULT_COLLECTION,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
    force: bool = False,
) -> str:
    """Ingest a single document: detect type → extract text → chunk → embed → upsert Qdrant.

    Idempotent via content hash: re-ingestion of the same file is skipped
    unless force=True.
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        # Check for duplicate
        content_hash = _file_hash(str(path))
        db = get_db()
        try:
            existing = db.query(IngestedDocument).filter(
                IngestedDocument.content_hash == content_hash
            ).first()
            if existing and not force:
                return json.dumps({
                    "status": "skipped",
                    "reason": "Already ingested (use force=True to re-ingest)",
                    "document_id": existing.document_id,
                    "file": str(path),
                })
        finally:
            db.close()

        # Detect type
        doc_type = detect_document_type(str(path))
        subtype = doc_type.get("subtype", "unknown")

        # Extract text based on detected subtype
        if subtype == "text_pdf":
            text = extract_pdf_hybrid(str(path)).get("full_text", "")
        elif subtype == "scanned_pdf":
            text = extract_pdf_hybrid(str(path), dpi=300).get("full_text", "")
        elif subtype in ("text_docx", "mixed_docx"):
            import docx
            d = docx.Document(str(path))
            text = "\n".join(p.text for p in d.paragraphs)
        elif subtype == "html":
            text = extract_html(str(path))
        elif subtype == "json":
            text = extract_json(str(path))
        elif subtype == "xml":
            text = extract_xml(str(path))
        elif subtype == "epub":
            text = extract_epub(str(path))
        else:
            text = extract_text(str(path))

        if not text.strip():
            return json.dumps({"error": "No text extracted from document"})

        # Chunk using source-type-aware boundaries (html -> markdown headings)
        chunks = chunk_document(
            text, chunk_source_type(subtype), chunk_size, chunk_overlap
        )

        # Embed
        embeddings = embed_chunks(chunks)

        # Upsert to Qdrant
        document_id = content_hash[:16]
        client = _get_qdrant()

        points = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            payload = build_chunk_payload(
                document_id=document_id,
                chunk_index=i,
                chunk_text=chunk_text,
                source_file=str(path),
                file_type=subtype,
            )
            points.append(models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=payload,
            ))

        client.upsert(collection_name=collection, points=points)

        # Track in SQLite
        db = get_db()
        try:
            doc = IngestedDocument(
                document_id=document_id,
                source_file=str(path),
                file_type=subtype,
                file_size_bytes=path.stat().st_size,
                status="completed",
                chunks_created=len(chunks),
                content_hash=content_hash,
            )
            db.add(doc)
            db.commit()
        except Exception as e:
            logger.warning("Failed to track ingestion in SQLite: %s", e)
            db.rollback()
        finally:
            db.close()

        return json.dumps({
            "status": "completed",
            "document_id": document_id,
            "file": str(path),
            "file_type": subtype,
            "chunks_created": len(chunks),
            "needs_ocr": doc_type.get("needs_ocr", False),
        })
    except Exception as e:
        logger.error("Ingestion failed for %s: %s", file_path, e)
        return json.dumps({"error": str(e)})


def ingest_directory(
    dir_path: str,
    collection: str = DEFAULT_COLLECTION,
    recursive: bool = True,
    file_patterns: List[str] = None,
) -> str:
    """Ingest all supported documents in a directory."""
    if file_patterns is None:
        file_patterns = [
            "*.pdf", "*.docx", "*.md", "*.txt",
            "*.html", "*.htm", "*.json", "*.xml", "*.epub",
            "*.png", "*.jpg", "*.jpeg",
        ]

    path = Path(dir_path)
    if not path.exists() or not path.is_dir():
        return json.dumps({"error": f"Directory not found: {dir_path}"})

    files = []
    for pattern in file_patterns:
        if recursive:
            files.extend(path.rglob(pattern))
        else:
            files.extend(path.glob(pattern))

    results = []
    errors = []
    for f in files:
        r = json.loads(ingest_document(str(f), collection))
        if "error" in r:
            errors.append({"file": str(f), "error": r["error"]})
        else:
            results.append(r)

    return json.dumps({
        "files_processed": len(results),
        "files_failed": len(errors),
        "results": results[:50],  # Truncate for readability
        "errors": errors[:50],
    })


def ingest_get_status(document_id: Optional[str] = None) -> str:
    """Get ingestion status for one or all documents."""
    db = get_db()
    try:
        if document_id:
            doc = db.query(IngestedDocument).filter(
                IngestedDocument.document_id == document_id
            ).first()
            if not doc:
                return json.dumps({"error": f"Document not found: {document_id}"})
            return json.dumps({
                "document_id": doc.document_id,
                "source_file": doc.source_file,
                "status": doc.status,
                "chunks_created": doc.chunks_created,
                "ingested_at": str(doc.ingested_at),
            })
        else:
            docs = db.query(IngestedDocument).order_by(
                IngestedDocument.ingested_at.desc()
            ).limit(50).all()
            return json.dumps({
                "documents": [{
                    "document_id": d.document_id,
                    "source_file": d.source_file,
                    "status": d.status,
                    "chunks_created": d.chunks_created,
                } for d in docs],
            })
    finally:
        db.close()


def ingest_delete_document(document_id: str, collection: str = DEFAULT_COLLECTION) -> str:
    """Delete a document and its chunks from Qdrant and SQLite."""
    try:
        # Delete from Qdrant
        client = _get_qdrant()
        client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )]
                )
            ),
        )
        # Delete from SQLite
        db = get_db()
        try:
            db.query(IngestedDocument).filter(
                IngestedDocument.document_id == document_id
            ).delete()
            db.commit()
        finally:
            db.close()
        return json.dumps({"status": "deleted", "document_id": document_id})
    except Exception as e:
        return json.dumps({"error": str(e)})


def ingest_search_chunks(
    query: str,
    collection: str = DEFAULT_COLLECTION,
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> str:
    """Search across ingested document chunks for relevant content."""
    if not query.strip():
        return json.dumps({"error": "Query text cannot be empty"})
    try:
        from .embedder import embed_chunks
        query_embedding = embed_chunks([query])[0]
        client = _get_qdrant()

        response = client.query_points(
            collection_name=collection,
            query=query_embedding,
            limit=limit,
            with_payload=True,
        )

        items = []
        for hit in response.points:
            items.append({
                "id": hit.id,
                "score": round(hit.score, 4),
                "document_id": hit.payload.get("document_id"),
                "chunk_index": hit.payload.get("chunk_index"),
                "source_file": hit.payload.get("source_file"),
                "text": hit.payload.get("text", "")[:500],
            })

        return json.dumps({"query": query, "results": items, "count": len(items)})
    except Exception as e:
        return json.dumps({"error": str(e)})


def ingest_list_documents() -> str:
    """List all ingested documents with their status."""
    return ingest_get_status()
