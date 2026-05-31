"""SQLite tracking for enrichment runs."""

import datetime
import json
import os

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

ENRICHMENT_DB_PATH = os.environ.get("ENRICHMENT_DB", "/data/enrichment.db")


class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False)
    document_id = Column(String(64), nullable=False, index=True)
    strategy = Column(String(32), nullable=False)
    status = Column(String(32), default="pending")
    llm_calls = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    log_entries = Column(Text, default="[]")
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


engine = create_engine(f"sqlite:///{ENRICHMENT_DB_PATH}")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Return a new SQLAlchemy session."""
    return SessionLocal()


def serialize_logs(log_entries: list) -> str:
    """Serialize log entries list to JSON string for storage."""
    return json.dumps(log_entries, default=str)
