"""Utility functions for file hashing, markdown, and code analysis."""

import ast
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional

import markdown

from wiki_mcp_server.config import logger


def get_file_hash(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return ""


def markdown_to_html(content: str) -> str:
    md = markdown.Markdown(extensions=["codehilite", "fenced_code", "tables"])
    return md.convert(content)


def find_repository_root(start_path: Optional[str] = None) -> Optional[str]:
    if start_path is None:
        start_path = os.getcwd()

    current_path = Path(start_path).resolve()
    for path in [current_path] + list(current_path.parents):
        if (path / ".git").exists():
            return str(path)
        if (path / ".wikijs_mcp").exists():
            return str(path)
    return str(current_path)


def extract_code_structure(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)
        structure: Dict[str, Any] = {
            "classes": [],
            "functions": [],
            "imports": [],
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                structure["classes"].append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "docstring": ast.get_docstring(node),
                    }
                )
            elif isinstance(node, ast.FunctionDef):
                structure["functions"].append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "docstring": ast.get_docstring(node),
                    }
                )
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        structure["imports"].append(alias.name)
                else:
                    module = node.module or ""
                    for alias in node.names:
                        structure["imports"].append(f"{module}.{alias.name}")

        return structure
    except Exception as e:
        logger.error("Error parsing %s: %s", file_path, e)
        return {"classes": [], "functions": [], "imports": []}
