"""Load and persist enrichment-config.md (YAML frontmatter hot-reload)."""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "log_level": "INFO",
    "llm_model": "gpt-4o-mini",
    "llm_temperature": 0.1,
    "llm_max_tokens": 2000,
    "cost_saving_mode": True,
    "sample_chars_for_classification": 5000,
    "max_chunks_per_batch": 20,
}

CONFIG_PATH = os.environ.get(
    "ENRICHMENT_CONFIG_PATH",
    "/app/knowledge/enrichment-config.md",
)


def _parse_frontmatter(content: str) -> Dict[str, Any]:
    """Extract YAML frontmatter between --- markers."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = yaml.safe_load(match.group(1))
        return parsed if isinstance(parsed, dict) else {}
    except yaml.YAMLError as e:
        logger.error("Invalid YAML in enrichment config: %s", e)
        return {}


def load_config() -> Dict[str, Any]:
    """Read enrichment-config.md and merge with defaults."""
    config = dict(DEFAULT_CONFIG)
    path = Path(CONFIG_PATH)
    if not path.exists():
        logger.warning("Enrichment config not found at %s; using defaults", path)
        return config
    try:
        content = path.read_text(encoding="utf-8")
        overrides = _parse_frontmatter(content)
        config.update(overrides)
    except OSError as e:
        logger.error("Failed to read enrichment config: %s", e)
    return config


def save_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update YAML frontmatter keys while preserving markdown body."""
    path = Path(CONFIG_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    content = path.read_text(encoding="utf-8")
    match = re.match(r"^(---\n.*?\n---)(.*)$", content, re.DOTALL)
    if not match:
        raise ValueError("Config file missing YAML frontmatter")

    current = _parse_frontmatter(content)
    current.update(updates)

    yaml_block = yaml.dump(current, default_flow_style=False, allow_unicode=True)
    new_content = f"---\n{yaml_block}---{match.group(2)}"
    path.write_text(new_content, encoding="utf-8")
    logger.info("Updated enrichment config: %s", list(updates.keys()))
    return current
