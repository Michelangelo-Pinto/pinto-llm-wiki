# AGENTS.md — LLM Wiki Schema

This file is the **schema layer** of the LLM Wiki pattern. Every agent operating on this wiki must read and follow the conventions described here.

---

## 1. What is wiki-js-mcp

wiki-js-mcp is an MCP (Model Context Protocol) server that wraps a self-hosted Wiki.js instance, exposing its GraphQL API as MCP tools. It runs alongside the Docker wiki stack (`wiki-js-mcp/docker-compose.yml`).

**Current state**: 45 tools across 6 categories (21 original + 24 new). **ALL planned features implemented.** See `VECTOR_ENGINE_IMPACT.md` for features that can be enhanced.

```
Cursor IDE --> MCP Server (SSE :8000) --> Wiki.js GraphQL (:3000) --> PostgreSQL
                                     --> SQLite (file->page mappings)
```

Tool modules live in `mcp-server/src/wiki_mcp_server/tools_*.py`. Every tool is an `@mcp.tool()` async function returning `json.dumps(...)`.

## 2. The LLM Wiki pattern

The LLM Wiki is an agent-driven, incrementally maintained knowledge base. The LLM ingests sources, writes and updates wiki pages, maintains cross-references, and keeps the wiki consistent over time.

### Three layers

| Layer | Description | Who modifies it |
|-------|-------------|-----------------|
| **Raw sources** | Immutable source documents (articles, papers, data) | Human only |
| **The wiki** | Structured, interlinked markdown pages | LLM agent entirely |
| **The schema** | This file — conventions, workflow rules, tool usage | Human + LLM |

### Three operations

- **Ingest**: process a new source -> write summary page -> update entity/concept pages -> update index -> append to log. A single source may touch 10-15 pages.
- **Query**: search the wiki -> read relevant pages -> synthesize answer with citations. Good answers get filed back as new pages.
- **Lint**: health-check the wiki -> contradictions, stale claims, orphan pages, missing cross-references.

### Why this works

The boring part of maintaining a knowledge base is not reading or thinking — it is the bookkeeping: updating cross-references, keeping summaries current, noticing contradictions, maintaining coherence across dozens of pages. LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass.

### Special files

- **index.md**: content-oriented catalog, organized by category. Updated on every ingest.
- **log.md**: chronological append-only register of ingests, queries, lint runs. Consistent prefix for parsing: `## [YYYY-MM-DD] ingest | Title`.

## Import/Export conventions

All pages use `editor: "markdown"` with standard markdown formatting to ensure compatibility with Obsidian and any markdown editor.

### Export format

Exported files use YAML frontmatter:

```
---
title: Page Title
wiki_path: space/sub/page
tags: [tag1, tag2]
created: 2026-05-20T10:00:00Z
updated: 2026-05-23T12:00:00Z
---
```

### Content rules

1. **Link format**: Use absolute wiki paths: `[text](/path/to/page)`. Never use wiki.js internal IDs.
2. **No proprietary syntax**: No `:::` callouts, no `[toc]`, no `{docsify-ignore}`.
3. **Standard markdown only**: tables, lists, code fences, blockquotes, bold/italic.
4. **Tags in API metadata**: Tags belong to the page's tag list (via API), not in the markdown body as `#tag` or inline metadata.
5. **Editor always `markdown`**: The `editor` field in create/update mutations is always `"markdown"`.

## 3. Tool categories (existing 45 tools)

### Page management (27 tools — `tools_pages.py`)

| Tool | When to use |
|------|------------|
| `wikijs_create_page` | Create a new page. Automatically syncs backlinks. Use `parent_id` for hierarchy. |
| `wikijs_update_page` | Update a page's title or content. Automatically re-syncs backlinks after content change. |
| `wikijs_get_page` | Read a single page by ID or slug. **Prefer `wikijs_bulk_get_pages` for multiple pages.** |
| `wikijs_search_pages` | Full-text search. Returns page IDs, titles, paths. |
| `wikijs_list_spaces` | List top-level path groupings ("spaces"). |
| `wikijs_create_space` | Create a root-level page acting as a space container. |
| `wikijs_bulk_get_pages` | **NEW (P1)** Read N pages in parallel. Cap 50. Partial success with error reporting. |
| `wikijs_get_backlinks` | **NEW (P1)** Find all pages that link to a given page. Powered by SQLite BacklinkIndex. |
| `wikijs_rebuild_backlink_index` | **NEW (P1)** Full index rebuild from scratch. Call after bulk imports. |
| `wikijs_get_page_stats` | **NEW (P1)** Metadata without content: wordCount, link counts, freshness, tags. |
| `wikijs_bulk_get_page_stats` | **NEW (P1)** Batch page stats. Two-phase: bulk_get_pages + BacklinkIndex batch query. |
| `wikijs_append_to_page` | **NEW (P2)** Append/prepend content with optimistic locking + retry loop. For log.md. |
| `wikijs_search_by_tag` | **NEW (P2)** Search pages by exact tag or hierarchical subtag (prefix matching via "/" convention). |
| `wikijs_list_all_tags` | **NEW (P2)** List all unique tags with page counts. Optional hierarchical tree view ("/" as separator). |
| `wikijs_set_page_tags` | **NEW (P2)** Replace tags on a page without modifying content (fetch + update). |
| `wikijs_filter_pages` | **NEW (P2)** Multi-facet AND filtering (tag, locale, isPublished). Client-side from pages.list. |
| `wikijs_vector_search` | **NEW (P4)** Semantic search via all-MiniLM-L6-v2 embeddings + cosine similarity. |
| `wikijs_rebuild_vector_index` | **NEW (P4)** Full or incremental vector index rebuild. Powers vector_search and smart_query. |
| `wikijs_smart_query` | **NEW (P2)** Hybrid search (semantic + keyword) via Reciprocal Rank Fusion. Primary Query entry point. |
| `wikijs_get_recent_changes` | **NEW (P3)** Pages modified in last N days. Client-side date filter from pages.list. |
| `wikijs_wiki_stats` | **NEW (P4)** Aggregate wiki dashboard (links, tags, orphans). 60s cache. No content reading. |
| `wikijs_wiki_health` | **NEW (P3)** Unified health check: 7 checks (orphans, stale, density, untagged, connected, clusters, contradictions). BFS for clusters. |
| `wikijs_get_affected_pages` | **NEW (P4)** Impact analysis: 4 signals (backlink, semantic, tags, graph). Weighted ranking + dedup. |
| `wikijs_export_wiki` | Export all wiki pages as .md files to a local directory. Preserves folder hierarchy. |
| `wikijs_export_page` | Export a single wiki page as a .md file. |
| `wikijs_import_page` | Import a .md file as a wiki page. Supports YAML frontmatter. |
| `wikijs_import_directory` | Import all .md files from a directory recursively. Preserves folder hierarchy. |

### Hierarchy (4 tools — `tools_hierarchy.py`)

| Tool | When to use |
|------|------------|
| `wikijs_create_repo_structure` | Bootstrap a repo docs tree with sections. |
| `wikijs_create_nested_page` | Create a page at a specific path like `parent/child`. |
| `wikijs_get_page_children` | Get direct children of a page. |
| `wikijs_create_documentation_hierarchy` | Auto-organize files into component/api/etc buckets. |

### File integration (4 tools — `tools_files.py`)

| Tool | When to use |
|------|------------|
| `wikijs_link_file_to_page` | Map a repo file to a wiki page. |
| `wikijs_sync_file_docs` | Append change notes to a page linked to a file. |
| `wikijs_generate_file_overview` | AST-based markdown for a Python file. |
| `wikijs_bulk_update_project_docs` | Batch sync multiple files. |

### Deletion (4 tools — `tools_deletion.py`)

| Tool | When to use |
|------|------------|
| `wikijs_delete_page` | Delete a single page. |
| `wikijs_batch_delete_pages` | Delete by IDs, paths, or fnmatch pattern. Requires `confirm_deletion=True`. |
| `wikijs_delete_hierarchy` | Delete a subtree. Modes: `children_only`, `include_root`, `root_only`. |
| `wikijs_cleanup_orphaned_mappings` | Remove file mappings where the page no longer exists. |

### System (3 tools — `tools_system.py`)

| Tool | When to use |
|------|------------|
| `wikijs_connection_status` | Verify connectivity to Wiki.js. |
| `wikijs_repository_context` | Get current repo root and file mappings. |
| `wikijs_manage_collections` | Placeholder, no real API call. |

### Graph (3 tools — `tools_graph.py`) **NEW (P2)**

| Tool | When to use |
|------|------------|
| `wikijs_extract_page_links` | Extract internal/external links from a page. Flags broken links. |
| `wikijs_get_page_graph` | BFS-traverse the local link neighborhood (incoming, outgoing, or both). |
| `wikijs_find_shortest_path` | Bidirectional BFS to find the shortest link path between two pages. |

## 4. LLM Wiki roadmap tools (all completed)

| Priority | Tool | Status | Depends on |
|----------|------|--------|-----------|
| P1 | `wikijs_bulk_get_pages` | completed | — |
| P1 | `wikijs_get_backlinks` | completed | bulk_get_pages |
| P1 | `wikijs_get_page_stats` | completed | backlinks |
| P2 | `wikijs_append_to_page` | completed | — |
| P2 | Tag management (4 tools) | completed | — |
| P2 | `wikijs_smart_query` | completed | backlinks, bulk_get_pages, vector_search |
| P2 | Link graph tools (3 tools) | completed | backlinks |
| P3 | `wikijs_wiki_health` | completed | backlinks, page_stats |
| P3 | `wikijs_get_recent_changes` | completed | — |
| P4 | `wikijs_get_affected_pages` | completed | backlinks, tag_mgmt, link_graph, vector_search |
| P4 | Vector search engine | completed | — |
| P4 | `wikijs_wiki_stats` | completed | backlinks, page_stats |

### Dependency graph

```
P1: bulk_get_pages  <-- no dependencies
P1: backlinks       <-- may depend on bulk_get_pages
P1: page_stats      <-- may depend on backlinks (inbound link count)
P2: append_to_page  <-- no dependencies
P2: tag_mgmt        <-- no dependencies
P2: smart_query     <-- backlinks (P1), bulk_get_pages (P1), vector_search (P4)
P2: link_graph      <-- backlinks (P1)
P3: wiki_health     <-- backlinks (P1), page_stats (P1)
P3: recent_changes  <-- no dependencies
P4: affected_pages  <-- backlinks (P1), tag_mgmt (P2), link_graph (P2), vector_search (P4)
P4: vector_search   <-- no dependencies
P4: wiki_stats      <-- backlinks (P1), page_stats (P1)
```

## 5. Conventions

### Metadata-first navigation

At scale (200+ pages), never read page content without first checking metadata:

1. Use `page_stats` / `wiki_health` to triage — which pages are stale? which are orphans? which have the most inbound links?
2. Use `search_pages` / `smart_query` to find relevant pages
3. Only then use `bulk_get_pages` to read the content

**Anti-pattern**: `bulk_get_pages([1,2,3,4,5,...,200])` — reading everything blindly.

**Pattern**: `page_stats` -> identify relevant pages -> `bulk_get_pages([42, 55, 67])` — targeted reading.

### JSON returns

Every MCP tool returns `json.dumps(...)`. Successful responses are a JSON object. Errors contain an `"error"` key:

```json
{"error": "Page not found"}
```

### Locale and paths

- All pages use `locale: "en"`
- Hierarchy is path-based: `parent/child`, not Wiki.js folder IDs
- Slugs are auto-generated from titles via `python-slugify`

### Error handling pattern (for tool authors)

Every tool follows this structure:

```python
@mcp.tool()
async def wikijs_some_tool(param: Type) -> str:
    try:
        await wikijs.authenticate()
        # ... GraphQL logic ...
        logger.info(f"some_tool completed: {summary}")
        return json.dumps(result)
    except Exception as e:
        error_msg = f"Failed to ...: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
```

## 6. LLM Wiki workflows

### Ingest workflow

```
1. SEARCH: wikijs_search_pages("topic") -> find existing pages
2. STATS: wikijs_get_page_stats(ids) -> triage without reading
3. BACKLINKS: wikijs_get_backlinks(id) -> find pages that link to affected concepts
4. BULK READ: wikijs_bulk_get_pages(affected_ids) -> read current state
5. UPDATE: wikijs_update_page(id, content=updated) -> write new content
6. APPEND: wikijs_append_to_page(log_id, entry) -> append to log.md
7. INDEX: wikijs_update_page(index_id, content=updated_index) -> update index.md
```

### Query workflow

```
1. SEARCH: wikijs_search_pages("question keywords") -> find candidates
   or SMART: wikijs_smart_query("question") -> ranked + snippets
2. STATS: wikijs_get_page_stats(candidate_ids) -> triage relevance
3. BULK READ: wikijs_bulk_get_pages(relevant_ids) -> read full content
4. SYNTHESIZE: (in agent memory) -> build answer with citations
5. FILE (optional): wikijs_create_page(title="Query: ...", content=answer) -> file good answers
```

### Lint workflow

```
1. HEALTH: wikijs_wiki_health() -> dashboard of all issues
2. INSPECT: wikijs_bulk_get_pages(orphan_ids) -> read orphan pages
3. DECIDE: unlink, link, or delete orphans; update stale pages
4. FIX: wikijs_update_page / wikijs_delete_page as needed
5. LOG: wikijs_append_to_page(log_id, lint_entry) -> append to log.md
```

## 7. Scale mindset

This wiki is designed for **200+ pages from day one**. Every decision must consider scale.

### Rules

- **Never read pages one-by-one in a loop.** Use `wikijs_bulk_get_pages` for any batch read of 2+ pages.
- **Triage before reading.** Use `page_stats`, `wiki_health`, or `backlinks` to identify which pages matter before reading content.
- **Batch limit is 50 per call.** Above 50, rethink the approach — use `smart_query`, `wiki_health`, or paginate.
- **Append to log, don't rewrite.** The log is append-only. Use `wikijs_append_to_page`, not read-modify-write.
- **Cross-references are the backbone.** When updating a page that mentions a concept, update every page that links to that concept. Use `backlinks` to find them.

### What to avoid

- Calling `wikijs_get_page` 15 times in sequence -> use `wikijs_bulk_get_pages`
- Reading a page to check if it needs updating -> use `wikijs_get_page_stats` first
- Manually scanning for orphan pages -> use `wikijs_wiki_health`
- Rewriting log.md from scratch -> use `wikijs_append_to_page`

## 8. Current implementation status

See `STATUS.md` for the live feature tracker. At time of writing:

- P4 completed: vector search engine (sentence-transformers + brute force cosine similarity, wikijs_vector_search + wikijs_rebuild_vector_index)
- All 12 roadmap features implemented. 45 tools total.
- `VECTOR_ENGINE_IMPACT.md` lists features that benefit from vector search for future enhancement.
- Auth race condition fixed in `WikiJSClient` (asyncio.Lock + early-return)
- All tested inside Docker container against live Wiki.js instance

## 9. Project structure reference

```
wiki-js-mcp/
├── docker-compose.yml
├── docs/                          # Technical docs (for humans and agents)
│   ├── ARCHITECTURE.md
│   ├── MCP_TOOL_CATALOG.md
│   ├── DATABASE_LAYER.md
│   └── ...
├── plans/llm-wiki/               # LLM Wiki plan system
│   ├── README.md                  # Plan overview and process
│   ├── STATUS.md                 # Feature status tracker (source of truth)
│   ├── roadmap.md                # All 12 features, dependencies
│   ├── AGENTS.md                 # This file
│   └── subplans/                 # One file per feature
└── mcp-server/
    ├── src/wiki_mcp_server/
    │   ├── server.py             # FastMCP entry point
    │   ├── client.py             # GraphQL client
    │   ├── config.py             # Settings + logging
    │   ├── db.py                 # SQLite models
    │   ├── utils.py              # AST parsing, file hashing
    │   └── tools_*.py            # Tool implementations
    └── scripts/                  # Setup, start, test, seed
```

## 10. Quick start for an agent

Before any wiki operation:

1. Call `wikijs_connection_status` to verify the stack is reachable
2. Call `wikijs_repository_context` to understand the current repo
3. Read `STATUS.md` to know which tools are available
4. Follow the workflow for your operation (ingest / query / lint) from Section 6 above
5. Update `log.md` after every significant operation with `## [YYYY-MM-DD] type | description`
