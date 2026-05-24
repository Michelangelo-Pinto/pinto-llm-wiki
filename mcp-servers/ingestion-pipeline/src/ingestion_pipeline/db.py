"""SQLite database for ingestion tracking and idempotency."""

import datetime
import os

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

INGESTION_DB_PATH = os.environ.get("INGESTION_DB", "/data/ingestion.db")


class IngestedDocument(Base):
    __tablename__ = "ingested_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(64), unique=True, nullable=False)
    source_file = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size_bytes = Column(Integer)
    status = Column(String, default="pending")
    chunks_created = Column(Integer, default=0)
    error_message = Column(Text)
    content_hash = Column(String(64), unique=True, nullable=False)
    ingested_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(64), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_hash = Column(String(64), nullable=False)
    page_number = Column(Integer)
    section_title = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_doc_chunk"),
    )


class PageChunkReference(Base):
    __tablename__ = "page_chunk_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wiki_page_id = Column(Integer, nullable=False)
    chunk_id = Column(Integer, nullable=False)
    document_id = Column(String(64), nullable=False)
    linked_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("wiki_page_id", "chunk_id", name="uq_page_chunk"),
    )


engine = create_engine(f"sqlite:///{INGESTION_DB_PATH}")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get a new database session."""
    return SessionLocal()
