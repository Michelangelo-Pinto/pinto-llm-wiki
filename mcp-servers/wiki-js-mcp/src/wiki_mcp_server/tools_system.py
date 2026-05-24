"""Wiki.js MCP tools - tools_system."""

import datetime
import json
import os
from typing import Any, Dict, List, Optional

from slugify import slugify

from wiki_mcp_server.client import wikijs
from wiki_mcp_server.config import logger, settings
from wiki_mcp_server.db import FileMapping, RepositoryContext, get_db
from wiki_mcp_server.server import mcp
from wiki_mcp_server.utils import (
    extract_code_structure,
    find_repository_root,
    get_file_hash,
)

@mcp.tool()
async def wikijs_manage_collections(collection_name: str, description: str = None, space_ids: List[int] = None) -> str:
    """
    Manage Wiki.js collections (groups of spaces/pages).
    Note: This is a placeholder as Wiki.js collections API may vary by version.
    
    Args:
        collection_name: Name of the collection
        description: Collection description
        space_ids: List of space IDs to include
    
    Returns:
        JSON string with collection details
    """
    try:
        # This is a conceptual implementation
        # Actual Wiki.js API for collections may differ
        result = {
            "collection_name": collection_name,
            "description": description,
            "space_ids": space_ids or [],
            "status": "managed",
            "note": "Collection management depends on Wiki.js version and configuration"
        }
        
        logger.info(f"Managed collection: {collection_name}")
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Failed to manage collection: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_connection_status() -> str:
    """
    Check the status of the Wiki.js connection and authentication.
    
    Returns:
        JSON string with connection status
    """
    try:
        auth_success = await wikijs.authenticate()
        
        if auth_success:
            # Test with a simple API call
            response = await wikijs.graphql_request("query { pages { list { id } } }")
            
            result = {
                "connected": True,
                "authenticated": True,
                "api_url": settings.WIKIJS_API_URL,
                "auth_method": "token" if settings.token else "session",
                "status": "healthy"
            }
        else:
            result = {
                "connected": False,
                "authenticated": False,
                "api_url": settings.WIKIJS_API_URL,
                "status": "authentication_failed"
            }
        
        return json.dumps(result)
        
    except Exception as e:
        result = {
            "connected": False,
            "authenticated": False,
            "api_url": settings.WIKIJS_API_URL,
            "error": str(e),
            "status": "connection_failed"
        }
        return json.dumps(result)

@mcp.tool()
async def wikijs_repository_context() -> str:
    """
    Show current repository context and Wiki.js organization.
    
    Returns:
        JSON string with repository context
    """
    try:
        repo_root = find_repository_root()
        db = get_db()
        
        # Get repository context from database
        context = db.query(RepositoryContext).filter(
            RepositoryContext.root_path == repo_root
        ).first()
        
        # Get file mappings for this repository
        mappings = db.query(FileMapping).filter(
            FileMapping.repository_root == repo_root
        ).all()
        
        result = {
            "repository_root": repo_root,
            "space_name": context.space_name if context else settings.DEFAULT_SPACE_NAME,
            "space_id": context.space_id if context else None,
            "mapped_files": len(mappings),
            "mappings": [
                {
                    "file_path": m.file_path,
                    "page_id": m.page_id,
                    "relationship": m.relationship_type,
                    "last_updated": m.last_updated.isoformat() if m.last_updated else None
                }
                for m in mappings[:10]  # Limit to first 10 for brevity
            ]
        }
        
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Failed to get repository context: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
