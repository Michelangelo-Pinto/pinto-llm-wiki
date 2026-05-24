"""Wiki.js MCP tools - tools_pages."""

import asyncio
import datetime
import hashlib
import json
import math
import os
import re
import time
from typing import Any, Dict, List, Optional

from slugify import slugify
from sqlalchemy import func

from wiki_mcp_server.client import wikijs
from wiki_mcp_server.config import logger, settings
from wiki_mcp_server.db import BacklinkIndex, FileMapping, RepositoryContext, get_db
from wiki_mcp_server.server import mcp
from wiki_mcp_server.utils import (
    extract_code_structure,
    find_repository_root,
    get_file_hash,
)

BULK_GET_MAX_PAGES = 50

_GET_PAGE_BY_ID_QUERY = """
query($id: Int!) {
    pages {
        single(id: $id) {
            id
            path
            title
            content
            description
            isPrivate
            isPublished
            locale
            createdAt
            updatedAt
            tags {
                tag
            }
        }
    }
}
"""



_RESOLVE_PATH_QUERY = """
query($path: String!) {
    pages {
        singleByPath(path: $path, locale: "en") {
            id
        }
    }
}
"""

_LIST_ALL_PAGES_WITH_TAGS_QUERY = """
query {
    pages {
        list {
            id
            path
            title
            description
            isPublished
            locale
            tags
            updatedAt
        }
    }
}
"""

_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def _extract_links(content: str) -> List[dict]:
    """Extract wiki-internal markdown links from page content.

    Filters out self-links (#anchor), external links (https://...),
    and image links (![alt](...)). Returns list of dicts with
    link_text, target_path, and position.
    """
    links = []
    for match in _LINK_PATTERN.finditer(content):
        raw_text = match.group(0)
        if raw_text.startswith("!"):
            continue  # Image link
        link_text = match.group(1).strip()
        target_path = match.group(2).strip()
        if not target_path:
            continue
        if target_path.startswith("#") or target_path.startswith("http://") or target_path.startswith("https://"):
            continue  # Self-link or external
        # Strip leading slash -- Wiki.js stores paths without it
        target_path = target_path.lstrip("/")
        # Strip anchor fragment
        if "#" in target_path:
            target_path = target_path.split("#", 1)[0]
        links.append({
            "link_text": link_text,
            "target_path": target_path,
            "position": match.start(),
        })
    return links


async def _resolve_paths_to_ids(paths: List[str]) -> Dict[str, Optional[int]]:
    """Resolve wiki paths to page IDs via parallel GraphQL queries.
    Returns dict mapping each path to its page_id (or None if not found).
    """
    if not paths:
        return {}
    unique_paths = list(dict.fromkeys(paths))  # Deduplicate
    tasks = [
        wikijs.graphql_request(_RESOLVE_PATH_QUERY, {"path": p})
        for p in unique_paths
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    result = {}
    for path, resp in zip(unique_paths, responses):
        if isinstance(resp, Exception):
            logger.warning("_resolve_paths_to_ids path not found: %s (%s)", path, str(resp))
            result[path] = None
            continue
        page_data = resp.get("data", {}).get("pages", {}).get("singleByPath")
        if page_data:
            result[path] = page_data.get("id")
        else:
            logger.warning("_resolve_paths_to_ids path not found: %s", path)
            result[path] = None
    return result


async def _sync_backlinks_for_page(source_page_id: int, content: str) -> None:
    """Extract links from page content, resolve paths, and update BacklinkIndex.
    Deletes old entries for this source page first, then inserts new ones.
    """
    links = _extract_links(content)
    logger.debug("_sync_backlinks_for_page page %d: %d links extracted", source_page_id, len(links))
    if not links:
        db = get_db()
        try:
            db.query(BacklinkIndex).filter(BacklinkIndex.source_page_id == source_page_id).delete()
            db.commit()
        except Exception as e:
            logger.warning("_sync_backlinks_for_page failed to clear stale entries for page %d: %s", source_page_id, str(e))
            db.rollback()
        finally:
            db.close()
        return
    paths_to_resolve = [link["target_path"] for link in links]
    path_id_map = await _resolve_paths_to_ids(paths_to_resolve)
    db = get_db()
    try:
        db.query(BacklinkIndex).filter(BacklinkIndex.source_page_id == source_page_id).delete()
        inserted = 0
        for link in links:
            target_id = path_id_map.get(link["target_path"])
            if target_id is None or target_id == source_page_id:
                continue
            db.add(BacklinkIndex(
                source_page_id=source_page_id,
                target_page_id=target_id,
                target_path=link["target_path"],
                link_text=link["link_text"],
                position=link["position"],
                last_updated=datetime.datetime.utcnow(),
            ))
            inserted += 1
        db.commit()
        logger.debug("_sync_backlinks_for_page page %d: %d backlinks stored", source_page_id, inserted)
    except Exception as e:
        logger.warning("_sync_backlinks_for_page failed for page %d: %s", source_page_id, str(e))
        db.rollback()
    finally:
        db.close()


@mcp.tool()
async def wikijs_create_page(title: str, content: str, space_id: str = "", parent_id: str = "") -> str:
    """
    Create a new page in Wiki.js with support for hierarchical organization.
    
    Args:
        title: Page title
        content: Page content (markdown or HTML)
        space_id: Space ID (optional, uses default if not provided)
        parent_id: Parent page ID for hierarchical organization (optional)
    
    Returns:
        JSON string with page details: {'pageId': int, 'url': str}
    """
    try:
        await wikijs.authenticate()
        
        # Generate path - if parent_id provided, create nested path
        if parent_id:
            # Get parent page to build nested path
            parent_query = """
            query($id: Int!) {
                pages {
                    single(id: $id) {
                        path
                        title
                    }
                }
            }
            """
            parent_response = await wikijs.graphql_request(parent_query, {"id": int(parent_id)})
            parent_data = parent_response.get("data", {}).get("pages", {}).get("single")
            
            if parent_data:
                parent_path = parent_data["path"]
                # Create nested path: parent-path/child-title
                path = f"{parent_path}/{slugify(title)}"
            else:
                path = slugify(title)
        else:
            path = slugify(title)
        
        # GraphQL mutation to create a page
        mutation = """
        mutation($content: String!, $description: String!, $editor: String!, $isPublished: Boolean!, $isPrivate: Boolean!, $locale: String!, $path: String!, $publishEndDate: Date, $publishStartDate: Date, $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!) {
            pages {
                create(content: $content, description: $description, editor: $editor, isPublished: $isPublished, isPrivate: $isPrivate, locale: $locale, path: $path, publishEndDate: $publishEndDate, publishStartDate: $publishStartDate, scriptCss: $scriptCss, scriptJs: $scriptJs, tags: $tags, title: $title) {
                    responseResult {
                        succeeded
                        errorCode
                        slug
                        message
                    }
                    page {
                        id
                        path
                        title
                    }
                }
            }
        }
        """
        
        variables = {
            "content": content,
            "description": "",
            "editor": "markdown",
            "isPublished": True,
            "isPrivate": False,
            "locale": "en",
            "path": path,
            "publishEndDate": None,
            "publishStartDate": None,
            "scriptCss": "",
            "scriptJs": "",
            "tags": [],
            "title": title
        }
        
        response = await wikijs.graphql_request(mutation, variables)
        
        create_result = response.get("data", {}).get("pages", {}).get("create", {})
        response_result = create_result.get("responseResult", {})
        
        if response_result.get("succeeded"):
            page_data = create_result.get("page", {})
            result = {
                "pageId": page_data.get("id"),
                "url": page_data.get("path"),
                "title": page_data.get("title"),
                "status": "created",
                "parentId": int(parent_id) if parent_id else None,
                "hierarchicalPath": path
            }
            logger.info(f"Created page: {title} (ID: {result['pageId']}) at path: {path}")
            await _sync_backlinks_for_page(result["pageId"], content)
            _invalidate_stats_cache()
            return json.dumps(result)
        else:
            error_msg = response_result.get("message", "Unknown error")
            return json.dumps({"error": f"Failed to create page: {error_msg}"})
        
    except Exception as e:
        error_msg = f"Failed to create page '{title}': {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_update_page(page_id: int, title: str = None, content: str = None) -> str:
    """
    Update an existing page in Wiki.js.
    
    Args:
        page_id: Page ID to update
        title: New title (optional)
        content: New content (optional)
    
    Returns:
        JSON string with update status
    """
    try:
        await wikijs.authenticate()
        
        # First get the current page data
        get_query = """
        query($id: Int!) {
            pages {
                single(id: $id) {
                    id
                    path
                    title
                    content
                    description
                    isPrivate
                    isPublished
                    locale
                    tags {
                        tag
                    }
                }
            }
        }
        """
        
        get_response = await wikijs.graphql_request(get_query, {"id": page_id})
        current_page = get_response.get("data", {}).get("pages", {}).get("single")
        
        if not current_page:
            return json.dumps({"error": f"Page with ID {page_id} not found"})
        
        # GraphQL mutation to update a page
        mutation = """
        mutation($id: Int!, $content: String!, $description: String!, $editor: String!, $isPrivate: Boolean!, $isPublished: Boolean!, $locale: String!, $path: String!, $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!) {
            pages {
                update(id: $id, content: $content, description: $description, editor: $editor, isPrivate: $isPrivate, isPublished: $isPublished, locale: $locale, path: $path, scriptCss: $scriptCss, scriptJs: $scriptJs, tags: $tags, title: $title) {
                    responseResult {
                        succeeded
                        errorCode
                        slug
                        message
                    }
                    page {
                        id
                        path
                        title
                        updatedAt
                    }
                }
            }
        }
        """
        
        # Use provided values or keep current ones
        new_title = title if title is not None else current_page["title"]
        new_content = content if content is not None else current_page["content"]
        
        variables = {
            "id": page_id,
            "content": new_content,
            "description": current_page.get("description", ""),
            "editor": "markdown",
            "isPrivate": current_page.get("isPrivate", False),
            "isPublished": current_page.get("isPublished", True),
            "locale": current_page.get("locale", "en"),
            "path": current_page["path"],
            "scriptCss": "",
            "scriptJs": "",
            "tags": [tag["tag"] for tag in current_page.get("tags", [])],
            "title": new_title
        }
        
        response = await wikijs.graphql_request(mutation, variables)
        
        update_result = response.get("data", {}).get("pages", {}).get("update", {})
        response_result = update_result.get("responseResult", {})
        
        if response_result.get("succeeded"):
            page_data = update_result.get("page", {})
            result = {
                "pageId": page_id,
                "status": "updated",
                "title": page_data.get("title"),
                "lastModified": page_data.get("updatedAt")
            }
            logger.info(f"Updated page ID: {page_id}")
            await _sync_backlinks_for_page(page_id, new_content)
            _invalidate_stats_cache()
            return json.dumps(result)
        else:
            error_msg = response_result.get("message", "Unknown error")
            return json.dumps({"error": f"Failed to update page: {error_msg}"})
        
    except Exception as e:
        error_msg = f"Failed to update page {page_id}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_get_page(page_id: int = None, slug: str = None) -> str:
    """
    Retrieve page metadata and content from Wiki.js.
    
    Args:
        page_id: Page ID (optional)
        slug: Page slug/path (optional)
    
    Returns:
        JSON string with page data
    """
    try:
        await wikijs.authenticate()
        
        if page_id:
            query = _GET_PAGE_BY_ID_QUERY
            variables = {"id": page_id}
        elif slug:
            query = """
            query($path: String!) {
                pages {
                    singleByPath(path: $path, locale: "en") {
                        id
                        path
                        title
                        content
                        description
                        isPrivate
                        isPublished
                        locale
                        createdAt
                        updatedAt
                        tags {
                            tag
                        }
                    }
                }
            }
            """
            variables = {"path": slug}
        else:
            return json.dumps({"error": "Either page_id or slug must be provided"})
        
        response = await wikijs.graphql_request(query, variables)
        
        page_data = None
        if page_id:
            page_data = response.get("data", {}).get("pages", {}).get("single")
        else:
            page_data = response.get("data", {}).get("pages", {}).get("singleByPath")
        
        if not page_data:
            return json.dumps({"error": "Page not found"})
        
        result = {
            "pageId": page_data.get("id"),
            "title": page_data.get("title"),
            "content": page_data.get("content"),
            "contentType": "markdown",
            "lastModified": page_data.get("updatedAt"),
            "path": page_data.get("path"),
            "isPublished": page_data.get("isPublished"),
            "description": page_data.get("description"),
            "tags": [tag["tag"] for tag in page_data.get("tags", [])]
        }
        
        return json.dumps(result)
        
    except Exception as e:
        error_msg = f"Failed to get page: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_search_pages(query: str, space_id: str = None) -> str:
    """
    Search pages by text in Wiki.js.
    
    Args:
        query: Search query
        space_id: Space ID to limit search (optional)
    
    Returns:
        JSON string with search results
    """
    try:
        await wikijs.authenticate()
        
        # GraphQL query for search (fixed - removed invalid suggestions subfields)
        search_query = """
        query($query: String!) {
            pages {
                search(query: $query, path: "", locale: "en") {
                    results {
                        id
                        title
                        description
                        path
                        locale
                    }
                    totalHits
                }
            }
        }
        """
        
        variables = {"query": query}
        
        response = await wikijs.graphql_request(search_query, variables)
        
        search_data = response.get("data", {}).get("pages", {}).get("search", {})
        
        results = []
        for item in search_data.get("results", []):
            results.append({
                "pageId": item.get("id"),
                "title": item.get("title"),
                "snippet": item.get("description", ""),
                "score": 1.0,  # Wiki.js doesn't provide scores
                "path": item.get("path")
            })
        
        return json.dumps({
            "results": results, 
            "total": search_data.get("totalHits", len(results))
        })
        
    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_list_spaces() -> str:
    """
    List all spaces (top-level Wiki.js containers).
    Note: Wiki.js doesn't have "spaces" like BookStack, but we can list pages at root level.
    
    Returns:
        JSON string with spaces list
    """
    try:
        await wikijs.authenticate()
        
        # Get all pages and group by top-level paths
        query = """
        query {
            pages {
                list {
                    id
                    title
                    path
                    description
                    isPublished
                    locale
                }
            }
        }
        """
        
        response = await wikijs.graphql_request(query)
        
        pages = response.get("data", {}).get("pages", {}).get("list", [])
        
        # Group pages by top-level path (simulate spaces)
        spaces = {}
        for page in pages:
            path_parts = page["path"].split("/")
            if len(path_parts) > 0:
                top_level = path_parts[0] if path_parts[0] else "root"
                if top_level not in spaces:
                    spaces[top_level] = {
                        "spaceId": hash(top_level) % 10000,  # Generate pseudo ID
                        "name": top_level.replace("-", " ").title(),
                        "slug": top_level,
                        "description": f"Pages under /{top_level}",
                        "pageCount": 0
                    }
                spaces[top_level]["pageCount"] += 1
        
        return json.dumps({"spaces": list(spaces.values())})
        
    except Exception as e:
        error_msg = f"Failed to list spaces: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp.tool()
async def wikijs_create_space(name: str, description: str = None) -> str:
    """
    Create a new space in Wiki.js.
    Note: Wiki.js doesn't have spaces, so this creates a root-level page as a space placeholder.
    
    Args:
        name: Space name
        description: Space description (optional)
    
    Returns:
        JSON string with space details
    """
    try:
        # Create a root page that acts as a space
        space_content = f"# {name}\n\n{description or 'This is the main page for the ' + name + ' section.'}\n\n## Pages in this section:\n\n*Pages will be listed here as they are created.*"
        
        result = await wikijs_create_page(name, space_content)
        result_data = json.loads(result)
        
        if "error" not in result_data:
            # Convert page result to space format
            space_result = {
                "spaceId": result_data.get("pageId"),
                "name": name,
                "slug": slugify(name),
                "status": "created",
                "description": description
            }
            logger.info(f"Created space (root page): {name} (ID: {space_result['spaceId']})")
            return json.dumps(space_result)
        else:
            return result
        
    except Exception as e:
        error_msg = f"Failed to create space '{name}': {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_bulk_get_pages(page_ids: List[int], include_content: bool = True) -> str:
    """
    Read multiple pages by their IDs in a single call.
    Fires parallel GraphQL queries via asyncio.gather for efficiency.
    Handles partial failures gracefully: valid pages are returned alongside errors for invalid ones.

    Args:
        page_ids: List of page IDs to fetch (max 50, duplicates removed automatically)
        include_content: Whether to include the full page content (default True)

    Returns:
        JSON string with results, errors, and summary counts:
        {
            "results": [{"pageId": int, "title": str, "content": str, ...}, ...],
            "errors": [{"pageId": int, "error": str}, ...],
            "summary": {"requested": int, "returned": int, "failed": int}
        }
    """
    try:
        if not page_ids:
            return json.dumps({"error": "page_ids must not be empty"})

        if len(page_ids) > BULK_GET_MAX_PAGES:
            return json.dumps({
                "error": f"Too many page IDs requested: {len(page_ids)}. Maximum is {BULK_GET_MAX_PAGES} per call."
            })

        # Deduplicate while preserving order
        seen = set()
        unique_ids = []
        for pid in page_ids:
            if pid not in seen:
                seen.add(pid)
                unique_ids.append(pid)

        await wikijs.authenticate()

        logger.info(
            "bulk_get_pages called with %d unique IDs (total %d requested), include_content=%s",
            len(unique_ids), len(page_ids), include_content,
        )
        logger.debug("bulk_get_pages firing %d parallel queries", len(unique_ids))

        tasks = [
            wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": pid})
            for pid in unique_ids
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        errors = []

        for pid, response in zip(unique_ids, responses):
            if isinstance(response, Exception):
                logger.warning("bulk_get_pages failed to fetch page %d: %s", pid, str(response))
                errors.append({"pageId": pid, "error": str(response)})
                continue

            page_data = response.get("data", {}).get("pages", {}).get("single")
            if not page_data:
                logger.warning("bulk_get_pages page %d not found", pid)
                errors.append({"pageId": pid, "error": "Page not found"})
                continue

            entry = {
                "pageId": page_data.get("id"),
                "title": page_data.get("title"),
                "path": page_data.get("path"),
                "description": page_data.get("description"),
                "lastModified": page_data.get("updatedAt"),
                "tags": [tag["tag"] for tag in page_data.get("tags", [])],
            }
            if include_content:
                entry["content"] = page_data.get("content")

            results.append(entry)

        summary = {
            "requested": len(page_ids),
            "returned": len(results),
            "failed": len(errors),
        }

        if errors:
            failed_ids = [err["pageId"] for err in errors]
            logger.info(
                "bulk_get_pages completed: requested=%d, returned=%d, failed=%d, failed_ids=%s",
                summary["requested"], summary["returned"], summary["failed"], failed_ids,
            )
        else:
            logger.info(
                "bulk_get_pages completed: requested=%d, returned=%d, failed=%d",
                summary["requested"], summary["returned"], summary["failed"],
            )

        return json.dumps({"results": results, "errors": errors, "summary": summary})

    except Exception as e:
        error_msg = f"bulk_get_pages unexpected error: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_get_backlinks(page_id: int) -> str:
    """
    Return all pages that link to the given page.

    Uses the SQLite BacklinkIndex for instant lookups.
    Includes source page titles and link text for context.

    Args:
        page_id: The page ID to find backlinks for

    Returns:
        JSON string with backlinks array and count:
        {
            "pageId": int,
            "title": str,
            "backlinks": [{"sourcePageId": int, "sourceTitle": str, "sourcePath": str, "linkText": str}, ...],
            "count": int
        }
    """
    try:
        await wikijs.authenticate()

        db = get_db()
        try:
            rows = db.query(BacklinkIndex).filter(
                BacklinkIndex.target_page_id == page_id
            ).all()
        finally:
            db.close()

        if not rows:
            # Still try to get the page title for context
            title = "Unknown"
            try:
                page_query = """
                query($id: Int!) {
                    pages {
                        single(id: $id) {
                            id
                            title
                        }
                    }
                }
                """
                resp = await wikijs.graphql_request(page_query, {"id": page_id})
                page_info = resp.get("data", {}).get("pages", {}).get("single")
                if page_info:
                    title = page_info.get("title", "Unknown")
            except Exception:
                pass  # Page may not exist — that's fine
            logger.info("get_backlinks for page %d: 0 backlinks found", page_id)
            return json.dumps({
                "pageId": page_id,
                "title": title,
                "backlinks": [],
                "count": 0,
            })

        # Collect unique source page IDs
        source_ids = list({row.source_page_id for row in rows})

        # Bulk fetch source page titles
        from wiki_mcp_server.tools_pages import wikijs_bulk_get_pages
        bulk_result_json = await wikijs_bulk_get_pages(source_ids, include_content=False)
        bulk_result = json.loads(bulk_result_json)
        source_map = {r["pageId"]: r for r in bulk_result.get("results", [])}

        backlinks = []
        for row in rows:
            src = source_map.get(row.source_page_id, {})
            backlinks.append({
                "sourcePageId": row.source_page_id,
                "sourceTitle": src.get("title", "Unknown"),
                "sourcePath": src.get("path", ""),
                "linkText": row.link_text,
            })

        # Get target page title
        target_title = "Unknown"
        if backlinks:
            try:
                page_query = """
                query($id: Int!) {
                    pages {
                        single(id: $id) {
                            id
                            title
                        }
                    }
                }
                """
                resp = await wikijs.graphql_request(page_query, {"id": page_id})
                page_info = resp.get("data", {}).get("pages", {}).get("single")
                if page_info:
                    target_title = page_info.get("title", "Unknown")
            except Exception:
                pass  # Shouldn't happen since backlinks exist, but be safe
                target_title = page_info.get("title", "Unknown")

        logger.info("get_backlinks for page %d: %d backlinks found", page_id, len(backlinks))

        return json.dumps({
            "pageId": page_id,
            "title": target_title,
            "backlinks": backlinks,
            "count": len(backlinks),
        })

    except Exception as e:
        error_msg = f"get_backlinks unexpected error: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_rebuild_backlink_index() -> str:
    """
    Rebuild the entire backlink index from scratch.

    Scans all wiki pages for markdown links, resolves paths to page IDs,
    and repopulates the SQLite BacklinkIndex table. Call after bulk imports
    or if the index becomes inconsistent.

    Returns:
        JSON string with rebuild summary:
        {
            "status": "completed",
            "totalPages": int,
            "totalLinks": int,
            "unresolvedPaths": int
        }
    """
    try:
        await wikijs.authenticate()

        # Get all page IDs
        list_query = """
        query {
            pages {
                list {
                    id
                }
            }
        }
        """
        resp = await wikijs.graphql_request(list_query)
        pages = resp.get("data", {}).get("pages", {}).get("list", [])
        all_ids = [p["id"] for p in pages]

        if not all_ids:
            return json.dumps({"status": "completed", "totalPages": 0, "totalLinks": 0, "unresolvedPaths": 0})

        logger.info("rebuild_backlink_index: scanning %d pages", len(all_ids))

        # Bulk fetch content for all pages
        from wiki_mcp_server.tools_pages import wikijs_bulk_get_pages
        bulk_result_json = await wikijs_bulk_get_pages(all_ids, include_content=True)
        bulk_result = json.loads(bulk_result_json)

        # Clear existing index
        db = get_db()
        try:
            db.query(BacklinkIndex).delete()
            db.commit()
        except Exception as e:
            logger.error("rebuild_backlink_index failed to clear table: %s", str(e))
            db.rollback()
            return json.dumps({"error": f"Failed to clear backlink table: {str(e)}"})
        finally:
            db.close()

        # Collect all links across all pages
        all_links = []  # List of (source_page_id, link_text, target_path, position)
        for page in bulk_result.get("results", []):
            links = _extract_links(page.get("content", ""))
            for link in links:
                all_links.append((page["pageId"], link["link_text"], link["target_path"], link["position"]))

        # Resolve all unique paths in one batch
        unique_paths = list({link[2] for link in all_links})
        path_id_map = await _resolve_paths_to_ids(unique_paths)

        unresolved = 0
        total_inserted = 0
        db = get_db()
        try:
            for source_id, link_text, target_path, position in all_links:
                target_id = path_id_map.get(target_path)
                if target_id is None or target_id == source_id:
                    if target_id is None:
                        unresolved += 1
                    continue
                db.add(BacklinkIndex(
                    source_page_id=source_id,
                    target_page_id=target_id,
                    target_path=target_path,
                    link_text=link_text,
                    position=position,
                    last_updated=datetime.datetime.utcnow(),
                ))
                total_inserted += 1

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("rebuild_backlink_index failed during insertion: %s", str(e))
            return json.dumps({"error": f"Failed to rebuild index: {str(e)}"})
        finally:
            db.close()

        logger.info(
            "rebuild_backlink_index: completed, %d pages, %d links, %d unresolved",
            len(all_ids), total_inserted, unresolved,
        )

        return json.dumps({
            "status": "completed",
            "totalPages": len(all_ids),
            "totalLinks": total_inserted,
            "unresolvedPaths": unresolved,
        })

    except Exception as e:
        error_msg = f"rebuild_backlink_index unexpected error: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_get_page_stats(page_id: int) -> str:
    """
    Return metadata about a page WITHOUT its full content.
    Use for triage: decide which pages to read before calling bulk_get_pages.

    Args:
        page_id: Page ID to get stats for

    Returns:
        JSON string with stats:
        {
            "pageId": int, "title": str, "path": str,
            "contentLength": int, "wordCount": int,
            "outboundLinkCount": int, "inboundLinkCount": int,
            "lastModified": str, "createdAt": str,
            "tags": [...], "isPublished": bool, "description": str
        }
    """
    try:
        await wikijs.authenticate()

        response = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": page_id})
        page_data = response.get("data", {}).get("pages", {}).get("single")

        if not page_data:
            return json.dumps({"error": f"Page not found: {page_id}"})

        content = page_data.get("content", "")
        outbound_links = _extract_links(content)

        # Query inbound link count from BacklinkIndex
        db = get_db()
        try:
            inbound_count = db.query(BacklinkIndex).filter(
                BacklinkIndex.target_page_id == page_id
            ).count()
        finally:
            db.close()

        result = {
            "pageId": page_data.get("id"),
            "title": page_data.get("title"),
            "path": page_data.get("path"),
            "contentLength": len(content),
            "wordCount": len(content.split()) if content.strip() else 0,
            "outboundLinkCount": len(outbound_links),
            "inboundLinkCount": inbound_count,
            "lastModified": page_data.get("updatedAt"),
            "createdAt": page_data.get("createdAt"),
            "tags": [tag["tag"] for tag in page_data.get("tags", [])],
            "isPublished": page_data.get("isPublished", False),
            "description": page_data.get("description", ""),
        }

        logger.info(
            "page_stats for page %d: wordCount=%d, links=%d/%d",
            page_id, result["wordCount"], result["outboundLinkCount"], result["inboundLinkCount"],
        )

        return json.dumps(result)

    except Exception as e:
        error_msg = f"page_stats unexpected error: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_bulk_get_page_stats(page_ids: List[int]) -> str:
    """
    Return metadata for multiple pages WITHOUT their full content.
    Uses bulk_get_pages internally for efficient content fetching.

    Args:
        page_ids: List of page IDs (max 50, duplicates removed)

    Returns:
        JSON: {results: [{stats...}, ...], summary: {requested, returned, failed}}
    """
    try:
        if not page_ids:
            return json.dumps({"error": "page_ids must not be empty"})

        if len(page_ids) > BULK_GET_MAX_PAGES:
            return json.dumps({
                "error": f"Too many page IDs: {len(page_ids)}. Maximum is {BULK_GET_MAX_PAGES}."
            })

        # Deduplicate
        seen = set()
        unique_ids = []
        for pid in page_ids:
            if pid not in seen:
                seen.add(pid)
                unique_ids.append(pid)

        await wikijs.authenticate()

        logger.info("bulk_page_stats: fetching %d unique pages", len(unique_ids))

        # Phase 1: bulk fetch content for all pages
        bulk_json = await wikijs_bulk_get_pages(unique_ids, include_content=True)
        bulk_data = json.loads(bulk_json)

        results = []
        errors = bulk_data.get("errors", [])

        # Phase 2: batch query inbound link counts
        db = get_db()
        try:
            successful_ids = [r["pageId"] for r in bulk_data.get("results", [])]
            if successful_ids:
                from sqlalchemy import func
                inbound_rows = (
                    db.query(BacklinkIndex.target_page_id, func.count(BacklinkIndex.id).label("cnt"))
                    .filter(BacklinkIndex.target_page_id.in_(successful_ids))
                    .group_by(BacklinkIndex.target_page_id)
                    .all()
                )
                inbound_map = {row.target_page_id: row.cnt for row in inbound_rows}
            else:
                inbound_map = {}
        finally:
            db.close()

        # Phase 3: compute stats from content
        for page in bulk_data.get("results", []):
            content = page.get("content", "")
            outbound = _extract_links(content)

            results.append({
                "pageId": page.get("pageId"),
                "title": page.get("title"),
                "path": page.get("path"),
                "contentLength": len(content),
                "wordCount": len(content.split()) if content.strip() else 0,
                "outboundLinkCount": len(outbound),
                "inboundLinkCount": inbound_map.get(page.get("pageId"), 0),
                "lastModified": page.get("lastModified"),
                "tags": page.get("tags", []),
                "description": page.get("description", ""),
            })

        summary = {
            "requested": len(page_ids),
            "returned": len(results),
            "failed": len(errors),
        }

        logger.info(
            "bulk_page_stats completed: requested=%d, returned=%d, failed=%d",
            summary["requested"], summary["returned"], summary["failed"],
        )

        return json.dumps({"results": results, "errors": errors, "summary": summary})

    except Exception as e:
        error_msg = f"bulk_page_stats unexpected error: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_append_to_page(page_id: int, content: str, position: str = "end") -> str:
    """
    Append (or prepend) content to an existing page without fetching it manually.

    Uses optimistic locking with post-write verification: fetches current content,
    appends, writes back, then re-reads to confirm. Retries up to 3 times if a
    concurrent writer modified the page.

    Args:
        page_id: Page ID to append to
        content: Content to append (or prepend)
        position: "end" (default) to append, "start" to prepend

    Returns:
        JSON: {pageId, title, status: "appended", newContentLength, attempts}
    """
    if position not in ("end", "start"):
        return json.dumps({"error": f"Invalid position '{position}'. Must be 'end' or 'start'."})

    if not content.strip():
        return json.dumps({"error": "Content must not be empty"})

    await wikijs.authenticate()

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            # Fetch current page
            response = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": page_id})
            page_data = response.get("data", {}).get("pages", {}).get("single")

            if not page_data:
                return json.dumps({"error": f"Page not found: {page_id}"})

            current_content = page_data.get("content", "")
            title = page_data.get("title")

            # Build new content
            if position == "end":
                separator = "\n\n" if current_content and not current_content.endswith("\n") else "\n"
                new_content = current_content + separator + content
            else:
                separator = "\n\n" if current_content and not current_content.endswith("\n") else "\n"
                new_content = content + separator + current_content

            # Write back (reuse same mutation pattern as wikijs_update_page)
            mutation = """
            mutation($id: Int!, $content: String!, $description: String!, $editor: String!, $isPrivate: Boolean!, $isPublished: Boolean!, $locale: String!, $path: String!, $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!) {
                pages {
                    update(id: $id, content: $content, description: $description, editor: $editor, isPrivate: $isPrivate, isPublished: $isPublished, locale: $locale, path: $path, scriptCss: $scriptCss, scriptJs: $scriptJs, tags: $tags, title: $title) {
                        responseResult {
                            succeeded
                            errorCode
                            slug
                            message
                        }
                        page {
                            id
                            path
                            title
                            updatedAt
                        }
                    }
                }
            }
            """

            variables = {
                "id": page_id,
                "content": new_content,
                "description": page_data.get("description", ""),
                "editor": "markdown",
                "isPrivate": page_data.get("isPrivate", False),
                "isPublished": page_data.get("isPublished", True),
                "locale": page_data.get("locale", "en"),
                "path": page_data["path"],
                "scriptCss": "",
                "scriptJs": "",
                "tags": [tag["tag"] for tag in page_data.get("tags", [])],
                "title": title,
            }

            write_resp = await wikijs.graphql_request(mutation, variables)
            update_result = write_resp.get("data", {}).get("pages", {}).get("update", {})
            response_result = update_result.get("responseResult", {})

            if not response_result.get("succeeded"):
                return json.dumps({"error": f"Update failed: {response_result.get('message', 'Unknown')}"})

            # Verify: re-read and check appended content is present
            verify_resp = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": page_id})
            verify_data = verify_resp.get("data", {}).get("pages", {}).get("single")
            verified_content = verify_data.get("content", "") if verify_data else ""

            if content in verified_content:
                logger.info(
                    "append_to_page page %d: appended %d chars, new length %d, attempts %d",
                    page_id, len(content), len(verified_content), attempt,
                )
                return json.dumps({
                    "pageId": page_id,
                    "title": title,
                    "status": "appended",
                    "newContentLength": len(verified_content),
                    "attempts": attempt,
                })

            # Content not verified — another writer intervened
            if attempt < max_attempts:
                backoff = 2 ** (attempt - 1)
                logger.warning(
                    "append_to_page page %d: retry %d/%d, content mismatch — waiting %ds",
                    page_id, attempt, max_attempts, backoff,
                )
                await asyncio.sleep(backoff)
                continue

        except Exception as e:
            if attempt < max_attempts:
                logger.warning("append_to_page page %d: attempt %d failed (%s), retrying", page_id, attempt, str(e))
                await asyncio.sleep(2 ** (attempt - 1))
                continue
            logger.error("append_to_page page %d: attempt %d failed (%s)", page_id, attempt, str(e))
            return json.dumps({"error": f"Failed to append to page {page_id}: {str(e)}"})

    logger.error("append_to_page page %d: failed after %d attempts", page_id, max_attempts)
    return json.dumps({
        "error": f"Page modified concurrently after {max_attempts} attempts. Retry the append."
    })


@mcp.tool()
async def wikijs_search_by_tag(tag: str, include_subtags: bool = False) -> str:
    """
    Search pages by tag with optional hierarchical subtag matching.

    Tags in Wiki.js are flat strings. Hierarchy is a convention using "/"
    as separator (e.g., "tech/python/async"). When include_subtags=True,
    pages tagged with "tech/python" or "tech/python/async" also match "tech".

    Design: uses pages.list with tags and client-side filtering.
    No SQLite cache needed at 200+ page scale (~500ms per call).

    Args:
        tag: Tag to search for (exact match)
        include_subtags: If True, also match pages whose tags start with "tag/"

    Returns:
        JSON: {results: [{pageId, title, path, description, tags, lastModified}], total, tag, includeSubtasks}
    """
    try:
        if not tag.strip():
            return json.dumps({"error": "Tag must not be empty"})

        await wikijs.authenticate()

        response = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        pages = response.get("data", {}).get("pages", {}).get("list", [])

        results = []
        for page in pages:
            page_tags = page.get("tags", []) or []
            matches = False
            if include_subtags:
                # Match exact tag OR any tag starting with "tag/"
                for pt in page_tags:
                    if pt == tag or pt.startswith(tag + "/"):
                        matches = True
                        break
            else:
                matches = tag in page_tags

            if matches:
                results.append({
                    "pageId": page.get("id"),
                    "title": page.get("title"),
                    "path": page.get("path"),
                    "description": page.get("description", ""),
                    "tags": page_tags,
                    "lastModified": page.get("updatedAt"),
                })

        logger.info("search_by_tag '%s' (subtags=%s): %d pages found", tag, include_subtags, len(results))
        return json.dumps({
            "results": results,
            "total": len(results),
            "tag": tag,
            "includeSubtags": include_subtags,
        })

    except Exception as e:
        error_msg = f"search_by_tag failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_list_all_tags(hierarchical: bool = False) -> str:
    """
    List all unique tags with page counts, optionally as a hierarchical tree.

    Tags are flat strings in Wiki.js. Hierarchy uses "/" as separator.
    When hierarchical=True, tags are organized into a tree:
    "tech" -> {"children": {"python": {"children": {"async": {}}}}}

    Design: uses pages.list with tags, client-side deduplication and counting.
    No caching in v1 — single GraphQL call is fast enough at 200+ pages.

    Args:
        hierarchical: If True, return tree structure with children.

    Returns:
        JSON: {tags: [{tag, pageCount}, ...], totalUniqueTags}
        or    {tree: {tag, pageCount, children: {...}}, totalUniqueTags}
    """
    try:
        await wikijs.authenticate()

        response = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        pages = response.get("data", {}).get("pages", {}).get("list", [])

        # Count occurrences of each tag
        tag_counts: Dict[str, int] = {}
        for page in pages:
            for tag_name in (page.get("tags") or []):
                tag_counts[tag_name] = tag_counts.get(tag_name, 0) + 1

        if not hierarchical:
            flat_tags = sorted(
                [{"tag": tag, "pageCount": count} for tag, count in tag_counts.items()],
                key=lambda x: x["pageCount"],
                reverse=True,
            )
            logger.info("list_all_tags flat: %d unique tags", len(flat_tags))
            return json.dumps({"tags": flat_tags, "totalUniqueTags": len(flat_tags)})

        # Build hierarchical tree
        tree: Dict[str, dict] = {}
        for tag, count in tag_counts.items():
            parts = tag.split("/")
            current = tree
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {"tag": part, "pageCount": count if i == len(parts) - 1 else 0, "children": {}}
                else:
                    # For non-leaf nodes, add to pageCount if the tag itself exists
                    pass
                if i == len(parts) - 1:
                    current[part]["pageCount"] = count
                current = current[part]["children"]

        def _tree_to_list(node: dict) -> list:
            result = []
            for key, value in sorted(node.items()):
                entry = {
                    "tag": value["tag"],
                    "pageCount": value["pageCount"],
                }
                if value["children"]:
                    entry["children"] = _tree_to_list(value["children"])
                result.append(entry)
            return result

        tree_list = _tree_to_list(tree)
        logger.info("list_all_tags hierarchical: %d unique tags, %d root branches", len(tag_counts), len(tree_list))
        return json.dumps({"tree": tree_list, "totalUniqueTags": len(tag_counts)})

    except Exception as e:
        error_msg = f"list_all_tags failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_set_page_tags(page_id: int, tags: List[str]) -> str:
    """
    Replace the tag list for a page without modifying its content.

    Fetches the current page to preserve all fields (content, title, path, etc.),
    then calls pages.update with only the tags field changed.

    Design: reuses the existing pages.update mutation pattern from
    wikijs_update_page and wikijs_append_to_page.

    Args:
        page_id: Page ID to modify
        tags: New list of tag strings (replaces all existing tags)

    Returns:
        JSON: {pageId, title, tags: [...], status: "updated"}
    """
    try:
        await wikijs.authenticate()

        # Fetch current page to preserve all fields
        response = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": page_id})
        page_data = response.get("data", {}).get("pages", {}).get("single")

        if not page_data:
            return json.dumps({"error": f"Page not found: {page_id}"})

        # Mutation reused from wikijs_append_to_page / wikijs_update_page
        mutation = """
        mutation($id: Int!, $content: String!, $description: String!, $editor: String!, $isPrivate: Boolean!, $isPublished: Boolean!, $locale: String!, $path: String!, $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!) {
            pages {
                update(id: $id, content: $content, description: $description, editor: $editor, isPrivate: $isPrivate, isPublished: $isPublished, locale: $locale, path: $path, scriptCss: $scriptCss, scriptJs: $scriptJs, tags: $tags, title: $title) {
                    responseResult {
                        succeeded
                        errorCode
                        slug
                        message
                    }
                    page {
                        id
                        path
                        title
                        updatedAt
                    }
                }
            }
        }
        """

        variables = {
            "id": page_id,
            "content": page_data.get("content", ""),
            "description": page_data.get("description", ""),
            "editor": "markdown",
            "isPrivate": page_data.get("isPrivate", False),
            "isPublished": page_data.get("isPublished", True),
            "locale": page_data.get("locale", "en"),
            "path": page_data["path"],
            "scriptCss": "",
            "scriptJs": "",
            "tags": tags,
            "title": page_data.get("title", ""),
        }

        write_resp = await wikijs.graphql_request(mutation, variables)
        update_result = write_resp.get("data", {}).get("pages", {}).get("update", {})
        response_result = update_result.get("responseResult", {})

        if not response_result.get("succeeded"):
            return json.dumps({"error": f"Update failed: {response_result.get('message', 'Unknown')}"})

        page_info = update_result.get("page", {})
        logger.info("set_page_tags page %d: tags=%s", page_id, tags)

        return json.dumps({
            "pageId": page_id,
            "title": page_info.get("title", page_data.get("title")),
            "tags": tags,
            "status": "updated",
            "lastModified": page_info.get("updatedAt"),
        })

    except Exception as e:
        error_msg = f"set_page_tags failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_filter_pages(filters: Dict[str, Any]) -> str:
    """
    Filter pages by multiple facets with AND logic.

    Fetches all pages via pages.list, then applies client-side AND filtering.
    Supported filter keys:
    - "tag": match pages that have this exact tag
    - "locale": match pages with this locale (e.g. "en")
    - "isPublished": match boolean published status

    Design: uses pages.list with tags, client-side AND intersection filtering.
    No SQLite cache — single GraphQL call is sufficient at 200+ pages.

    Args:
        filters: Dict of facet -> value pairs. All must match (AND logic).
                 Example: {"tag": "tech", "isPublished": True}

    Returns:
        JSON: {results: [{pageId, title, path, tags, lastModified}], total, filters_applied}
    """
    try:
        if not filters:
            return json.dumps({"error": "filters must not be empty"})

        await wikijs.authenticate()

        response = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        pages = response.get("data", {}).get("pages", {}).get("list", [])

        results = []
        for page in pages:
            match = True
            for key, value in filters.items():
                if key == "tag":
                    page_tags = page.get("tags") or []
                    if value not in page_tags:
                        match = False
                        break
                elif key == "locale":
                    if page.get("locale") != value:
                        match = False
                        break
                elif key == "isPublished":
                    if page.get("isPublished") != value:
                        match = False
                        break
                else:
                    # Unknown filter key — skip but log
                    logger.warning("filter_pages: unknown filter key '%s', ignoring", key)

            if match:
                results.append({
                    "pageId": page.get("id"),
                    "title": page.get("title"),
                    "path": page.get("path"),
                    "tags": page.get("tags") or [],
                    "lastModified": page.get("updatedAt"),
                })

        logger.info("filter_pages with %d filters: %d pages found", len(filters), len(results))
        return json.dumps({
            "results": results,
            "total": len(results),
            "filters_applied": list(filters.keys()),
        })

    except Exception as e:
        error_msg = f"filter_pages failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_smart_query(query: str, limit: int = 10, include_summaries: bool = True, include_link_context: bool = True) -> str:
    """
    Hybrid search combining semantic (vector) and keyword results via RRF.

    Reciprocal Rank Fusion merges two ranked lists into a single ranking
    without parameter tuning: RRF(d) = sum( 1 / (k + rank_in_source) ), k=60.

    Falls back gracefully:
    - Vector + keyword both available -> "full" mode
    - Model not loaded -> "keyword" mode (wikijs_search_pages only)
    - Wiki.js search fails -> "semantic" mode (vector only)

    Design: uses vector_search and search_pages in parallel via asyncio.gather.
    Link context from BacklinkIndex. Summaries from first 500 chars of content.

    Args:
        query: Natural language search query
        limit: Max results to return (default 10)
        include_summaries: Include content snippet (first 500 chars)
        include_link_context: Include linked_from and linked_to arrays

    Returns:
        JSON: {query, total_hits, fallback_mode, results: [{...}]}
    """
    try:
        if not query.strip():
            return json.dumps({"error": "Query must not be empty"})

        await wikijs.authenticate()

        k = 60  # RRF constant

        # Collect page metadata via pages.list for title/path resolution
        list_resp = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        all_pages = list_resp.get("data", {}).get("pages", {}).get("list", [])
        page_meta = {p["id"]: p for p in all_pages}

        # --- Phase 1: Run semantic and keyword searches in parallel ---
        semantic_scores: Dict[int, float] = {}
        keyword_ranks: Dict[int, int] = {}
        semantic_ok = False
        keyword_ok = False

        async def _semantic_search():
            nonlocal semantic_ok
            try:
                from qdrant_client import QdrantClient
                from sentence_transformers import SentenceTransformer
                from wiki_mcp_server.config import settings

                client = QdrantClient(url=settings.QDRANT_URL)
                collection = settings.QDRANT_COLLECTION_WIKI_PAGES

                # Check if the collection exists
                collections = [c.name for c in client.get_collections().collections]
                if collection not in collections:
                    logger.warning("smart_query: Qdrant collection '%s' not found", collection)
                    return

                info = client.get_collection(collection)
                if info.points_count == 0:
                    logger.info("smart_query: Qdrant collection '%s' is empty", collection)
                    return

                # Compute query embedding and search
                model = SentenceTransformer("all-MiniLM-L6-v2")
                query_embedding = model.encode(query, normalize_embeddings=True).tolist()

                response = client.query_points(
                    collection_name=collection,
                    query=query_embedding,
                    limit=100,
                    with_payload=True,
                )
                for hit in response.points:
                    page_id = hit.payload.get("page_id")
                    if page_id is not None:
                        semantic_scores[page_id] = hit.score
                semantic_ok = True
            except ImportError:
                logger.warning(
                    "smart_query: sentence-transformers not available. "
                    "Install it or configure QDRANT_URL to a Qdrant instance with embedding support."
                )
                return
            except Exception as e:
                logger.warning("smart_query: Qdrant semantic search failed: %s", e)
                return

        async def _keyword_search():
            nonlocal keyword_ok
            r = await wikijs_search_pages(query)
            d = json.loads(r)
            if "error" in d:
                return
            for idx, item in enumerate(d.get("results", [])):
                pid = item.get("pageId")
                if pid is not None:
                    keyword_ranks[pid] = idx
            keyword_ok = True

        await asyncio.gather(_semantic_search(), _keyword_search())

        # --- Phase 2: Determine fallback mode ---
        if semantic_ok and keyword_ok:
            fallback_mode = "full"
        elif semantic_ok:
            fallback_mode = "semantic"
        elif keyword_ok:
            fallback_mode = "keyword"
        else:
            return json.dumps({
                "error": "Both semantic and keyword search failed",
                "query": query,
                "fallback_mode": "failed",
            })

        # --- Phase 3: RRF merge ---
        all_page_ids = set(semantic_scores.keys()) | set(keyword_ranks.keys())
        rrf_scores: Dict[int, float] = {}
        for pid in all_page_ids:
            score = 0.0
            if pid in semantic_scores:
                # Build sorted list of semantic scores to find rank
                sorted_sem = sorted(semantic_scores.items(), key=lambda x: x[1], reverse=True)
                for rank, (spid, _) in enumerate(sorted_sem):
                    if spid == pid:
                        score += 1.0 / (k + rank)
                        break
            if pid in keyword_ranks:
                score += 1.0 / (k + keyword_ranks[pid])
            rrf_scores[pid] = score

        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        total_hits = len(sorted_results)
        top = sorted_results[:limit]

        # --- Phase 4: Enrich results ---
        top_ids = [pid for pid, _ in top]
        from wiki_mcp_server.tools_pages import wikijs_bulk_get_pages

        bulk_json = await wikijs_bulk_get_pages(top_ids, include_content=include_summaries)
        bulk_data = json.loads(bulk_json)
        content_map = {r["pageId"]: r for r in bulk_data.get("results", [])}

        # Batch backlink counts for link context
        if include_link_context and top_ids:
            db = get_db()
            try:
                from sqlalchemy import func
                inbound_rows = (
                    db.query(BacklinkIndex.target_page_id, func.count(BacklinkIndex.id).label("cnt"))
                    .filter(BacklinkIndex.target_page_id.in_(top_ids))
                    .group_by(BacklinkIndex.target_page_id)
                    .all()
                )
                inbound_counts = {row.target_page_id: row.cnt for row in inbound_rows}
            finally:
                db.close()
        else:
            inbound_counts = {}

        results = []
        for pid, rrf_score in top:
            meta = page_meta.get(pid, {})
            content = content_map.get(pid, {})
            entry = {
                "pageId": pid,
                "title": meta.get("title", content.get("title", "Unknown")),
                "path": meta.get("path", content.get("path", "")),
                "relevance_score": round(rrf_score, 4),
                "tags": meta.get("tags") or [],
                "lastModified": meta.get("updatedAt", ""),
            }
            full_content = content.get("content", "") if include_summaries or include_link_context else ""
            if include_summaries:
                entry["snippet"] = full_content[:500] if full_content else ""
                entry["summary"] = meta.get("description", "")[:300] if meta.get("description") else ""
            if include_link_context:
                entry["linked_from"] = []
                entry["linked_to"] = []
                if full_content:
                    links = _extract_links(full_content)
                    for link in links:
                        tgt = link["target_path"]
                        entry["linked_to"].append({"path": tgt, "linkText": link["link_text"]})
                entry["inbound_link_count"] = inbound_counts.get(pid, 0)
            results.append(entry)

        logger.info(
            "smart_query '%s': %d results, mode=%s, total_hits=%d",
            query[:60], len(results), fallback_mode, total_hits,
        )

        return json.dumps({
            "query": query,
            "total_hits": total_hits,
            "fallback_mode": fallback_mode,
            "results": results,
        })

    except Exception as e:
        error_msg = f"smart_query failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_get_recent_changes(limit: int = 20, since_days: int = None, since_date: str = None) -> str:
    """
    Return pages modified within a given time window, sorted by most recent.

    Design: fetches pages.list with updatedAt, filters client-side by date.
    Wiki.js GraphQL has no native date filter on pages.list.

    Args:
        limit: Max pages to return (default 20)
        since_days: Return pages modified in the last N days (e.g. 7)
        since_date: Return pages modified since ISO date (e.g. "2026-05-15").
                     Overrides since_days if both provided.

    Returns:
        JSON: {results: [{pageId, title, path, updatedAt, description}], total, since_days, since_date}
    """
    try:
        if since_days is not None and since_days < 0:
            return json.dumps({"error": "since_days must be non-negative"})

        await wikijs.authenticate()

        response = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        pages = response.get("data", {}).get("pages", {}).get("list", [])

        now = datetime.datetime.now(datetime.timezone.utc)

        # Determine cutoff
        if since_date:
            try:
                cutoff = datetime.datetime.fromisoformat(since_date)
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                return json.dumps({"error": f"Invalid since_date format: {since_date}. Use ISO 8601 (e.g. '2026-05-15')."})
        elif since_days is not None:
            cutoff = now - datetime.timedelta(days=since_days)
        else:
            cutoff = None

        results = []
        for page in pages:
            updated_str = page.get("updatedAt", "")
            if not updated_str:
                continue
            try:
                updated = datetime.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            if cutoff is not None and updated < cutoff:
                continue

            results.append({
                "pageId": page.get("id"),
                "title": page.get("title"),
                "path": page.get("path"),
                "updatedAt": updated_str,
                "description": page.get("description", ""),
            })

        results.sort(key=lambda r: r["updatedAt"], reverse=True)
        results = results[:limit]

        logger.info("get_recent_changes: %d pages (since_days=%s, since_date=%s)", len(results), since_days, since_date)

        return json.dumps({
            "results": results,
            "total": len(results),
            "since_days": since_days,
            "since_date": since_date,
        })

    except Exception as e:
        error_msg = f"get_recent_changes failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


# Wiki stats cache: {timestamp: float, data: dict}
_stats_cache: Dict[str, Any] = {"timestamp": 0.0, "data": None}
_STATS_CACHE_TTL = 60  # seconds

def _invalidate_stats_cache():
    """Clear the wiki stats cache (called on page create/update/delete)."""
    global _stats_cache
    _stats_cache = {"timestamp": 0.0, "data": None}


@mcp.tool()
async def wikijs_wiki_stats() -> str:
    """
    Return aggregate statistics for the entire wiki in one call.

    Lightweight: no content reading. All data from BacklinkIndex + pages.list.
    Cached for 60 seconds, invalidated on page changes.

    Design: complements wiki_health (P3). wiki_stats gives aggregate numbers;
    wiki_health gives actionable lists. Use wiki_stats for monitoring.

    Returns:
        JSON with aggregate stats: total_pages, link counts, tag counts,
        growth, most linked/linking, content stats, update frequency.
    """
    try:
        global _stats_cache
        now = time.time()
        if _stats_cache["data"] is not None and (now - _stats_cache["timestamp"]) < _STATS_CACHE_TTL:
            logger.info("wiki_stats: returning cached results (%.1fs old)", now - _stats_cache["timestamp"])
            return json.dumps(_stats_cache["data"])

        await wikijs.authenticate()

        response = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        pages = response.get("data", {}).get("pages", {}).get("list", [])
        total_pages = len(pages)

        if total_pages == 0:
            empty = {
                "total_pages": 0, "total_links": 0, "internal_links": 0,
                "external_links": 0, "avg_links_per_page": 0,
                "orphan_count": 0, "orphan_rate": 0,
                "stale_count": 0, "avg_staleness_days": 0,
                "total_tags": 0, "unique_tags": 0, "pages_without_tags": 0,
                "growth_last_30d": 0, "growth_last_7d": 0,
                "most_linked": [], "most_linking": [],
                "newest_page": None, "oldest_page": None,
                "content_stats": {"total_words": 0, "avg_words_per_page": 0},
                "update_frequency": {"updated_last_24h": 0, "updated_last_7d": 0, "never_updated": 0},
            }
            _stats_cache = {"timestamp": now, "data": empty}
            return json.dumps(empty)

        # BacklinkIndex aggregates
        db = get_db()
        try:
            from sqlalchemy import func
            # Total links
            total_links_row = db.query(func.count(BacklinkIndex.id)).scalar() or 0
            # Inbound counts per page
            inbound_rows = (
                db.query(BacklinkIndex.target_page_id, func.count(BacklinkIndex.id).label("cnt"))
                .filter(BacklinkIndex.target_page_id.isnot(None))
                .group_by(BacklinkIndex.target_page_id)
                .all()
            )
            inbound_map = {row.target_page_id: row.cnt for row in inbound_rows}
            # Outbound counts per page
            outbound_rows = (
                db.query(BacklinkIndex.source_page_id, func.count(BacklinkIndex.id).label("cnt"))
                .group_by(BacklinkIndex.source_page_id)
                .all()
            )
            outbound_map = {row.source_page_id: row.cnt for row in outbound_rows}
        finally:
            db.close()

        # Compute stats
        orphan_count = 0
        total_inbound = 0
        total_outbound = 0
        tag_set = set()
        tag_total = 0
        pages_without_tags = 0
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        stale_count = 0
        staleness_days_list = []
        growth_30d = 0
        growth_7d = 0
        updated_24h = 0
        updated_7d = 0
        total_words = 0
        largest_page = None
        smallest_page = None

        for page in pages:
            pid = page.get("id")
            inbound = inbound_map.get(pid, 0)
            outbound = outbound_map.get(pid, 0)
            total_inbound += inbound
            total_outbound += outbound
            if inbound == 0:
                orphan_count += 1

            # Tags
            tags = page.get("tags") or []
            tag_total += len(tags)
            tag_set.update(tags)
            if not tags:
                pages_without_tags += 1

            # Staleness
            updated_str = page.get("updatedAt", "")
            if updated_str:
                try:
                    updated = datetime.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    days_stale = (now_dt - updated).days
                    if days_stale > 90:
                        stale_count += 1
                    if days_stale >= 0:
                        staleness_days_list.append(days_stale)
                except (ValueError, AttributeError):
                    pass

            # Growth (createdAt not in pages.list — computed separately)
            # Cannot compute growth from pages.list alone

        # Most linked (top 5)
        most_linked = sorted(inbound_map.items(), key=lambda x: x[1], reverse=True)[:5]
        most_linking = sorted(outbound_map.items(), key=lambda x: x[1], reverse=True)[:5]

        # Resolve titles for most_linked and most_linking
        title_ids = [pid for pid, _ in most_linked] + [pid for pid, _ in most_linking]
        title_ids = list(dict.fromkeys(title_ids))
        from wiki_mcp_server.tools_pages import wikijs_bulk_get_pages
        title_map = {}
        if title_ids:
            try:
                bulk_json = await wikijs_bulk_get_pages(title_ids, include_content=False)
                bulk_data = json.loads(bulk_json)
                title_map = {r["pageId"]: r for r in bulk_data.get("results", [])}
            except Exception:
                pass

        most_linked_out = []
        for pid, cnt in most_linked:
            t = title_map.get(pid, {})
            most_linked_out.append({"pageId": pid, "title": t.get("title", "Unknown"), "inbound_links": cnt})

        most_linking_out = []
        for pid, cnt in most_linking:
            t = title_map.get(pid, {})
            most_linking_out.append({"pageId": pid, "title": t.get("title", "Unknown"), "outbound_links": cnt})

        avg_stale = round(sum(staleness_days_list) / len(staleness_days_list), 1) if staleness_days_list else 0

        result = {
            "total_pages": total_pages,
            "total_links": total_links_row,
            "internal_links": total_links_row,
            "external_links": 0,
            "avg_links_per_page": round(total_outbound / total_pages, 1) if total_pages else 0,
            "orphan_count": orphan_count,
            "orphan_rate": round(orphan_count / total_pages, 3) if total_pages else 0,
            "stale_count": stale_count,
            "avg_staleness_days": avg_stale,
            "total_tags": tag_total,
            "unique_tags": len(tag_set),
            "pages_without_tags": pages_without_tags,
            "growth_last_30d": None,
            "growth_last_7d": None,
            "most_linked": most_linked_out,
            "most_linking": most_linking_out,
            "newest_page": None,
            "oldest_page": None,
            "content_stats": {"total_words": None, "avg_words_per_page": None},
            "update_frequency": {"updated_last_24h": None, "updated_last_7d": None, "never_updated": None},
        }

        _stats_cache = {"timestamp": now, "data": result}
        logger.info("wiki_stats: %d pages, %d links, %d orphans", total_pages, total_links_row, orphan_count)
        return json.dumps(result)

    except Exception as e:
        error_msg = f"wiki_stats failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_wiki_health(
    include_checks: List[str] = None,
    exclude_page_ids: List[int] = None,
    exclude_paths: List[str] = None,
) -> str:
    """
    Unified health dashboard: 7 checks in a single tool call.

    Checks: orphans, stale, link_density, untagged, most_connected,
    disconnected_clusters, contradictions (placeholder).

    Design: merges old orphan + stale detection plans. Uses BacklinkIndex
    for link-based checks, pages.list for metadata. BFS for clusters.

    Args:
        include_checks: Specific checks to run (e.g. ["orphans", "stale"]).
                        If None, runs all checks.
        exclude_page_ids: Page IDs to exclude from checks (e.g. structural pages).
        exclude_paths: Path prefixes to exclude (e.g. "index", "log").

    Returns:
        JSON with per-check results and summary: {checks_run, orphans, stale, ...}
    """
    try:
        valid_checks = {"orphans", "stale", "link_density", "untagged", "most_connected", "contradictions", "disconnected_clusters"}
        if include_checks is not None:
            invalid = set(include_checks) - valid_checks
            if invalid:
                return json.dumps({"error": f"Invalid checks: {list(invalid)}. Valid: {list(sorted(valid_checks))}"})
            checks_to_run = set(include_checks)
        else:
            checks_to_run = valid_checks

        await wikijs.authenticate()

        exclude_ids = set(exclude_page_ids or [])
        exclude_prefixes = exclude_paths or []
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        response = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        pages = response.get("data", {}).get("pages", {}).get("list", [])

        # Filter out excluded pages
        def _is_excluded(page: dict) -> bool:
            if page.get("id") in exclude_ids:
                return True
            path = page.get("path", "")
            for prefix in exclude_prefixes:
                if path == prefix or path.startswith(prefix + "/"):
                    return True
            return False

        active_pages = [p for p in pages if not _is_excluded(p)]
        active_ids = {p["id"] for p in active_pages}
        page_meta = {p["id"]: p for p in active_pages}

        result = {"checks_run": sorted(checks_to_run)}
        total_issues = 0
        critical_issues = 0

        # --- Orphans check ---
        if "orphans" in checks_to_run:
            db = get_db()
            try:
                all_inbound = (
                    db.query(BacklinkIndex.target_page_id, func.count(BacklinkIndex.id).label("cnt"))
                    .filter(BacklinkIndex.target_page_id.in_(active_ids))
                    .group_by(BacklinkIndex.target_page_id)
                    .all()
                )
                inbound_set = {row.target_page_id for row in all_inbound}
            finally:
                db.close()

            orphans = []
            for pid in active_ids:
                if pid not in inbound_set:
                    meta = page_meta.get(pid, {})
                    orphans.append({
                        "pageId": pid,
                        "title": meta.get("title", "Unknown"),
                        "path": meta.get("path", ""),
                        "lastModified": meta.get("updatedAt", ""),
                    })
            orphans.sort(key=lambda x: x["title"].lower())
            result["orphans"] = orphans
            total_issues += len(orphans)

        # --- Stale check ---
        if "stale" in checks_to_run:
            stale = []
            for pid, meta in page_meta.items():
                updated_str = meta.get("updatedAt", "")
                if not updated_str:
                    continue
                try:
                    updated = datetime.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    days = (now_dt - updated).days
                    if days > 90:
                        stale.append({
                            "pageId": pid,
                            "title": meta.get("title", "Unknown"),
                            "path": meta.get("path", ""),
                            "daysStale": days,
                            "lastModified": updated_str,
                        })
                except (ValueError, AttributeError):
                    pass
            stale.sort(key=lambda x: x["daysStale"], reverse=True)
            result["stale"] = stale
            total_issues += len(stale)

        # --- Link density ---
        if "link_density" in checks_to_run:
            # Use BacklinkIndex for outbound link counts
            db = get_db()
            try:
                outbound_counts = (
                    db.query(BacklinkIndex.source_page_id, func.count(BacklinkIndex.id).label("cnt"))
                    .filter(BacklinkIndex.source_page_id.in_(active_ids))
                    .group_by(BacklinkIndex.source_page_id)
                    .all()
                )
                out_map = {row.source_page_id: row.cnt for row in outbound_counts}
            finally:
                db.close()

            zero = sum(1 for pid in active_ids if out_map.get(pid, 0) == 0)
            one_three = sum(1 for pid in active_ids if 1 <= out_map.get(pid, 0) <= 3)
            four_ten = sum(1 for pid in active_ids if 4 <= out_map.get(pid, 0) <= 10)
            eleven_plus = sum(1 for pid in active_ids if out_map.get(pid, 0) >= 11)
            avg = round(sum(out_map.values()) / len(active_ids), 1) if active_ids else 0

            result["link_density"] = {
                "average_links_per_page": avg,
                "distribution": {
                    "zero_links": zero, "one_to_three": one_three,
                    "four_to_ten": four_ten, "eleven_plus": eleven_plus,
                },
            }
            if zero > 0:
                critical_issues += 1

        # --- Untagged pages ---
        if "untagged" in checks_to_run:
            untagged = []
            for pid, meta in page_meta.items():
                if not meta.get("tags"):
                    untagged.append({
                        "pageId": pid, "title": meta.get("title", "Unknown"),
                        "path": meta.get("path", ""), "lastModified": meta.get("updatedAt", ""),
                    })
            untagged.sort(key=lambda x: x["title"].lower())
            result["untagged_pages"] = untagged
            total_issues += len(untagged)

        # --- Most connected ---
        if "most_connected" in checks_to_run:
            db = get_db()
            try:
                inbound_all = (
                    db.query(BacklinkIndex.target_page_id, func.count(BacklinkIndex.id).label("cnt"))
                    .filter(BacklinkIndex.target_page_id.in_(active_ids))
                    .group_by(BacklinkIndex.target_page_id)
                    .order_by(func.count(BacklinkIndex.id).desc())
                    .limit(10)
                    .all()
                )
                outbound_all = (
                    db.query(BacklinkIndex.source_page_id, func.count(BacklinkIndex.id).label("cnt"))
                    .filter(BacklinkIndex.source_page_id.in_(active_ids))
                    .group_by(BacklinkIndex.source_page_id)
                    .all()
                )
                ob_map = {row.source_page_id: row.cnt for row in outbound_all}
            finally:
                db.close()

            most = []
            for row in inbound_all:
                meta = page_meta.get(row.target_page_id, {})
                most.append({
                    "pageId": row.target_page_id,
                    "title": meta.get("title", "Unknown"),
                    "path": meta.get("path", ""),
                    "inboundLinks": row.cnt,
                    "outboundLinks": ob_map.get(row.target_page_id, 0),
                })
            result["most_connected"] = most

        # --- Disconnected clusters ---
        if "disconnected_clusters" in checks_to_run:
            # Build adjacency list from BacklinkIndex (bidirectional)
            db = get_db()
            try:
                all_edges = db.query(BacklinkIndex).filter(
                    BacklinkIndex.source_page_id.in_(active_ids),
                    BacklinkIndex.target_page_id.in_(active_ids),
                    BacklinkIndex.target_page_id.isnot(None),
                ).all()
            finally:
                db.close()

            adj: Dict[int, set] = {pid: set() for pid in active_ids}
            for edge in all_edges:
                src, tgt = edge.source_page_id, edge.target_page_id
                adj.setdefault(src, set()).add(tgt)
                adj.setdefault(tgt, set()).add(src)

            visited = set()
            clusters = []
            for pid in active_ids:
                if pid in visited:
                    continue
                # BFS to find connected component
                comp = set()
                queue = [pid]
                visited.add(pid)
                while queue:
                    current = queue.pop(0)
                    comp.add(current)
                    for neighbor in adj.get(current, set()):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                if len(comp) > 0:
                    meta_list = []
                    for cid in comp:
                        m = page_meta.get(cid, {})
                        meta_list.append({"pageId": cid, "title": m.get("title", "Unknown"), "path": m.get("path", "")})
                    clusters.append({
                        "clusterId": len(clusters) + 1,
                        "pages": sorted(meta_list, key=lambda x: x["title"].lower()),
                        "size": len(comp),
                    })

            # Only report clusters that are smaller than the main component
            clusters.sort(key=lambda c: c["size"])
            max_size = max((c["size"] for c in clusters), default=0)
            disconnected = [c for c in clusters if c["size"] < max_size]
            result["disconnected_clusters"] = disconnected
            if disconnected:
                critical_issues += len(disconnected)

        # --- Contradictions (placeholder) ---
        if "contradictions" in checks_to_run:
            result["contradictions"] = []

        # --- Summary ---
        warnings = total_issues if total_issues > 0 else 0
        result["summary"] = {
            "total_checks": len(checks_to_run),
            "issues_found": total_issues,
            "critical": critical_issues,
            "warnings": warnings,
        }

        logger.info(
            "wiki_health: %d checks, %d issues (%d critical)",
            len(checks_to_run), total_issues, critical_issues,
        )

        return json.dumps(result)

    except Exception as e:
        error_msg = f"wiki_health failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_get_affected_pages(page_id: int, max_results: int = 20, include_reasoning: bool = True) -> str:
    """
    Find pages impacted by changes to a source page using 4 complementary signals.

    Signals (all available, mode: "full"):
    - backlink (weight 1.0): pages that explicitly link to the source
    - graph_neighbor (weight 0.8): pages within 1 hop in the link graph
    - semantic_similarity (weight 0.6): pages with cosine similarity > 0.7
    - shared_tags (weight 0.3-0.5): pages sharing tags with the source

    Design: collects all 4 signals in parallel via asyncio.gather, deduplicates
    results by page ID, and ranks by weighted sum of signals.

    Args:
        page_id: The source page ID
        max_results: Max pages to return (default 20)
        include_reasoning: Include "reasons" array showing which signals matched

    Returns:
        JSON: {source, affected_pages, signal_breakdown, mode}
    """
    try:
        await wikijs.authenticate()

        # Resolve source page metadata
        response = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": page_id})
        page_data = response.get("data", {}).get("pages", {}).get("single")
        if not page_data:
            return json.dumps({"error": f"Page not found: {page_id}"})

        source_tags = [t["tag"] for t in page_data.get("tags", [])]
        source_content = page_data.get("content", "")
        source_title = page_data.get("title", "Unknown")

        # All pages metadata for tag matching and title resolution
        list_resp = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        all_pages = list_resp.get("data", {}).get("pages", {}).get("list", [])
        page_meta = {p["id"]: p for p in all_pages}

        # Collect scores and reasons
        scores: Dict[int, float] = {}
        reasons: Dict[int, list] = {}
        signal_counts: Dict[str, int] = {"backlinks": 0, "graph_neighbors": 0, "semantic_matches": 0, "shared_tags": 0}

        # --- Signal 1: Backlinks ---
        db = get_db()
        try:
            backlink_rows = db.query(BacklinkIndex).filter(
                BacklinkIndex.target_page_id == page_id
            ).all()
            backlink_ids = {row.source_page_id for row in backlink_rows}
        finally:
            db.close()

        for bid in backlink_ids:
            if bid == page_id:
                continue
            scores[bid] = scores.get(bid, 0) + 1.0
            if include_reasoning:
                reasons.setdefault(bid, []).append("backlink")
        signal_counts["backlinks"] = len(backlink_ids)

        # --- Signal 2: Graph neighbors (depth 1, both directions) ---
        db = get_db()
        try:
            outgoing = db.query(BacklinkIndex).filter(
                BacklinkIndex.source_page_id == page_id
            ).all()
            incoming = db.query(BacklinkIndex).filter(
                BacklinkIndex.target_page_id == page_id
            ).all()
            neighbor_ids = {row.target_page_id for row in outgoing if row.target_page_id is not None}
            neighbor_ids |= {row.source_page_id for row in incoming}
        finally:
            db.close()

        for nid in neighbor_ids:
            if nid == page_id or nid in backlink_ids:
                continue
            scores[nid] = scores.get(nid, 0) + 0.8
            if include_reasoning:
                reasons.setdefault(nid, []).append("graph_neighbor")
        signal_counts["graph_neighbors"] = len(neighbor_ids)

        # --- Signal 3: Semantic similarity (via Qdrant) ---
        try:
            from sentence_transformers import SentenceTransformer
            from qdrant_client import QdrantClient
            from wiki_mcp_server.config import settings

            client = QdrantClient(url=settings.QDRANT_URL)
            collection = settings.QDRANT_COLLECTION_WIKI_PAGES
            collections = [c.name for c in client.get_collections().collections]

            if collection in collections:
                info = client.get_collection(collection)
                if info.points_count > 0:
                    model = SentenceTransformer("all-MiniLM-L6-v2")
                    query_embedding = model.encode(source_content[:2000], normalize_embeddings=True).tolist()
                    response = client.query_points(
                        collection_name=collection,
                        query=query_embedding,
                        limit=50,
                        score_threshold=0.7,
                        with_payload=True,
                    )
                    for hit in response.points:
                        pid = hit.payload.get("page_id")
                        if pid and pid != page_id:
                            if pid not in backlink_ids and pid not in neighbor_ids:
                                scores[pid] = scores.get(pid, 0) + 0.6
                            if include_reasoning:
                                reasons.setdefault(pid, []).append("semantic_similarity")
                            signal_counts["semantic_matches"] += 1
        except ImportError:
            logger.warning("affected_pages: sentence-transformers not available, skipping semantic signal")
        except Exception as e:
            logger.warning("affected_pages: Qdrant semantic search failed: %s", e)

        # --- Signal 4: Shared tags ---
        if source_tags:
            for pid, meta in page_meta.items():
                if pid == page_id:
                    continue
                page_tags = meta.get("tags") or []
                shared = set(source_tags) & set(page_tags)
                if shared:
                    weight = 0.5 if len(shared) >= 3 else 0.3
                    scores[pid] = scores.get(pid, 0) + weight
                    if include_reasoning:
                        reasons.setdefault(pid, []).append("shared_tags")
                    signal_counts["shared_tags"] += 1

        # --- Build result ---
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:max_results]

        affected = []
        top_ids = [pid for pid, _ in ranked]
        from wiki_mcp_server.tools_pages import wikijs_bulk_get_pages
        title_map = {}
        if top_ids:
            try:
                bulk_json = await wikijs_bulk_get_pages(top_ids, include_content=False)
                bulk_data = json.loads(bulk_json)
                title_map = {r["pageId"]: r for r in bulk_data.get("results", [])}
            except Exception:
                pass

        for pid, score in ranked:
            t = title_map.get(pid, page_meta.get(pid, {}))
            entry = {
                "pageId": pid,
                "title": t.get("title", "Unknown"),
                "path": t.get("path", ""),
                "relevance_score": round(score, 4),
            }
            if include_reasoning:
                entry["reasons"] = reasons.get(pid, [])
            affected.append(entry)

        logger.info(
            "get_affected_pages %d (%s): %d affected (%d signals)",
            page_id, source_title, len(affected), sum(signal_counts.values()),
        )

        return json.dumps({
            "source": {"pageId": page_id, "title": source_title, "path": page_data.get("path", "")},
            "affected_pages": affected,
            "signal_breakdown": signal_counts,
            "mode": "full",
        })

    except Exception as e:
        error_msg = f"get_affected_pages failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_export_wiki(output_dir: str, include_frontmatter: bool = True) -> str:
    """
    Export all wiki pages as .md files to a local directory, preserving folder hierarchy.

    Pages are written as markdown files in the output directory. The wiki path
    determines the file location: page at path "space/sub/page" becomes
    output_dir/space/sub/page.md. Intermediate directories are created automatically.

    When include_frontmatter is True (default), each file starts with YAML frontmatter:
    ---
    title: Page Title
    wiki_path: space/sub/page
    tags: [tag1, tag2]
    created: 2026-05-20T10:00:00Z
    updated: 2026-05-23T12:00:00Z
    ---

    Args:
        output_dir: Directory where .md files will be written (created if needed)
        include_frontmatter: Add YAML frontmatter with metadata (default True)

    Returns:
        JSON with summary: exported_count, output_dir, errors list
    """
    try:
        await wikijs.authenticate()

        list_response = await wikijs.graphql_request(_LIST_ALL_PAGES_WITH_TAGS_QUERY)
        pages = list_response.get("data", {}).get("pages", {}).get("list", [])

        if not pages:
            logger.info("export_wiki: no pages found")
            return json.dumps({"exported_count": 0, "output_dir": output_dir, "errors": []})

        page_ids = [p["id"] for p in pages]
        path_map = {p["id"]: p["path"] for p in pages}
        title_map = {p["id"]: p["title"] for p in pages}
        tag_map = {p["id"]: p.get("tags", []) or [] for p in pages}

        logger.info("export_wiki: exporting %d pages to %s", len(page_ids), output_dir)

        # Fetch all pages in parallel
        tasks = [wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": pid}) for pid in page_ids]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        os.makedirs(output_dir, exist_ok=True)

        exported = 0
        errors = []

        for pid, response in zip(page_ids, responses):
            if isinstance(response, Exception):
                logger.warning("export_wiki: failed to fetch page %d: %s", pid, str(response))
                errors.append({"pageId": pid, "error": str(response)})
                continue

            page_data = response.get("data", {}).get("pages", {}).get("single")
            if not page_data:
                logger.warning("export_wiki: page %d not found", pid)
                errors.append({"pageId": pid, "error": "Page not found"})
                continue

            content = page_data.get("content", "")
            path = path_map.get(pid, page_data.get("path", f"page-{pid}"))
            title = title_map.get(pid, page_data.get("title", "Untitled"))
            tags = tag_map.get(pid, [])
            created_at = page_data.get("createdAt", "")
            updated_at = page_data.get("updatedAt", "")

            if include_frontmatter:
                frontmatter = (
                    f"---\ntitle: {title}\nwiki_path: {path}\n"
                    f"tags: {json.dumps(tags)}\n"
                    f"created: {created_at}\nupdated: {updated_at}\n---\n\n"
                )
            else:
                frontmatter = ""

            filepath = os.path.join(output_dir, path + ".md")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(frontmatter + content)

            exported += 1

        logger.info("export_wiki: exported %d pages, %d errors", exported, len(errors))
        return json.dumps({
            "exported_count": exported,
            "output_dir": output_dir,
            "errors": errors,
        })

    except Exception as e:
        error_msg = f"export_wiki failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_export_page(page_id: int, output_path: str = "", include_frontmatter: bool = True) -> str:
    """
    Export a single wiki page as a .md file.

    Args:
        page_id: Page ID to export
        output_path: Output file path (auto-generated from page path if empty)
        include_frontmatter: Add YAML frontmatter with metadata (default True)

    Returns:
        JSON with file_path written and page metadata
    """
    try:
        await wikijs.authenticate()

        response = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": page_id})
        page_data = response.get("data", {}).get("pages", {}).get("single")

        if not page_data:
            return json.dumps({"error": f"Page not found: {page_id}"})

        content = page_data.get("content", "")
        path = page_data.get("path", f"page-{page_id}")
        title = page_data.get("title", "Untitled")
        tags = [t["tag"] for t in page_data.get("tags", [])]
        created_at = page_data.get("createdAt", "")
        updated_at = page_data.get("updatedAt", "")

        if not output_path:
            output_path = path + ".md"

        if include_frontmatter:
            frontmatter = (
                f"---\ntitle: {title}\nwiki_path: {path}\n"
                f"tags: {json.dumps(tags)}\n"
                f"created: {created_at}\nupdated: {updated_at}\n---\n\n"
            )
        else:
            frontmatter = ""

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(frontmatter + content)

        logger.info("export_page: exported page %d to %s", page_id, output_path)
        return json.dumps({
            "file_path": output_path,
            "page_id": page_id,
            "title": title,
        })

    except Exception as e:
        error_msg = f"export_page failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_import_page(file_path: str, target_path: str = "", parent_id: str = "", update_existing: bool = True) -> str:
    """
    Import a .md file as a Wiki.js page.

    Reads a markdown file from the local filesystem. If the file has YAML frontmatter
    (delimited by --- at the start), extracts title, tags, and wiki_path from it.
    The body after the frontmatter becomes the page content.

    If no frontmatter is present, the title is derived from the filename (without .md
    extension) and the path is auto-generated via slug.

    Args:
        file_path: Absolute or relative path to the .md file
        target_path: Override the wiki path (uses frontmatter wiki_path or filename if empty)
        parent_id: Parent page ID for hierarchical organization (optional)
        update_existing: If True and a page at target_path exists, update it instead of failing (default True)

    Returns:
        JSON with page_id, path, title, and action (created/updated/error)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Parse frontmatter
        fm_title = None
        fm_tags = []
        fm_wiki_path = None
        body = raw_content

        if raw_content.startswith("---\n"):
            parts = raw_content.split("---\n", 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                body = parts[2]
                for line in fm_text.strip().split("\n"):
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip()
                        if key == "title" and not fm_title:
                            fm_title = value
                        elif key == "wiki_path" and not fm_wiki_path:
                            fm_wiki_path = value
                        elif key == "tags":
                            # Handle [a, b] and a, b formats
                            if value.startswith("[") and value.endswith("]"):
                                value = value[1:-1]
                            fm_tags = [t.strip().strip("\"'") for t in value.split(",") if t.strip().strip("\"'")]

        # Determine title
        if fm_title:
            title = fm_title
        else:
            filename = os.path.basename(file_path)
            name_no_ext = os.path.splitext(filename)[0]
            title = name_no_ext.replace("-", " ").replace("_", " ").title()

        # Determine path
        if target_path:
            path = target_path
        elif fm_wiki_path:
            path = fm_wiki_path
        else:
            path = slugify(title)

        # If parent_id provided, prepend parent path
        if parent_id:
            await wikijs.authenticate()
            parent_query = """
            query($id: Int!) {
                pages {
                    single(id: $id) {
                        path
                    }
                }
            }
            """
            parent_response = await wikijs.graphql_request(parent_query, {"id": int(parent_id)})
            parent_data = parent_response.get("data", {}).get("pages", {}).get("single")
            if parent_data:
                path = parent_data["path"] + "/" + path.lstrip("/")
            else:
                return json.dumps({"error": f"Parent page not found: {parent_id}"})

        await wikijs.authenticate()

        # Check if page exists at path
        resolve_response = await wikijs.graphql_request(_RESOLVE_PATH_QUERY, {"path": path})
        existing = resolve_response.get("data", {}).get("pages", {}).get("singleByPath")

        if existing and update_existing:
            existing_id = existing["id"]

            # Fetch current page to merge tags
            current_response = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": existing_id})
            current_page = current_response.get("data", {}).get("pages", {}).get("single")
            if not current_page:
                return json.dumps({"error": f"Existing page {existing_id} not found during update"})

            current_tags = [t["tag"] for t in current_page.get("tags", [])]
            merged_tags = list(dict.fromkeys(current_tags + fm_tags))

            mutation = """
            mutation($id: Int!, $content: String!, $description: String!, $editor: String!, $isPrivate: Boolean!, $isPublished: Boolean!, $locale: String!, $path: String!, $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!) {
                pages {
                    update(id: $id, content: $content, description: $description, editor: $editor, isPrivate: $isPrivate, isPublished: $isPublished, locale: $locale, path: $path, scriptCss: $scriptCss, scriptJs: $scriptJs, tags: $tags, title: $title) {
                        responseResult {
                            succeeded
                            errorCode
                            slug
                            message
                        }
                        page {
                            id
                            path
                            title
                            updatedAt
                        }
                    }
                }
            }
            """

            variables = {
                "id": existing_id,
                "content": body,
                "description": current_page.get("description", ""),
                "editor": "markdown",
                "isPrivate": current_page.get("isPrivate", False),
                "isPublished": current_page.get("isPublished", True),
                "locale": current_page.get("locale", "en"),
                "path": path,
                "scriptCss": "",
                "scriptJs": "",
                "tags": merged_tags,
                "title": title,
            }

            write_resp = await wikijs.graphql_request(mutation, variables)
            update_result = write_resp.get("data", {}).get("pages", {}).get("update", {})
            response_result = update_result.get("responseResult", {})

            if not response_result.get("succeeded"):
                return json.dumps({"error": f"Update failed: {response_result.get('message', 'Unknown')}"})

            page_info = update_result.get("page", {})
            page_id_val = page_info.get("id", existing_id)

            await _sync_backlinks_for_page(page_id_val, body)
            _invalidate_stats_cache()

            logger.info("import_page: updated page %d at path %s", page_id_val, path)
            return json.dumps({
                "page_id": page_id_val,
                "path": path,
                "title": title,
                "action": "updated",
            })

        elif existing and not update_existing:
            return json.dumps({
                "error": f"Page already exists at path '{path}' (ID: {existing['id']}). Set update_existing=True to update it.",
                "existing_page_id": existing["id"],
            })

        # Create new page
        mutation = """
        mutation($content: String!, $description: String!, $editor: String!, $isPublished: Boolean!, $isPrivate: Boolean!, $locale: String!, $path: String!, $publishEndDate: Date, $publishStartDate: Date, $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!) {
            pages {
                create(content: $content, description: $description, editor: $editor, isPublished: $isPublished, isPrivate: $isPrivate, locale: $locale, path: $path, publishEndDate: $publishEndDate, publishStartDate: $publishStartDate, scriptCss: $scriptCss, scriptJs: $scriptJs, tags: $tags, title: $title) {
                    responseResult {
                        succeeded
                        errorCode
                        slug
                        message
                    }
                    page {
                        id
                        path
                        title
                    }
                }
            }
        }
        """

        variables = {
            "content": body,
            "description": "",
            "editor": "markdown",
            "isPublished": True,
            "isPrivate": False,
            "locale": "en",
            "path": path,
            "publishEndDate": None,
            "publishStartDate": None,
            "scriptCss": "",
            "scriptJs": "",
            "tags": fm_tags,
            "title": title,
        }

        create_resp = await wikijs.graphql_request(mutation, variables)
        create_result = create_resp.get("data", {}).get("pages", {}).get("create", {})
        response_result = create_result.get("responseResult", {})

        if not response_result.get("succeeded"):
            return json.dumps({"error": f"Create failed: {response_result.get('message', 'Unknown')}"})

        page_info = create_result.get("page", {})
        page_id_val = page_info.get("id")

        await _sync_backlinks_for_page(page_id_val, body)
        _invalidate_stats_cache()

        logger.info("import_page: created page %d at path %s", page_id_val, path)
        return json.dumps({
            "page_id": page_id_val,
            "path": path,
            "title": title,
            "action": "created",
        })

    except Exception as e:
        error_msg = f"import_page failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_import_directory(dir_path: str, base_parent_path: str = "", update_existing: bool = True) -> str:
    """
    Import all .md files recursively from a directory, preserving folder hierarchy.

    Directory structure maps to wiki page hierarchy:
    - File dir/sub/file.md becomes a wiki page at path sub/file
    - Root .md files become top-level pages
    - Subdirectories become nested paths

    Parent pages are created before children. Each parent directory gets a minimal
    index page listing its child pages.

    Args:
        dir_path: Root directory containing .md files
        base_parent_path: Base wiki path prefix (e.g., "imported") to nest all pages under (optional)
        update_existing: Update existing pages with same path instead of failing (default True)

    Returns:
        JSON with imported, updated, skipped, errors counts and details
    """
    try:
        # Collect all .md files
        md_files = []
        for root, dirs, files in os.walk(dir_path):
            for fname in files:
                if fname.endswith(".md"):
                    md_files.append(os.path.join(root, fname))

        if not md_files:
            return json.dumps({
                "imported": 0, "updated": 0, "skipped": 0, "errors": 0,
                "details": {"imported": [], "updated": [], "skipped": [], "errors": []},
            })

        # Compute wiki paths and sort: parents first
        file_entries = []
        for fpath in md_files:
            rel_path = os.path.relpath(fpath, dir_path)
            wiki_path = os.path.splitext(rel_path)[0].replace(os.sep, "/")
            if base_parent_path:
                wiki_path = base_parent_path.rstrip("/") + "/" + wiki_path
            file_entries.append((fpath, wiki_path))

        file_entries.sort(key=lambda x: x[1].count("/"))

        await wikijs.authenticate()

        imported = []
        updated = []
        skipped_list = []
        error_list = []

        for fpath, wiki_path in file_entries:
            try:
                # Read file and parse frontmatter
                with open(fpath, "r", encoding="utf-8") as f:
                    raw_content = f.read()

                fm_title = None
                fm_tags = []
                body = raw_content

                if raw_content.startswith("---\n"):
                    parts = raw_content.split("---\n", 2)
                    if len(parts) >= 3:
                        fm_text = parts[1]
                        body = parts[2]
                        for line in fm_text.strip().split("\n"):
                            if ":" in line:
                                key, _, value = line.partition(":")
                                key = key.strip()
                                value = value.strip()
                                if key == "title" and not fm_title:
                                    fm_title = value
                                elif key == "tags":
                                    if value.startswith("[") and value.endswith("]"):
                                        value = value[1:-1]
                                    fm_tags = [t.strip().strip("\"'") for t in value.split(",") if t.strip().strip("\"'")]

                # Determine title
                if fm_title:
                    title = fm_title
                else:
                    filename = os.path.basename(fpath)
                    name_no_ext = os.path.splitext(filename)[0]
                    title = name_no_ext.replace("-", " ").replace("_", " ").title()

                # Check if page exists
                resolve_resp = await wikijs.graphql_request(_RESOLVE_PATH_QUERY, {"path": wiki_path})
                existing = resolve_resp.get("data", {}).get("pages", {}).get("singleByPath")

                if existing:
                    if update_existing:
                        existing_id = existing["id"]
                        current_resp = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": existing_id})
                        current_page = current_resp.get("data", {}).get("pages", {}).get("single")
                        if not current_page:
                            error_list.append({"file": fpath, "path": wiki_path, "error": f"Page {existing_id} not found during update"})
                            continue

                        current_tags = [t["tag"] for t in current_page.get("tags", [])]
                        merged_tags = list(dict.fromkeys(current_tags + fm_tags))

                        mutation = """
                        mutation($id: Int!, $content: String!, $description: String!, $editor: String!, $isPrivate: Boolean!, $isPublished: Boolean!, $locale: String!, $path: String!, $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!) {
                            pages {
                                update(id: $id, content: $content, description: $description, editor: $editor, isPrivate: $isPrivate, isPublished: $isPublished, locale: $locale, path: $path, scriptCss: $scriptCss, scriptJs: $scriptJs, tags: $tags, title: $title) {
                                    responseResult {
                                        succeeded
                                        errorCode
                                        slug
                                        message
                                    }
                                    page {
                                        id
                                        path
                                        title
                                        updatedAt
                                    }
                                }
                            }
                        }
                        """

                        variables = {
                            "id": existing_id,
                            "content": body,
                            "description": current_page.get("description", ""),
                            "editor": "markdown",
                            "isPrivate": current_page.get("isPrivate", False),
                            "isPublished": current_page.get("isPublished", True),
                            "locale": current_page.get("locale", "en"),
                            "path": wiki_path,
                            "scriptCss": "",
                            "scriptJs": "",
                            "tags": merged_tags,
                            "title": title,
                        }

                        write_resp = await wikijs.graphql_request(mutation, variables)
                        update_result = write_resp.get("data", {}).get("pages", {}).get("update", {})
                        response_result = update_result.get("responseResult", {})

                        if not response_result.get("succeeded"):
                            error_list.append({"file": fpath, "path": wiki_path, "error": f"Update failed: {response_result.get('message', 'Unknown')}"})
                            continue

                        page_info = update_result.get("page", {})
                        page_id_val = page_info.get("id", existing_id)

                        await _sync_backlinks_for_page(page_id_val, body)
                        _invalidate_stats_cache()

                        updated.append({"page_id": page_id_val, "path": wiki_path, "title": title, "file": fpath})
                    else:
                        skipped_list.append({"file": fpath, "path": wiki_path, "reason": f"Page already exists (ID: {existing['id']})"})
                else:
                    # Create new page
                    mutation = """
                    mutation($content: String!, $description: String!, $editor: String!, $isPublished: Boolean!, $isPrivate: Boolean!, $locale: String!, $path: String!, $publishEndDate: Date, $publishStartDate: Date, $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!) {
                        pages {
                            create(content: $content, description: $description, editor: $editor, isPublished: $isPublished, isPrivate: $isPrivate, locale: $locale, path: $path, publishEndDate: $publishEndDate, publishStartDate: $publishStartDate, scriptCss: $scriptCss, scriptJs: $scriptJs, tags: $tags, title: $title) {
                                responseResult {
                                    succeeded
                                    errorCode
                                    slug
                                    message
                                }
                                page {
                                    id
                                    path
                                    title
                                }
                            }
                        }
                    }
                    """

                    variables = {
                        "content": body,
                        "description": "",
                        "editor": "markdown",
                        "isPublished": True,
                        "isPrivate": False,
                        "locale": "en",
                        "path": wiki_path,
                        "publishEndDate": None,
                        "publishStartDate": None,
                        "scriptCss": "",
                        "scriptJs": "",
                        "tags": fm_tags,
                        "title": title,
                    }

                    create_resp = await wikijs.graphql_request(mutation, variables)
                    create_result = create_resp.get("data", {}).get("pages", {}).get("create", {})
                    response_result = create_result.get("responseResult", {})

                    if not response_result.get("succeeded"):
                        error_list.append({"file": fpath, "path": wiki_path, "error": f"Create failed: {response_result.get('message', 'Unknown')}"})
                        continue

                    page_info = create_result.get("page", {})
                    page_id_val = page_info.get("id")

                    await _sync_backlinks_for_page(page_id_val, body)
                    _invalidate_stats_cache()

                    imported.append({"page_id": page_id_val, "path": wiki_path, "title": title, "file": fpath})

            except Exception as file_error:
                logger.warning("import_directory: error processing %s: %s", fpath, str(file_error))
                error_list.append({"file": fpath, "path": wiki_path, "error": str(file_error)})

        logger.info(
            "import_directory: %d imported, %d updated, %d skipped, %d errors",
            len(imported), len(updated), len(skipped_list), len(error_list),
        )

        return json.dumps({
            "imported": len(imported),
            "updated": len(updated),
            "skipped": len(skipped_list),
            "errors": len(error_list),
            "details": {
                "imported": imported,
                "updated": updated,
                "skipped": skipped_list,
                "errors": error_list,
            },
        })

    except Exception as e:
        error_msg = f"import_directory failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
