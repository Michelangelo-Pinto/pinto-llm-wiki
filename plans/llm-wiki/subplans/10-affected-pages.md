# wikijs_get_affected_pages

---

- **Status**: `completed`
- **Priority**: P4

## Why

When the agent ingests a new source, it must discover which existing wiki pages need updating. Currently this is a manual, multi-step process:

1. Search for pages by related keywords
2. Read those pages and extract their backlinks
3. Follow the link graph outward
4. Check shared tags for related topics

This is the single most expensive part of the ingestion workflow. `wikijs_get_affected_pages` automates this discovery by combining multiple signals (backlinks, semantic similarity, shared tags, graph proximity) into one call.

This is complementary to `wikijs_get_backlinks` (P1). Backlinks tell you "which pages explicitly link to X". Affected pages tells you "which pages are semantically and structurally related to X" — including pages that don't have explicit links but cover overlapping topics.

## What

```python
wikijs_get_affected_pages(page_id: int, max_results: int = 20, include_reasoning: bool = True) -> str
```

Returns:
```json
{
  "source": {"pageId": 7, "title": "Authentication", "path": "auth/overview"},
  "affected_pages": [
    {
      "pageId": 12,
      "title": "OAuth 2.0",
      "path": "auth/oauth",
      "reasons": ["backlink", "shared_tags", "graph_neighbor"],
      "relevance_score": 0.85
    },
    {
      "pageId": 55,
      "title": "Session Management",
      "path": "web/sessions",
      "reasons": ["semantic_similarity", "shared_tags"],
      "relevance_score": 0.72
    },
    {
      "pageId": 89,
      "title": "JWT Best Practices",
      "path": "auth/jwt",
      "reasons": ["backlink", "graph_neighbor", "semantic_similarity"],
      "relevance_score": 0.91
    }
  ],
  "signal_breakdown": {
    "total_backlinks": 5,
    "semantic_matches": 12,
    "shared_tags": 8,
    "graph_neighbors": 6
  },
  "mode": "partial"  // "full" if all signals available, "partial" if some are missing
}
```

### Signal sources

| Signal | What it detects | Dependency |
|--------|----------------|------------|
| `backlink` | Pages that explicitly link to the source page | `wikijs_get_backlinks` (P1) |
| `semantic_similarity` | Pages with similar content (vector embeddings) | Vector search engine (P4-11) |
| `shared_tags` | Pages sharing one or more tags with the source | Tag management (P2) |
| `graph_neighbor` | Pages within 1-2 hops in the link graph (both directions) | Link graph (P2) |

### Ranking formula

Results are ranked by a weighted combination:
- `backlink`: weight 1.0 (explicit link = strongest signal)
- `graph_neighbor` (depth 1): weight 0.8
- `semantic_similarity` (cosine > 0.7): weight 0.6
- `shared_tags` (3+ shared): weight 0.5
- `shared_tags` (1-2 shared): weight 0.3

A page that appears via multiple signals gets the highest score (e.g., shown as backlink + semantic + shared_tags = 0.85).

## Design questions

- **Which signals to include?** The four signals above cover explicit links, content similarity, categorization, and structure. These are complementary and cover different types of relationships.
- **What distinguishes this from `backlinks`?** Backlinks are exact: "page X has a markdown link to page Y". Affected pages is fuzzy: "page X and page Y are about the same topic, even if they don't link to each other". Use affected_pages for ingestion discovery, backlinks for maintenance.
- **Partial results**: when lower-priority dependencies aren't implemented yet, return partial results with `mode: "partial"`. The agent can still use available signals.
- **How many results?** Default 20. At 200+ pages, semantic search might return 50+ similar pages. Cap at `max_results`.
- **Excluding the source page**: the source page shouldn't appear in results, nor should structural pages (index, log).

## Dependencies

- `wikijs_get_backlinks` (P1) — for `backlink` signal
- Tag management (P2) — for `shared_tags` signal
- Link graph (P2) — for `graph_neighbor` signal
- Vector search engine (P4-11) — for `semantic_similarity` signal
- `wikijs_get_page_stats` (P1) — for relevance scoring

Can return partial results if any dependency is unavailable (e.g., before P4-11 is done).

Feeds into: the Ingest operation of the LLM Wiki pattern.

## Scale considerations

- Computing all signals for one page on a 200+ page wiki: backlinks (O(1) with index), tags (O(1) with cache), graph neighbors (O(degree) with index), semantic similarity (O(N) for vector comparison, but reduced by pre-filtering with approximate nearest neighbor index).
- Caching: affected pages for a given page ID can be cached for 5 minutes, invalidated on page content change.
- The `mode` field is critical: at scale, the agent should know if partial results are due to missing infrastructure or genuinely few connections.

## Implementation plan

1. Implement signal collectors for each of the four sources
2. Implement ranking formula with configurable weights
3. Implement partial results mode detection
4. Add result deduplication (same page from multiple signals)
5. Implement caching with invalidation
6. Add tool to `tools_pages.py` or new `tools_analysis.py`
7. Update documentation
8. Verify by creating a wiki with intentional relationships and checking affected pages

## Acceptance criteria

- Returns all pages that link to the source (backlink signal)
- Returns semantically similar pages when vector engine is available
- Returns pages sharing tags with the source
- Returns pages within 1-2 graph hops of the source
- Results are deduplicated (same page from multiple signals appears once with all reasons)
- Rankings are consistent: explicit backlinks score higher than distant semantic matches
- `mode: "partial"` when some signals unavailable; `mode: "full"` when all are
- At 200+ pages, query completes in < 5 seconds

---

## Implementation notes (2026-05-23)

- All 4 signals available (mode: "full") — backlinks, semantic, tags, graph neighbors
- Semantic signal via `_cosine_similarity` on PageVector (threshold > 0.7)
- Graph neighbors via BacklinkIndex (depth 1, both directions)
- Weighted ranking: backlink 1.0, graph 0.8, semantic 0.6, tags 0.3-0.5
- Deduplication by page ID with accumulated reasons array
