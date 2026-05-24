"""Wiki.js MCP tools — link graph tools (P2).

Provides graph-awareness tools for the LLM Wiki pattern:
- extract_page_links: extract and classify links from a page
- get_page_graph: BFS traversal of the local link neighborhood
- find_shortest_path: bidirectional BFS between two pages

All graph operations use the existing SQLite BacklinkIndex.
No new database tables required.
"""

import asyncio
import json
import re
from collections import deque
from typing import Any, Dict, List, Optional, Set

from wiki_mcp_server.client import wikijs
from wiki_mcp_server.config import logger
from wiki_mcp_server.db import BacklinkIndex, get_db
from wiki_mcp_server.server import mcp

# Regex for external links (HTTP/HTTPS URLs in markdown)
_EXTERNAL_LINK_PATTERN = re.compile(r'\[([^\]]*)\]\((https?://[^)]+)\)')


def _extract_external_links(content: str) -> List[dict]:
    """Extract external HTTP/HTTPS links from markdown content.

    Returns list of dicts with link_text and url for each external link found.
    Filters out image links (![alt](url)).
    """
    links = []
    for match in _EXTERNAL_LINK_PATTERN.finditer(content):
        raw_text = match.group(0)
        if raw_text.startswith("!"):
            continue
        link_text = match.group(1).strip()
        url = match.group(2).strip()
        if url:
            links.append({"link_text": link_text, "url": url})
    return links


async def _batch_resolve_titles(page_ids: List[int]) -> Dict[int, dict]:
    """Batch-resolve page titles using wikijs_bulk_get_pages.

    Returns dict mapping page_id -> {title, path}.
    """
    if not page_ids:
        return {}
    unique = list(dict.fromkeys(page_ids))  # Deduplicate
    from wiki_mcp_server.tools_pages import wikijs_bulk_get_pages
    bulk_json = await wikijs_bulk_get_pages(unique, include_content=False)
    bulk_data = json.loads(bulk_json)
    return {r["pageId"]: r for r in bulk_data.get("results", [])}


@mcp.tool()
async def wikijs_extract_page_links(page_id: int, link_type: str = "all") -> str:
    """
    Extract all links from a wiki page, classified as internal or external.

    Internal links are markdown [text](path) links to other wiki pages.
    External links are markdown [text](https://...) links to external URLs.

    Internal link targets are resolved to page IDs via the Wiki.js API.
    Broken links (target page doesn't exist) are flagged with broken: true.

    Design: uses _extract_links from tools_pages for internal links,
    and a separate regex for external HTTP/HTTPS links.

    Args:
        page_id: Page ID to extract links from
        link_type: "all" (default), "internal", or "external"

    Returns:
        JSON: {pageId, title, internalLinks, externalLinks, totalInternal, totalExternal}
    """
    try:
        if link_type not in ("all", "internal", "external"):
            return json.dumps({"error": f"Invalid link_type '{link_type}'. Must be 'all', 'internal', or 'external'."})

        await wikijs.authenticate()

        # Fetch page content
        from wiki_mcp_server.tools_pages import _GET_PAGE_BY_ID_QUERY
        resp = await wikijs.graphql_request(_GET_PAGE_BY_ID_QUERY, {"id": page_id})
        page_data = resp.get("data", {}).get("pages", {}).get("single")
        if not page_data:
            return json.dumps({"error": f"Page not found: {page_id}"})

        content = page_data.get("content", "")
        title = page_data.get("title", "Unknown")

        internal_links = []
        external_links = []

        if link_type in ("all", "internal"):
            from wiki_mcp_server.tools_pages import _extract_links, _resolve_paths_to_ids
            raw_links = _extract_links(content)
            if raw_links:
                paths = [link["target_path"] for link in raw_links]
                path_id_map = await _resolve_paths_to_ids(paths)

                for link in raw_links:
                    target_path = link["target_path"]
                    target_id = path_id_map.get(target_path)
                    entry = {
                        "targetPath": target_path,
                        "linkText": link["link_text"],
                        "position": link["position"],
                    }
                    if target_id is not None:
                        entry["targetPageId"] = target_id
                        entry["broken"] = False
                    else:
                        entry["targetPageId"] = None
                        entry["broken"] = True
                    internal_links.append(entry)

        if link_type in ("all", "external"):
            raw_external = _extract_external_links(content)
            for link in raw_external:
                external_links.append({
                    "url": link["url"],
                    "linkText": link["link_text"],
                })

        logger.info(
            "extract_page_links page %d: %d internal, %d external",
            page_id, len(internal_links), len(external_links),
        )

        return json.dumps({
            "pageId": page_id,
            "title": title,
            "internalLinks": internal_links,
            "externalLinks": external_links,
            "totalInternal": len(internal_links),
            "totalExternal": len(external_links),
        })

    except Exception as e:
        error_msg = f"extract_page_links failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_get_page_graph(page_id: int, depth: int = 1, direction: str = "both", max_nodes: int = 50) -> str:
    """
    Explore the local link graph around a page using BFS traversal.

    Direction modes:
    - "outgoing": pages this page links to
    - "incoming": pages that link to this page (backlinks)
    - "both": union of outgoing and incoming

    BFS with cycle detection (visited set). Stops at depth limit or max_nodes cap.
    Reports truncation if max_nodes was reached.

    Design: uses BacklinkIndex for both outgoing (source_page_id) and
    incoming (target_page_id) queries. No new SQLite tables.

    Args:
        page_id: Root page ID
        depth: How many hops from root (default 1, max 2)
        direction: "outgoing", "incoming", or "both"
        max_nodes: Safety cap to prevent explosion (default 50)

    Returns:
        JSON: {root, nodes, edges, stats: {totalNodes, maxDepthReached, truncated}}
    """
    try:
        if depth < 1 or depth > 2:
            return json.dumps({"error": "Depth must be 1 or 2"})
        if direction not in ("outgoing", "incoming", "both"):
            return json.dumps({"error": f"Invalid direction '{direction}'. Must be 'outgoing', 'incoming', or 'both'."})

        await wikijs.authenticate()

        # Resolve root page title
        titles = await _batch_resolve_titles([page_id])
        root_title = titles.get(page_id, {}).get("title", "Unknown")

        visited: Set[int] = {page_id}
        nodes: List[dict] = []
        edges: List[dict] = []
        frontier = [page_id]
        truncated = False
        max_depth_reached = 0

        for current_depth in range(1, depth + 1):
            if not frontier:
                break
            next_frontier = []
            for current_id in frontier:
                neighbors = set()
                db = get_db()
                try:
                    if direction in ("outgoing", "both"):
                        outgoing = db.query(BacklinkIndex).filter(
                            BacklinkIndex.source_page_id == current_id
                        ).all()
                        for row in outgoing:
                            if row.target_page_id is not None:
                                neighbors.add(row.target_page_id)
                    if direction in ("incoming", "both"):
                        incoming = db.query(BacklinkIndex).filter(
                            BacklinkIndex.target_page_id == current_id
                        ).all()
                        for row in incoming:
                            neighbors.add(row.source_page_id)
                finally:
                    db.close()

                for neighbor_id in neighbors:
                    if neighbor_id in visited:
                        continue
                    if len(nodes) >= max_nodes:
                        truncated = True
                        break
                    visited.add(neighbor_id)
                    nodes.append({"pageId": neighbor_id, "direction": "outgoing" if current_id == page_id else "both", "depth": current_depth})
                    edges.append({"source": current_id, "target": neighbor_id})
                    next_frontier.append(neighbor_id)

                if truncated:
                    break

            frontier = next_frontier
            max_depth_reached = current_depth

        # Batch-resolve titles for all nodes
        node_ids = [n["pageId"] for n in nodes]
        node_titles = await _batch_resolve_titles(node_ids)
        for node in nodes:
            nt = node_titles.get(node["pageId"], {})
            node["title"] = nt.get("title", "Unknown")
            node["path"] = nt.get("path", "")

        logger.info(
            "get_page_graph page %d (depth=%d, dir=%s): %d nodes, %d edges%s",
            page_id, depth, direction, len(nodes), len(edges),
            " [TRUNCATED]" if truncated else "",
        )

        return json.dumps({
            "root": {"pageId": page_id, "title": root_title},
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "totalNodes": len(nodes),
                "maxDepthReached": max_depth_reached,
                "truncated": truncated,
            },
        })

    except Exception as e:
        error_msg = f"get_page_graph failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def wikijs_find_shortest_path(from_page_id: int, to_page_id: int, max_depth: int = 5) -> str:
    """
    Find the shortest path between two pages through the link graph.

    Uses bidirectional BFS: forward from source (outgoing links) and
    backward from target (incoming links / backlinks). Meeting point
    determines the path.

    Design: bidirectional BFS reduces complexity from O(b^d) to O(b^(d/2)).
    Uses BacklinkIndex for both directions. No new SQLite tables.

    Args:
        from_page_id: Starting page ID
        to_page_id: Destination page ID
        max_depth: Max search depth (default 5)

    Returns:
        JSON: {pathFound, length, path: [{pageId, title, step}], ...}
    """
    try:
        if from_page_id == to_page_id:
            return json.dumps({"error": "Source and target are the same page"})

        await wikijs.authenticate()

        # Bidirectional BFS
        # Forward: source -> outgoing links
        # Backward: target -> incoming links (backlinks)

        def _get_neighbors(pid: int, forward: bool) -> Set[int]:
            """Get neighbors in the specified direction from BacklinkIndex."""
            db = get_db()
            try:
                if forward:
                    rows = db.query(BacklinkIndex).filter(
                        BacklinkIndex.source_page_id == pid
                    ).all()
                    return {row.target_page_id for row in rows if row.target_page_id is not None}
                else:
                    rows = db.query(BacklinkIndex).filter(
                        BacklinkIndex.target_page_id == pid
                    ).all()
                    return {row.source_page_id for row in rows}
            finally:
                db.close()

        # forward_parents: pid -> parent (for path reconstruction)
        forward_parents: Dict[int, Optional[int]] = {from_page_id: None}
        forward_frontier = {from_page_id}

        backward_parents: Dict[int, Optional[int]] = {to_page_id: None}
        backward_frontier = {to_page_id}

        meeting_point = None

        for iteration in range(max_depth):
            if not forward_frontier and not backward_frontier:
                break

            # Expand forward
            if forward_frontier:
                next_forward: Set[int] = set()
                for pid in forward_frontier:
                    for neighbor in _get_neighbors(pid, forward=True):
                        if neighbor in forward_parents:
                            continue
                        forward_parents[neighbor] = pid
                        next_forward.add(neighbor)
                        if neighbor in backward_parents:
                            meeting_point = neighbor
                            break
                    if meeting_point:
                        break
                forward_frontier = next_forward

            if meeting_point:
                break

            # Expand backward
            if backward_frontier:
                next_backward: Set[int] = set()
                for pid in backward_frontier:
                    for neighbor in _get_neighbors(pid, forward=False):
                        if neighbor in backward_parents:
                            continue
                        backward_parents[neighbor] = pid
                        next_backward.add(neighbor)
                        if neighbor in forward_parents:
                            meeting_point = neighbor
                            break
                    if meeting_point:
                        break
                backward_frontier = next_backward

            if meeting_point:
                break

        if meeting_point is None:
            logger.info("find_shortest_path %d -> %d: no path found within depth %d", from_page_id, to_page_id, max_depth)
            return json.dumps({
                "pathFound": False,
                "fromPageId": from_page_id,
                "toPageId": to_page_id,
                "maxDepthSearched": max_depth,
            })

        # Reconstruct path
        path_ids = []
        # Forward: from meeting_point back to source
        current = meeting_point
        while current is not None:
            path_ids.append(current)
            current = forward_parents.get(current)
        path_ids.reverse()

        # Backward: from meeting_point forward to target (skip meeting_point itself)
        current = backward_parents.get(meeting_point)
        while current is not None:
            path_ids.append(current)
            current = backward_parents.get(current)

        # Resolve titles
        titles = await _batch_resolve_titles(path_ids)
        path = []
        for step, pid in enumerate(path_ids):
            pt = titles.get(pid, {})
            path.append({
                "pageId": pid,
                "title": pt.get("title", "Unknown"),
                "step": step,
            })

        logger.info(
            "find_shortest_path %d -> %d: path found, length=%d",
            from_page_id, to_page_id, len(path),
        )

        return json.dumps({
            "pathFound": True,
            "length": len(path) - 1,
            "path": path,
            "fromPageId": from_page_id,
            "toPageId": to_page_id,
        })

    except Exception as e:
        error_msg = f"find_shortest_path failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
