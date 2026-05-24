"""Wiki.js MCP tools - tools_deletion."""

import datetime
import fnmatch
import json
import os
from typing import Any, Dict, List, Optional

from slugify import slugify

from wiki_mcp_server.client import wikijs
from wiki_mcp_server.config import logger, settings
from wiki_mcp_server.db import BacklinkIndex, FileMapping, RepositoryContext, get_db
from wiki_mcp_server.server import mcp
from wiki_mcp_server.utils import (
    extract_code_structure,
    find_repository_root,
    get_file_hash,
)


@mcp.tool()
async def wikijs_delete_page(page_id: int = None, page_path: str = None, remove_file_mapping: bool = True) -> str:
    """
    Delete a specific page from Wiki.js.
    
    Args:
        page_id: Page ID to delete (optional)
        page_path: Page path to delete (optional)
        remove_file_mapping: Also remove file-to-page mapping from local database
    
    Returns:
        JSON string with deletion status
    """
    try:
        await wikijs.authenticate()
        
        # Get page info first
        if page_id:
            get_query = """
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
            get_response = await wikijs.graphql_request(get_query, {"id": page_id})
            page_data = get_response.get("data", {}).get("pages", {}).get("single")
        elif page_path:
            get_query = """
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
            get_response = await wikijs.graphql_request(get_query, {"path": page_path})
            page_data = get_response.get("data", {}).get("pages", {}).get("singleByPath")
            if page_data:
                page_id = page_data["id"]
        else:
            return json.dumps({"error": "Either page_id or page_path must be provided"})
        
        if not page_data:
            return json.dumps({"error": "Page not found"})
        
        # Delete the page using GraphQL mutation
        delete_mutation = """
        mutation($id: Int!) {
            pages {
                delete(id: $id) {
                    responseResult {
                        succeeded
                        errorCode
                        slug
                        message
                    }
                }
            }
        }
        """
        
        response = await wikijs.graphql_request(delete_mutation, {"id": page_id})
        
        delete_result = response.get("data", {}).get("pages", {}).get("delete", {})
        response_result = delete_result.get("responseResult", {})
        
        if response_result.get("succeeded"):
            result = {
                "deleted": True,
                "pageId": page_id,
                "title": page_data["title"],
                "path": page_data["path"],
                "status": "deleted"
            }
            
            # Remove file mapping if requested
            if remove_file_mapping:
                db = get_db()
                mapping = db.query(FileMapping).filter(FileMapping.page_id == page_id).first()
                if mapping:
                    db.delete(mapping)
                    db.commit()
                    result["file_mapping_removed"] = True
                else:
                    result["file_mapping_removed"] = False
            
            logger.info(f"Deleted page: {page_data['title']} (ID: {page_id})")
            
            # Clean up backlinks: remove entries where this page is source or target
            db_backlinks = get_db()
            try:
                db_backlinks.query(BacklinkIndex).filter(
                    (BacklinkIndex.source_page_id == page_id) | (BacklinkIndex.target_page_id == page_id)
                ).delete()
                db_backlinks.commit()
            except Exception as e:
                logger.warning("Failed to clean up backlinks for deleted page %d: %s", page_id, str(e))
                db_backlinks.rollback()
            finally:
                db_backlinks.close()
            
            # Clean up file mappings associated with this page
            try:
                db_files = get_db()
                try:
                    db_files.query(FileMapping).filter(FileMapping.page_id == page_id).delete()
                    db_files.commit()
                except Exception as e:
                    logger.warning("Failed to clean up file mappings for deleted page %d: %s", page_id, str(e))
                    db_files.rollback()
                finally:
                    db_files.close()
            except Exception as e:
                logger.warning("Failed to clean up file mappings for deleted page %d: %s", page_id, str(e))

            return json.dumps(result)
        else:
            error_msg = response_result.get("message", "Unknown error")
            return json.dumps({"error": f"Failed to delete page: {error_msg}"})
        
    except Exception as e:
        error_msg = f"Failed to delete page: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_batch_delete_pages(
    page_ids: List[int] = None, 
    page_paths: List[str] = None,
    path_pattern: str = None,
    confirm_deletion: bool = False,
    remove_file_mappings: bool = True
) -> str:
    """
    Batch delete multiple pages from Wiki.js.
    
    Args:
        page_ids: List of page IDs to delete (optional)
        page_paths: List of page paths to delete (optional)
        path_pattern: Pattern to match paths (e.g., "frontend-app/*" for all pages under frontend-app)
        confirm_deletion: Must be True to actually delete pages (safety check)
        remove_file_mappings: Also remove file-to-page mappings from local database
    
    Returns:
        JSON string with batch deletion results
    """
    try:
        if not confirm_deletion:
            return json.dumps({
                "error": "confirm_deletion must be True to proceed with batch deletion",
                "safety_note": "This is a safety check to prevent accidental deletions"
            })
        
        await wikijs.authenticate()
        
        pages_to_delete = []
        
        # Collect pages by IDs
        if page_ids:
            for page_id in page_ids:
                get_query = """
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
                get_response = await wikijs.graphql_request(get_query, {"id": page_id})
                page_data = get_response.get("data", {}).get("pages", {}).get("single")
                if page_data:
                    pages_to_delete.append(page_data)
        
        # Collect pages by paths
        if page_paths:
            for page_path in page_paths:
                get_query = """
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
                get_response = await wikijs.graphql_request(get_query, {"path": page_path})
                page_data = get_response.get("data", {}).get("pages", {}).get("singleByPath")
                if page_data:
                    pages_to_delete.append(page_data)
        
        # Collect pages by pattern
        if path_pattern:
            # Get all pages and filter by pattern
            all_pages_query = """
            query {
                pages {
                    list {
                        id
                        title
                        path
                    }
                }
            }
            """
            
            response = await wikijs.graphql_request(all_pages_query)
            all_pages = response.get("data", {}).get("pages", {}).get("list", [])
            
            # Simple pattern matching (supports * wildcard)
            for page in all_pages:
                if fnmatch.fnmatch(page["path"], path_pattern):
                    pages_to_delete.append(page)
        
        if not pages_to_delete:
            return json.dumps({"error": "No pages found to delete"})
        
        # Remove duplicates
        unique_pages = {}
        for page in pages_to_delete:
            unique_pages[page["id"]] = page
        pages_to_delete = list(unique_pages.values())
        
        # Delete pages
        deleted_pages = []
        failed_deletions = []
        
        for page in pages_to_delete:
            try:
                delete_result = await wikijs_delete_page(
                    page_id=page["id"], 
                    remove_file_mapping=remove_file_mappings
                )
                delete_data = json.loads(delete_result)
                
                if "error" not in delete_data:
                    deleted_pages.append({
                        "pageId": page["id"],
                        "title": page["title"],
                        "path": page["path"]
                    })
                else:
                    failed_deletions.append({
                        "pageId": page["id"],
                        "title": page["title"],
                        "path": page["path"],
                        "error": delete_data["error"]
                    })
            except Exception as e:
                failed_deletions.append({
                    "pageId": page["id"],
                    "title": page["title"],
                    "path": page["path"],
                    "error": str(e)
                })
        
        result = {
            "total_found": len(pages_to_delete),
            "deleted_count": len(deleted_pages),
            "failed_count": len(failed_deletions),
            "deleted_pages": deleted_pages,
            "failed_deletions": failed_deletions,
            "status": "completed"
        }
        
        logger.info(f"Batch deletion completed: {len(deleted_pages)} deleted, {len(failed_deletions)} failed")
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Batch deletion failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_delete_hierarchy(
    root_path: str,
    delete_mode: str = "children_only",
    confirm_deletion: bool = False,
    remove_file_mappings: bool = True
) -> str:
    """
    Delete an entire page hierarchy (folder structure) from Wiki.js.
    
    Args:
        root_path: Root path of the hierarchy to delete (e.g., "frontend-app" or "frontend-app/components")
        delete_mode: Deletion mode - "children_only", "include_root", or "root_only"
        confirm_deletion: Must be True to actually delete pages (safety check)
        remove_file_mappings: Also remove file-to-page mappings from local database
    
    Returns:
        JSON string with hierarchy deletion results
    """
    try:
        if not confirm_deletion:
            return json.dumps({
                "error": "confirm_deletion must be True to proceed with hierarchy deletion",
                "safety_note": "This is a safety check to prevent accidental deletions",
                "preview_mode": "Set confirm_deletion=True to actually delete"
            })
        
        valid_modes = ["children_only", "include_root", "root_only"]
        if delete_mode not in valid_modes:
            return json.dumps({
                "error": f"Invalid delete_mode. Must be one of: {valid_modes}"
            })
        
        await wikijs.authenticate()
        
        # Get all pages to find hierarchy
        all_pages_query = """
        query {
            pages {
                list {
                    id
                    title
                    path
                }
            }
        }
        """
        
        response = await wikijs.graphql_request(all_pages_query)
        all_pages = response.get("data", {}).get("pages", {}).get("list", [])
        
        # Find root page
        root_page = None
        for page in all_pages:
            if page["path"] == root_path:
                root_page = page
                break
        
        if not root_page and delete_mode in ["include_root", "root_only"]:
            return json.dumps({"error": f"Root page not found: {root_path}"})
        
        # Find child pages
        child_pages = []
        for page in all_pages:
            page_path = page["path"]
            if page_path.startswith(f"{root_path}/"):
                child_pages.append(page)
        
        # Determine pages to delete based on mode
        pages_to_delete = []
        
        if delete_mode == "children_only":
            pages_to_delete = child_pages
        elif delete_mode == "include_root":
            pages_to_delete = child_pages + ([root_page] if root_page else [])
        elif delete_mode == "root_only":
            pages_to_delete = [root_page] if root_page else []
        
        if not pages_to_delete:
            return json.dumps({
                "message": f"No pages found to delete for path: {root_path}",
                "delete_mode": delete_mode,
                "root_found": root_page is not None,
                "children_found": len(child_pages)
            })
        
        # Sort by depth (deepest first) to avoid dependency issues
        pages_to_delete.sort(key=lambda x: x["path"].count("/"), reverse=True)
        
        # Delete pages
        deleted_pages = []
        failed_deletions = []
        
        for page in pages_to_delete:
            try:
                delete_result = await wikijs_delete_page(
                    page_id=page["id"], 
                    remove_file_mapping=remove_file_mappings
                )
                delete_data = json.loads(delete_result)
                
                if "error" not in delete_data:
                    deleted_pages.append({
                        "pageId": page["id"],
                        "title": page["title"],
                        "path": page["path"],
                        "depth": page["path"].count("/")
                    })
                else:
                    failed_deletions.append({
                        "pageId": page["id"],
                        "title": page["title"],
                        "path": page["path"],
                        "error": delete_data["error"]
                    })
            except Exception as e:
                failed_deletions.append({
                    "pageId": page["id"],
                    "title": page["title"],
                    "path": page["path"],
                    "error": str(e)
                })
        
        result = {
            "root_path": root_path,
            "delete_mode": delete_mode,
            "total_found": len(pages_to_delete),
            "deleted_count": len(deleted_pages),
            "failed_count": len(failed_deletions),
            "deleted_pages": deleted_pages,
            "failed_deletions": failed_deletions,
            "hierarchy_summary": {
                "root_page_found": root_page is not None,
                "child_pages_found": len(child_pages),
                "max_depth": max([p["path"].count("/") for p in pages_to_delete]) if pages_to_delete else 0
            },
            "status": "completed"
        }
        
        logger.info(f"Hierarchy deletion completed for {root_path}: {len(deleted_pages)} deleted, {len(failed_deletions)} failed")
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Hierarchy deletion failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_cleanup_orphaned_mappings() -> str:
    """
    Clean up file-to-page mappings for pages that no longer exist in Wiki.js.
    
    Returns:
        JSON string with cleanup results
    """
    try:
        await wikijs.authenticate()
        db = get_db()
        
        # Get all file mappings
        mappings = db.query(FileMapping).all()
        
        if not mappings:
            return json.dumps({
                "message": "No file mappings found",
                "cleaned_count": 0
            })
        
        # Check which pages still exist
        orphaned_mappings = []
        valid_mappings = []
        
        for mapping in mappings:
            try:
                get_query = """
                query($id: Int!) {
                    pages {
                        single(id: $id) {
                            id
                            title
                            path
                        }
                    }
                }
                """
                get_response = await wikijs.graphql_request(get_query, {"id": mapping.page_id})
                page_data = get_response.get("data", {}).get("pages", {}).get("single")
                
                if page_data:
                    valid_mappings.append({
                        "file_path": mapping.file_path,
                        "page_id": mapping.page_id,
                        "page_title": page_data["title"]
                    })
                else:
                    orphaned_mappings.append({
                        "file_path": mapping.file_path,
                        "page_id": mapping.page_id,
                        "last_updated": mapping.last_updated.isoformat() if mapping.last_updated else None
                    })
                    # Delete orphaned mapping
                    db.delete(mapping)
                    
            except Exception as e:
                # If we can't check the page, consider it orphaned
                orphaned_mappings.append({
                    "file_path": mapping.file_path,
                    "page_id": mapping.page_id,
                    "error": str(e)
                })
                db.delete(mapping)
        
        db.commit()
        
        result = {
            "total_mappings": len(mappings),
            "valid_mappings": len(valid_mappings),
            "orphaned_mappings": len(orphaned_mappings),
            "cleaned_count": len(orphaned_mappings),
            "orphaned_details": orphaned_mappings,
            "status": "completed"
        }
        
        logger.info(f"Cleaned up {len(orphaned_mappings)} orphaned file mappings")
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Cleanup failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
