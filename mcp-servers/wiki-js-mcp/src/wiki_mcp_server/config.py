"""Configuration and logging for Wiki.js MCP server."""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    WIKIJS_API_URL: str = Field(default="http://localhost:3000")
    WIKIJS_TOKEN: Optional[str] = Field(default=None)
    WIKIJS_API_KEY: Optional[str] = Field(default=None)
    WIKIJS_USERNAME: Optional[str] = Field(default=None)
    WIKIJS_PASSWORD: Optional[str] = Field(default=None)
    WIKIJS_MCP_DB: str = Field(default="./wikijs_mappings.db")
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: str = Field(default="wikijs_mcp.log")
    REPOSITORY_ROOT: str = Field(default="./")
    DEFAULT_SPACE_NAME: str = Field(default="Documentation")

    MCP_HOST: str = Field(default="0.0.0.0")
    MCP_PORT: int = Field(default=8000)
    MCP_TRANSPORT: str = Field(default="sse")

    # Qdrant vector database (v3 — replaces embedded vector engine)
    QDRANT_URL: str = Field(default="http://qdrant-db:6334")
    QDRANT_COLLECTION_WIKI_PAGES: str = Field(default="wiki_pages")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def token(self) -> Optional[str]:
        return self.WIKIJS_TOKEN or self.WIKIJS_API_KEY


settings = Settings()

_log_dir = os.path.dirname(settings.LOG_FILE)
if _log_dir:
    os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
