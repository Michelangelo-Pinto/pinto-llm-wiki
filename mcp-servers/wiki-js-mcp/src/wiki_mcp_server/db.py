"""SQLite database models and session for file-to-page mappings."""

import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from wiki_mcp_server.config import settings

Base = declarative_base()


class FileMapping(Base):
    __tablename__ = "file_mappings"

    id = Column(Integer, primary_key=True)
    file_path = Column(String, unique=True, nullable=False)
    page_id = Column(Integer, nullable=False)
    relationship_type = Column(String, nullable=False)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)
    file_hash = Column(String)
    repository_root = Column(String, default="")
    space_name = Column(String, default="")


class RepositoryContext(Base):
    __tablename__ = "repository_contexts"

    id = Column(Integer, primary_key=True)
    root_path = Column(String, unique=True, nullable=False)
    space_name = Column(String, nullable=False)
    space_id = Column(Integer)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)


class BacklinkIndex(Base):
    __tablename__ = "backlinks"
    __table_args__ = (
        Index("idx_backlinks_source", "source_page_id"),
        Index("idx_backlinks_target", "target_page_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_page_id = Column(Integer, nullable=False)
    target_page_id = Column(Integer, nullable=True)
    target_path = Column(String, nullable=False)
    link_text = Column(String, default="")
    position = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)


engine = create_engine(f"sqlite:///{settings.WIKIJS_MCP_DB}")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session."""
    return SessionLocal()
