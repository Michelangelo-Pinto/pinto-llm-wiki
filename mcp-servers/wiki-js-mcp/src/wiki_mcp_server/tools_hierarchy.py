"""Wiki.js MCP tools - tools_hierarchy."""

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

from wiki_mcp_server.tools_pages import wikijs_create_page
from wiki_mcp_server.tools_files import wikijs_generate_file_overview, wikijs_link_file_to_page
@mcp.tool()
async def wikijs_create_repo_structure(repo_name: str, description: str = None, sections: List[str] = None) -> str:
    """
    Create a complete repository documentation structure with nested pages.
    
    Args:
        repo_name: Repository name (will be the root page)
        description: Repository description
        sections: List of main sections to create (e.g., ["Overview", "API", "Components", "Deployment"])
    
    Returns:
        JSON string with created structure details
    """
    try:
        # Default sections if none provided
        if not sections:
            sections = ["Overview", "Getting Started", "Architecture", "API Reference", "Development", "Deployment"]
        
        # Create root repository page
        root_content = f"""# {repo_name}

{description or f'Documentation for the {repo_name} repository.'}

## Repository Structure

This documentation is organized into the following sections:

"""
        
        for section in sections:
            root_content += f"- [{section}]({slugify(repo_name)}/{slugify(section)})\n"
        
        root_content += f"""

## Quick Links

- [Repository Overview]({slugify(repo_name)}/overview)
- [Getting Started Guide]({slugify(repo_name)}/getting-started)
- [API Documentation]({slugify(repo_name)}/api-reference)

---
*This documentation structure was created by the Wiki.js MCP server.*
"""
        
        # Create root page
        root_result = await wikijs_create_page(repo_name, root_content)
        root_data = json.loads(root_result)
        
        if "error" in root_data:
            return json.dumps({"error": f"Failed to create root page: {root_data['error']}"})
        
        root_page_id = root_data["pageId"]
        created_pages = [root_data]
        
        # Create section pages
        for section in sections:
            section_content = f"""# {section}

This is the {section.lower()} section for {repo_name}.

## Contents

*Content will be added here as the documentation grows.*

## Related Pages

- [Back to {repo_name}]({slugify(repo_name)})

---
*This page is part of the {repo_name} documentation structure.*
"""
            
            section_result = await wikijs_create_page(section, section_content, parent_id=str(root_page_id))
            section_data = json.loads(section_result)
            
            if "error" not in section_data:
                created_pages.append(section_data)
            else:
                logger.warning(f"Failed to create section '{section}': {section_data['error']}")
        
        result = {
            "repository": repo_name,
            "root_page_id": root_page_id,
            "created_pages": len(created_pages),
            "sections": sections,
            "pages": created_pages,
            "status": "created"
        }
        
        logger.info(f"Created repository structure for {repo_name} with {len(created_pages)} pages")
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Failed to create repository structure: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_create_nested_page(title: str, content: str, parent_path: str, create_parent_if_missing: bool = True) -> str:
    """
    Create a nested page using hierarchical paths (e.g., "repo/api/endpoints").
    
    Args:
        title: Page title
        content: Page content
        parent_path: Full path to parent (e.g., "my-repo/api")
        create_parent_if_missing: Create parent pages if they don't exist
    
    Returns:
        JSON string with page details
    """
    try:
        await wikijs.authenticate()
        
        # Check if parent exists
        parent_query = """
        query($path: String!) {
            pages {
                singleByPath(path: $path, locale: "en") {
                    id
                    path
                    title
                }
            }
        }
        """
        
        parent_response = await wikijs.graphql_request(parent_query, {"path": parent_path})
        parent_data = parent_response.get("data", {}).get("pages", {}).get("singleByPath")
        
        if not parent_data and create_parent_if_missing:
            # Create parent structure
            path_parts = parent_path.split("/")
            current_path = ""
            parent_id = None
            
            for i, part in enumerate(path_parts):
                if current_path:
                    current_path += f"/{part}"
                else:
                    current_path = part
                
                # Check if this level exists
                check_response = await wikijs.graphql_request(parent_query, {"path": current_path})
                existing = check_response.get("data", {}).get("pages", {}).get("singleByPath")
                
                if not existing:
                    # Create this level
                    part_title = part.replace("-", " ").title()
                    part_content = f"""# {part_title}

This is a section page for organizing documentation.

## Subsections

*Subsections will appear here as they are created.*

---
*This page was auto-created as part of the documentation hierarchy.*
"""
                    
                    create_result = await wikijs_create_page(part_title, part_content, parent_id=str(parent_id) if parent_id else "")
                    create_data = json.loads(create_result)
                    
                    if "error" not in create_data:
                        parent_id = create_data["pageId"]
                    else:
                        return json.dumps({"error": f"Failed to create parent '{current_path}': {create_data['error']}"})
                else:
                    parent_id = existing["id"]
        
        elif parent_data:
            parent_id = parent_data["id"]
        else:
            return json.dumps({"error": f"Parent path '{parent_path}' not found and create_parent_if_missing is False"})
        
        # Create the target page
        result = await wikijs_create_page(title, content, parent_id=str(parent_id))
        result_data = json.loads(result)
        
        if "error" not in result_data:
            result_data["parent_path"] = parent_path
            result_data["full_path"] = f"{parent_path}/{slugify(title)}"
        
        return json.dumps(result_data)
        
    except Exception as e:
        error_msg = f"Failed to create nested page: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_get_page_children(page_id: int = None, page_path: str = None) -> str:
    """
    Get all child pages of a given page for hierarchical navigation.
    
    Args:
        page_id: Parent page ID (optional)
        page_path: Parent page path (optional)
    
    Returns:
        JSON string with child pages list
    """
    try:
        await wikijs.authenticate()
        
        # Get the parent page first
        if page_id:
            parent_query = """
            query($id: Int!) {
                pages {
                    single(id: $id) {
                        id
                        path
                        title
                    }
                }
            }
            """
            parent_response = await wikijs.graphql_request(parent_query, {"id": page_id})
            parent_data = parent_response.get("data", {}).get("pages", {}).get("single")
        elif page_path:
            parent_query = """
            query($path: String!) {
                pages {
                    singleByPath(path: $path, locale: "en") {
                        id
                        path
                        title
                    }
                }
            }
            """
            parent_response = await wikijs.graphql_request(parent_query, {"path": page_path})
            parent_data = parent_response.get("data", {}).get("pages", {}).get("singleByPath")
        else:
            return json.dumps({"error": "Either page_id or page_path must be provided"})
        
        if not parent_data:
            return json.dumps({"error": "Parent page not found"})
        
        parent_path = parent_data["path"]
        
        # Get all pages and filter for children
        all_pages_query = """
        query {
            pages {
                list {
                    id
                    title
                    path
                    description
                    isPublished
                    updatedAt
                }
            }
        }
        """
        
        response = await wikijs.graphql_request(all_pages_query)
        all_pages = response.get("data", {}).get("pages", {}).get("list", [])
        
        # Filter for direct children (path starts with parent_path/ but no additional slashes)
        children = []
        for page in all_pages:
            page_path_str = page["path"]
            if page_path_str.startswith(f"{parent_path}/"):
                # Check if it's a direct child (no additional slashes after parent)
                remaining_path = page_path_str[len(parent_path) + 1:]
                if "/" not in remaining_path:  # Direct child
                    children.append({
                        "pageId": page["id"],
                        "title": page["title"],
                        "path": page["path"],
                        "description": page.get("description", ""),
                        "lastModified": page.get("updatedAt"),
                        "isPublished": page.get("isPublished", True)
                    })
        
        result = {
            "parent": {
                "pageId": parent_data["id"],
                "title": parent_data["title"],
                "path": parent_data["path"]
            },
            "children": children,
            "total_children": len(children)
        }
        
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Failed to get page children: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_create_documentation_hierarchy(project_name: str, file_mappings: List[Dict[str, str]], auto_organize: bool = True) -> str:
    """
    Create a complete documentation hierarchy for a project based on file structure.
    
    Args:
        project_name: Name of the project/repository
        file_mappings: List of {"file_path": "src/components/Button.tsx", "doc_path": "components/button"} mappings
        auto_organize: Automatically organize files into logical sections
    
    Returns:
        JSON string with created hierarchy details
    """
    try:
        # Auto-organize files into sections if requested
        if auto_organize:
            sections = {
                "components": [],
                "api": [],
                "utils": [],
                "services": [],
                "models": [],
                "tests": [],
                "config": [],
                "docs": []
            }
            
            for mapping in file_mappings:
                file_path = mapping["file_path"].lower()
                
                if "component" in file_path or "/components/" in file_path:
                    sections["components"].append(mapping)
                elif "api" in file_path or "/api/" in file_path or "endpoint" in file_path:
                    sections["api"].append(mapping)
                elif "util" in file_path or "/utils/" in file_path or "/helpers/" in file_path:
                    sections["utils"].append(mapping)
                elif "service" in file_path or "/services/" in file_path:
                    sections["services"].append(mapping)
                elif "model" in file_path or "/models/" in file_path or "/types/" in file_path:
                    sections["models"].append(mapping)
                elif "test" in file_path or "/tests/" in file_path or ".test." in file_path:
                    sections["tests"].append(mapping)
                elif "config" in file_path or "/config/" in file_path or ".config." in file_path:
                    sections["config"].append(mapping)
                else:
                    sections["docs"].append(mapping)
        
        # Create root project structure
        section_names = [name.title() for name, files in sections.items() if files] if auto_organize else ["Documentation"]
        
        repo_result = await wikijs_create_repo_structure(project_name, f"Documentation for {project_name}", section_names)
        repo_data = json.loads(repo_result)
        
        if "error" in repo_data:
            return repo_result
        
        created_pages = []
        created_mappings = []
        
        if auto_organize:
            # Create pages for each section
            for section_name, files in sections.items():
                if not files:
                    continue
                
                section_title = section_name.title()
                
                for file_mapping in files:
                    file_path = file_mapping["file_path"]
                    doc_path = file_mapping.get("doc_path", slugify(os.path.basename(file_path)))
                    
                    # Generate documentation content for the file
                    file_overview_result = await wikijs_generate_file_overview(file_path, target_page_id=None)
                    overview_data = json.loads(file_overview_result)
                    
                    if "error" not in overview_data:
                        created_pages.append(overview_data)
                        
                        # Create mapping
                        mapping_result = await wikijs_link_file_to_page(file_path, overview_data["pageId"], "documents")
                        mapping_data = json.loads(mapping_result)
                        
                        if "error" not in mapping_data:
                            created_mappings.append(mapping_data)
        else:
            # Create pages without auto-organization
            for file_mapping in file_mappings:
                file_path = file_mapping["file_path"]
                doc_path = file_mapping.get("doc_path", f"{project_name}/{slugify(os.path.basename(file_path))}")
                
                # Create nested page
                nested_result = await wikijs_create_nested_page(
                    os.path.basename(file_path),
                    f"# {os.path.basename(file_path)}\n\nDocumentation for {file_path}",
                    doc_path
                )
                nested_data = json.loads(nested_result)
                
                if "error" not in nested_data:
                    created_pages.append(nested_data)
                    
                    # Create mapping
                    mapping_result = await wikijs_link_file_to_page(file_path, nested_data["pageId"], "documents")
                    mapping_data = json.loads(mapping_result)
                    
                    if "error" not in mapping_data:
                        created_mappings.append(mapping_data)
        
        result = {
            "project": project_name,
            "root_structure": repo_data,
            "created_pages": len(created_pages),
            "created_mappings": len(created_mappings),
            "auto_organized": auto_organize,
            "sections": list(sections.keys()) if auto_organize else ["manual"],
            "pages": created_pages[:10],  # Limit output
            "mappings": created_mappings[:10],  # Limit output
            "status": "completed"
        }
        
        logger.info(f"Created documentation hierarchy for {project_name}: {len(created_pages)} pages, {len(created_mappings)} mappings")
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Failed to create documentation hierarchy: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
