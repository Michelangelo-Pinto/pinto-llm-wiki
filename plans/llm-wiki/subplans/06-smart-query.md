# wikijs_smart_query

---

- **Status**: `completed`
- **Priority**: P2

## Why

At scale (200+ pages), the "search → read N pages → synthesize" pattern is too slow and too expensive in context tokens. The agent needs a single tool that:

1. Finds the most relevant pages by meaning (semantic), not just keywords
2. Ranks them intelligently (combining semantic relevance + keyword match + graph centrality)
3. Returns snippets and summaries so the agent can decide which pages to read in full
4. Includes link context to understand how results relate to each other

This is the primary entry point for the LLM Wiki **Query** operation. Without it, every query requires 5-10 separate MCP tool calls (search → pick top N → bulk_read → manually synthesize).

The `smart_query` tool wraps lower-level tools (semantic search, keyword search, backlinks, bulk_read) into a single intelligent query.

## What

```python
wikijs_smart_query(query: str, limit: int = 10, include_summaries: bool = True, include_link_context: bool = True) -> str
```

Returns:
```json
{
  "query": "authentication methods",
  "total_hits": 34,
  "results": [
    {
      "pageId": 7,
      "title": "Authentication",
      "path": "auth/overview",
      "snippet": "...Authentication is the process of verifying...",
      "summary": "Overview of authentication methods including OAuth, JWT, and session-based auth. Covers trade-offs between stateless and stateful approaches.",
      "relevance_score": 0.92,
      "linked_from": [{"pageId": 1, "title": "Index"}],
      "linked_to": [{"pageId": 12, "title": "OAuth 2.0"}, {"pageId": 15, "title": "Bearer Tokens"}],
      "tags": ["security", "api", "auth"],
      "lastModified": "2026-05-15"
    }
  ],
  "fallback_mode": "full"  // "semantic", "keyword", or "full"
}
```

### Key parameters

- `query`: natural language query (full sentence or keywords)
- `limit`: max results to return
- `include_summaries`: if true, includes a 2-3 sentence summary of each page (uses cached summaries or generates from content)
- `include_link_context`: if true, includes `linked_from` and `linked_to` arrays

### Fallback behavior

The tool combines three search modes with graceful degradation:

1. **Full mode** (default): semantic search (if vector engine available) + keyword search, merged and ranked
2. **Semantic-only**: if keyword index is rebuilding, fall back to semantic
3. **Keyword-only**: if vector engine is unavailable (before P4-11 is implemented), fall back to `wikijs_search_pages`

The `fallback_mode` field tells the agent which mode was used, so it can adjust expectations.

## Design questions

- **How to merge and rank results from multiple sources?**
  - Option A: Reciprocal Rank Fusion (RRF) — simple, no tuning needed
  - Option B: Weighted linear combination — more control, requires tuning
  - Recommendation: Start with RRF. It's parameter-free and proven for hybrid search.
- **How to generate summaries?**
  - Option A: LLM-generated on the fly (expensive in tokens, not available in MCP tool)
  - Option B: Cached summaries stored in SQLite, generated when the page is created/updated (by the update hook, asking the LLM agent)
  - Option C: Extract first N characters of content as a naive summary
  - Recommendation: Start with Option C (first 500 chars), then add a `wikijs_set_page_summary` tool for LLM-generated summaries.
- **Link context**: uses `wikijs_get_backlinks` (P1) and outbound links from the link graph index. If those aren't available, return empty arrays.
- **Pagination**: add `offset` parameter for paginating through many results? Not initially — `limit` with a cap of 50 is sufficient.
- **Integration with `wikijs_bulk_get_pages` (P1)**: for summaries, smart_query may need to read full content. It should use bulk_get_pages internally to minimize round trips.

## Dependencies

- `wikijs_search_pages` (existing) — for keyword search fallback
- `wikijs_get_backlinks` (P1) — for `linked_from` context
- `wikijs_bulk_get_pages` (P1) — for generating summaries and reading results
- Vector search engine (P4-11) — for semantic component. Falls back to keyword-only until implemented.
- `wikijs_get_page_stats` (P1) — for relevance signals (link count, freshness)

Feeds into: the primary Query operation of the LLM Wiki pattern.

## Scale considerations

- Summary caching: at 200+ pages, generating summaries on the fly is too expensive. Cache summaries in SQLite `PageSummary` table. Regenerate when page content changes.
- Result ranking at scale: RRF works well for up to ~1000 results. For larger scale, add pre-filtering by tags or path prefix.
- Fallback awareness: the agent should be aware that keyword-only mode is less precise than hybrid mode. The `fallback_mode` field enables this.
- Caching search results: for identical queries within a time window (e.g., 60 seconds), cache and reuse. Common when the agent re-queries to refine.

## Implementation plan

1. Implement Reciprocal Rank Fusion for result merging
2. Wire up keyword search via existing `wikijs_search_pages`
3. Implement semantic search integration (stub until P4-11)
4. Implement summary generation (first-N-chars fallback)
5. Add link context via backlinks (when available)
6. Design and implement SQLite `PageSummary` cache table
7. Add relevance scoring (word count, link count, freshness signals)
8. Implement fallback modes with clear reporting
9. Add tool to `tools_pages.py`
10. Update documentation
11. Verify query quality against manual search → read → synthesize workflow

## Acceptance criteria

- Returns ranked results for natural language queries
- `fallback_mode` correctly reports which search mode was used
- Results include snippets and link context when requested
- Falls back gracefully to keyword-only when vector engine unavailable
- Query completes in < 3 seconds on 200+ pages
- Results are measurably better than keyword-only `wikijs_search_pages` for semantic queries (when vector engine is active)
- `include_summaries=False` returns results faster (no content reading)

---

## Implementation notes (2026-05-23)

### Design decisions

| Aspect | Planned | Implemented | Why |
|--------|---------|-------------|-----|
| Ranking | RRF (Reciprocal Rank Fusion) | RRF with k=60 | Standard parameter-free hybrid search merge |
| Summaries | LLM-generated cached in SQLite | First 500 chars of content | No LLM available in MCP tool. Sufficient for triage. |
| Link context | Graph-based via backlinks | BacklinkIndex for inbound counts, _extract_links for outbound | Reuses existing infrastructure |
| Fallback modes | 3 modes | 3 modes (full/semantic/keyword) | Graceful degradation if vector engine or Wiki.js search fails |
| Vector engine | P4-11 as dependency | Integrated via internal function calls | Parallel semantic + keyword via asyncio.gather |

### Key deviations from original plan

- **No summary caching**: The original plan suggested SQLite `PageSummary` table for LLM-generated summaries. Since the MCP tool cannot call an LLM, summaries are content snippets (first 500 chars). A future `wikijs_set_page_summary` tool could allow an LLM agent to set summaries.
- **Link context scope**: Returns inbound count + extracted outbound paths, not full title resolution for outbound links (would add significant latency).
- **Result enrichment**: Uses `_LIST_ALL_PAGES_WITH_TAGS_QUERY` for metadata (tags, timestamps) in addition to the planned schema.

### Test results

6/6 tests passed inside Docker container (vector engine already indexed):
- Full mode with RRF ranking
- Snippets present when include_summaries=True
- Link context (inbound_link_count) when include_link_context=True
- limit parameter respected
- Empty query returns error
- Fallback mode correctly reported
