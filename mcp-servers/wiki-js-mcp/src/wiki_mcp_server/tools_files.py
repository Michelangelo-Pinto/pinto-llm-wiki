"""Wiki.js MCP tools - tools_files."""

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

from wiki_mcp_server.tools_pages import wikijs_create_page, wikijs_get_page, wikijs_update_page
@mcp.tool()
async def wikijs_link_file_to_page(file_path: str, page_id: int, relationship: str = "documents") -> str:
    """
    Persist link between code file and Wiki.js page in local database.
    
    Args:
        file_path: Path to the source file
        page_id: Wiki.js page ID
        relationship: Type of relationship (documents, references, etc.)
    
    Returns:
        JSON string with link status
    """
    try:
        db = get_db()
        
        # Calculate file hash
        file_hash = get_file_hash(file_path)
        repo_root = find_repository_root(file_path)
        
        # Create or update mapping
        mapping = db.query(FileMapping).filter(FileMapping.file_path == file_path).first()
        if mapping:
            mapping.page_id = page_id
            mapping.relationship_type = relationship
            mapping.file_hash = file_hash
            mapping.last_updated = datetime.datetime.utcnow()
        else:
            mapping = FileMapping(
                file_path=file_path,
                page_id=page_id,
                relationship_type=relationship,
                file_hash=file_hash,
                repository_root=repo_root or ""
            )
            db.add(mapping)
        
        db.commit()
        
        result = {
            "linked": True,
            "file_path": file_path,
            "page_id": page_id,
            "relationship": relationship
        }
        
        logger.info(f"Linked file {file_path} to page {page_id}")
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Failed to link file to page: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_sync_file_docs(file_path: str, change_summary: str, snippet: str = None) -> str:
    """
    Sync a code change to the linked Wiki.js page.
    
    Args:
        file_path: Path to the changed file
        change_summary: Summary of changes made
        snippet: Code snippet showing changes (optional)
    
    Returns:
        JSON string with sync status
    """
    try:
        db = get_db()
        
        # Look up page mapping
        mapping = db.query(FileMapping).filter(FileMapping.file_path == file_path).first()
        if not mapping:
            return json.dumps({"error": f"No page mapping found for {file_path}"})
        
        # Get current page content
        page_response = await wikijs_get_page(page_id=mapping.page_id)
        page_data = json.loads(page_response)
        
        if "error" in page_data:
            return json.dumps({"error": f"Failed to get page: {page_data['error']}"})
        
        # Append change summary to page content
        current_content = page_data.get("content", "")
        
        update_section = f"\n\n## Recent Changes\n\n**{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}**: {change_summary}\n"
        if snippet:
            update_section += f"\n```\n{snippet}\n```\n"
        
        new_content = current_content + update_section
        
        # Update the page
        update_response = await wikijs_update_page(mapping.page_id, content=new_content)
        update_data = json.loads(update_response)
        
        if "error" in update_data:
            return json.dumps({"error": f"Failed to update page: {update_data['error']}"})
        
        # Update file hash
        mapping.file_hash = get_file_hash(file_path)
        mapping.last_updated = datetime.datetime.utcnow()
        db.commit()
        
        result = {
            "updated": True,
            "file_path": file_path,
            "page_id": mapping.page_id,
            "change_summary": change_summary
        }
        
        logger.info(f"Synced changes from {file_path} to page {mapping.page_id}")
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Failed to sync file docs: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_generate_file_overview(
    file_path: str, 
    include_functions: bool = True, 
    include_classes: bool = True,
    include_dependencies: bool = True,
    include_examples: bool = False,
    target_page_id: int = None
) -> str:
    """
    Create or update a structured overview page for a file.
    
    Args:
        file_path: Path to the source file
        include_functions: Include function documentation
        include_classes: Include class documentation
        include_dependencies: Include import/dependency information
        include_examples: Include usage examples
        target_page_id: Specific page ID to update (optional)
    
    Returns:
        JSON string with overview page details
    """
    try:
        if not os.path.exists(file_path):
            return json.dumps({"error": f"File not found: {file_path}"})
        
        # Extract code structure
        structure = extract_code_structure(file_path)
        
        # Generate documentation content
        content_parts = [f"# {os.path.basename(file_path)} Overview\n"]
        content_parts.append(f"**File Path**: `{file_path}`\n")
        content_parts.append(f"**Last Updated**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        
        if include_dependencies and structure['imports']:
            content_parts.append("\n## Dependencies\n")
            for imp in structure['imports']:
                content_parts.append(f"- `{imp}`")
            content_parts.append("")
        
        if include_classes and structure['classes']:
            content_parts.append("\n## Classes\n")
            for cls in structure['classes']:
                content_parts.append(f"### {cls['name']} (Line {cls['line']})\n")
                if cls['docstring']:
                    content_parts.append(f"{cls['docstring']}\n")
        
        if include_functions and structure['functions']:
            content_parts.append("\n## Functions\n")
            for func in structure['functions']:
                content_parts.append(f"### {func['name']}() (Line {func['line']})\n")
                if func['docstring']:
                    content_parts.append(f"{func['docstring']}\n")
        
        if include_examples:
            content_parts.append("\n## Usage Examples\n")
            content_parts.append("```python\n# Add usage examples here\n```\n")
        
        content = "\n".join(content_parts)
        
        # Create or update page
        if target_page_id:
            # Update existing page
            response = await wikijs_update_page(target_page_id, content=content)
            result_data = json.loads(response)
            if "error" not in result_data:
                result_data["action"] = "updated"
        else:
            # Create new page
            title = f"{os.path.basename(file_path)} Documentation"
            response = await wikijs_create_page(title, content)
            result_data = json.loads(response)
            if "error" not in result_data:
                result_data["action"] = "created"
                # Link file to new page
                if "pageId" in result_data:
                    await wikijs_link_file_to_page(file_path, result_data["pageId"], "documents")
        
        logger.info(f"Generated overview for {file_path}")
        return json.dumps(result_data)
        
    except Exception as e:
        error_msg = f"Failed to generate file overview: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_bulk_update_project_docs(
    summary: str, 
    affected_files: List[str], 
    context: str,
    auto_create_missing: bool = True
) -> str:
    """
    Batch update pages for large changes across multiple files.
    
    Args:
        summary: Overall project change summary
        affected_files: List of file paths that were changed
        context: Additional context about the changes
        auto_create_missing: Create pages for files without mappings
    
    Returns:
        JSON string with bulk update results
    """
    try:
        db = get_db()
        results = {
            "updated_pages": [],
            "created_pages": [],
            "errors": []
        }
        
        # Process each affected file
        for file_path in affected_files:
            try:
                # Check if file has a mapping
                mapping = db.query(FileMapping).filter(FileMapping.file_path == file_path).first()
                
                if mapping:
                    # Update existing page
                    sync_response = await wikijs_sync_file_docs(
                        file_path, 
                        f"Bulk update: {summary}", 
                        context
                    )
                    sync_data = json.loads(sync_response)
                    if "error" not in sync_data:
                        results["updated_pages"].append({
                            "file_path": file_path,
                            "page_id": mapping.page_id
                        })
                    else:
                        results["errors"].append({
                            "file_path": file_path,
                            "error": sync_data["error"]
                        })
                
                elif auto_create_missing:
                    # Create new overview page
                    overview_response = await wikijs_generate_file_overview(file_path)
                    overview_data = json.loads(overview_response)
                    if "error" not in overview_data and "pageId" in overview_data:
                        results["created_pages"].append({
                            "file_path": file_path,
                            "page_id": overview_data["pageId"]
                        })
                    else:
                        results["errors"].append({
                            "file_path": file_path,
                            "error": overview_data.get("error", "Failed to create page")
                        })
                
            except Exception as e:
                results["errors"].append({
                    "file_path": file_path,
                    "error": str(e)
                })
        
        results["summary"] = {
            "total_files": len(affected_files),
            "updated": len(results["updated_pages"]),
            "created": len(results["created_pages"]),
            "errors": len(results["errors"])
        }
        
        logger.info(f"Bulk update completed: {results['summary']}")
        return json.dumps(results)
        
    except Exception as e:
        error_msg = f"Bulk update failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
