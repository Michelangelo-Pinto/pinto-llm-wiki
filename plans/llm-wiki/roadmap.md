# Roadmap — LLM Wiki Features (Scale-First)

All features needed to extend the MCP server for full LLM Wiki support at scale (200+ pages from day one). Ordered by priority.

---

## Overall Goal: implementare il pattern "LLM Wiki" di Andrej Karpathy

> Full original description: [LLM Wiki](https://gist.github.com/karpathy) — "A pattern for building personal knowledge bases using LLMs."
> Extended context: `README.md` in this folder.

### Il pattern

L'idea centrale e' che l'LLM **costruisce e mantiene incrementalmente un wiki persistente** — una collezione strutturata e interconnessa di file markdown che sta tra l'utente e le fonti grezze. Quando arriva una nuova fonte, l'LLM non si limita a indicizzarla. La legge, estrae le informazioni chiave e le integra nel wiki esistente: aggiorna pagine di entita', rivede riassunti tematici, nota dove nuovi dati contraddicono affermazioni precedenti.

**Differenza chiave: il wiki e' un artefatto persistente e cumulativo**, non ri-derivato a ogni query. I cross-reference sono gia' li'. Le contraddizioni sono gia' segnalate. La sintesi riflette gia' tutto cio' che e' stato letto.

### Tre livelli architetturali

1. **Raw sources** — fonti immutabili (articoli, paper, dati). L'LLM legge ma non modifica.
2. **The wiki** — directory di markdown generati dall'LLM (riassunti, pagine entita', concetti, comparazioni, sintesi). L'LLM lo possiede interamente.
3. **The schema** — documento di convenzioni (CLAUDE.md / AGENTS.md) che dice all'LLM come strutturare il wiki e quali workflow seguire.

### Tre operazioni

- **Ingest**: processare una fonte → summary page → aggiornare index → aggiornare entity/concept pages → append a log. Una singola fonte puo' toccare 10-15 pagine.
- **Query**: cercare pagine rilevanti → leggerle → sintetizzare risposta con citazioni. Le buone risposte vengono archiviate come nuove pagine.
- **Lint**: health-check periodico — contraddizioni tra pagine, claim obsoleti, pagine orfane, concetti menzionati senza pagina propria, cross-reference mancanti.

### File speciali

- **index.md**: catalogo orientato al contenuto, organizzato per categoria. Aggiornato a ogni ingest.
- **log.md**: registro cronologico append-only di ingest, query, lint. Prefisso consistente per parsing: `## [2026-04-02] ingest | Titolo`.

### Perche' funziona

La parte noiosa del mantenere una knowledge base non e' leggere o pensare — e' la contabilita': aggiornare cross-reference, tenere aggiornati i riassunti, notare contraddizioni, mantenere coerenza tra decine di pagine. Gli LLM non si annoiano, non dimenticano di aggiornare un cross-reference, e possono toccare 15 file in un passaggio. Il costo di manutenzione e' vicino allo zero.

### Cosa deve fare il nostro MCP server

Il MCP server attuale (21 tool) fornisce le operazioni CRUD di base su Wiki.js, ma **non ha gli strumenti per permettere a un LLM agent di eseguire efficacemente il pattern LLM Wiki a scala**. In particolare mancano:

- **Discovery**: backlinks, link graph, ricerca semantica, smart query
- **Efficienza**: lettura batch, append, stats (per triage senza leggere tutto)
- **Manutenzione**: dashboard di health unificato, rilevazione pagine impattate, modifiche recenti

Le 12 feature elencate sotto colmano questi gap, progettate direttamente per wiki di 200+ pagine.

---

## Scale-first design rationale

L'approccio incrementale tradizionale (P1 basic → P4 advanced) non funziona per wiki sopra le 100 pagine: senza metadata-first navigation, semantic search, e graph awareness, l'agente e' cieco. Questo roadmap e' progettato per scala dal primo giorno:

1. **Metadata before content**: `page_stats` e' P1, non P2. A scala devi fare triage dai metadati prima di leggere contenuti.
2. **Unified dashboards**: tool di lint separati (orfani, stale, cambi recenti) sono stati unificati in `wiki_health` — un'unica chiamata che restituisce una dashboard completa.
3. **Search is core**: `semantic_search` non e' un lusso P4 — e' l'unico modo per fare query efficaci su 200+ pagine. E' P2 e alimenta `smart_query`.
4. **Graph awareness**: i link graph tools sono P2, non P3. Il grafo e' la struttura primaria di navigazione.
5. **Proactive maintenance**: `get_affected_pages` dice all'agente quali pagine aggiornare quando arriva una nuova fonte, invece di cercare backlinks manualmente.

Tool count: 10 → 12 (orphan + stale fusi in wiki_health, + smart_query, + affected_pages, + wiki_stats).

---

## P1 — Blockers for basic LLM Wiki workflow at scale

Without these, the agent cannot efficiently operate on a wiki of any size beyond a handful of pages.

### 1. `wikijs_bulk_get_pages` — [subplan](subplans/01-bulk-page-read.md)

**Goal**: Read multiple pages (full content) in a single MCP tool call.

**Why**: In the LLM Wiki pattern, the agent must read the index, then read multiple pages to answer a query or perform ingestion. Without batch read, 10 pages = 10 round trips. At 200+ pages, every operation would be painfully slow.

**Signature**:
```
wikijs_bulk_get_pages(page_ids: List[int]) -> str
```

**Dependencies**: None.

### 2. `wikijs_get_backlinks` — [subplan](subplans/02-backlinks.md)

**Goal**: Given a page ID, return all pages that link to it.

**Why**: The LLM Wiki pattern is built on cross-references. When ingesting a new source, the agent must update every page that references the affected concepts. Without backlinks, the agent has no way to discover which pages need updating. This is the foundation for `affected_pages`, `link_graph`, and `wiki_health`.

**Signature**:
```
wikijs_get_backlinks(page_id: int) -> str
```

**Dependencies**: May use `wikijs_bulk_get_pages` for scanning content across all pages during index building.

### 3. `wikijs_get_page_stats` — [subplan](subplans/03-page-stats.md)

**Goal**: Return metadata about a page without returning its full content. **Promoted from P2 — essential at scale.**

**Why**: When the agent operates on 200+ pages, it must make decisions without reading full content. Stats (word count, link counts, freshness, tags) enable triage. This is the metadata-first entry point for every operation.

**Signature**:
```
wikijs_get_page_stats(page_id: int) -> str
```
Returns: `{word_count, outbound_links, inbound_links, last_modified, created_at, tags, is_published, content_length, description}`

**Dependencies**: Inbound link count depends on `wikijs_get_backlinks` (P1). Can return null until backlinks are implemented.

---

## P2 — Core LLM Wiki workflow

These enable the ingestion, query, and navigation workflows at scale.

### 4. `wikijs_append_to_page` — [subplan](subplans/04-page-append.md)

**Goal**: Append content to a page without fetching and rewriting the entire content.

**Why**: The `log.md` file in the LLM Wiki pattern is append-only. Currently `wikijs_update_page` requires fetching the full content, appending in memory, then writing back — wasteful and prone to race conditions for frequently-updated pages.

**Signature**:
```
wikijs_append_to_page(page_id: int, content: str, position: str = "end") -> str
```

**Dependencies**: None.

### 5. Tag management (hierarchical) — [subplan](subplans/05-tag-management.md)

**Goal**: Four tools for working with Wiki.js tags with hierarchical and faceted filtering support.

**Why**: Tags are the simplest categorization mechanism. At scale, flat tags are insufficient — the agent needs hierarchical tags (e.g., `tech/python/async`) and facet filtering (filter by tag + category + status). This was enhanced from the original flat 3-tool design.

**Signatures**:
```
wikijs_search_by_tag(tag: str, include_subtags: bool = False) -> str
wikijs_list_all_tags(hierarchical: bool = False) -> str
wikijs_set_page_tags(page_id: int, tags: List[str]) -> str
wikijs_filter_pages(filters: Dict[str, str]) -> str  (NEW: facet filter)
```

**Dependencies**: None.

### 6. `wikijs_smart_query` — [subplan](subplans/06-smart-query.md) **NEW**

**Goal**: Hybrid query that combines semantic search, keyword search, and graph proximity. The primary entry point for the "Query" operation.

**Why**: At scale, the agent needs a single tool that finds the most relevant pages by meaning (not just keywords), ranks them, returns snippets and summaries, and includes link context. This replaces the pattern of "search → read 10 pages manually → synthesize".

**Signature**:
```
wikijs_smart_query(query: str, limit: int = 10, include_summaries: bool = True, include_link_context: bool = True) -> str
```
Returns: ranked results with `{pageId, title, path, snippet, summary, relevance_score, linked_from, linked_to}`

**Dependencies**: `wikijs_get_backlinks` (P1) for link context. `wikijs_bulk_get_pages` (P1) for summaries. Vector search engine (P4-11) for semantic component; falls back to keyword-only until vector engine is ready.

### 7. Link graph tools — [subplan](subplans/07-link-graph.md) **Promoted from P3, enhanced**

**Goal**: Extract links from a page, explore the local link graph, and find shortest paths between pages.

**Why**: The LLM Wiki is fundamentally a graph. At scale, the agent needs graph awareness for navigation, ingestion (finding affected pages), and lint (detecting disconnected clusters). Enhanced with shortest-path finding for scale.

**Signatures**:
```
wikijs_extract_page_links(page_id: int, link_type: str = "all") -> str
wikijs_get_page_graph(page_id: int, depth: int = 1, direction: str = "both") -> str
wikijs_find_shortest_path(from_page_id: int, to_page_id: int) -> str  (NEW)
```

**Dependencies**: `wikijs_get_backlinks` (P1) for incoming direction and path finding.

---

## P3 — Wiki health and maintenance

These support the "lint" operation and ongoing wiki health with a unified dashboard approach.

### 8. `wikijs_wiki_health` — [subplan](subplans/08-wiki-health.md) **NEW — merges orphan detection + stale detection**

**Goal**: Comprehensive health dashboard in a single tool call. Checks: orphan pages, stale pages, link density distribution, pages missing tags, most-connected pages, pages with contradictions, disconnected clusters.

**Why**: The original roadmap had three separate lint tools (orphan, stale, recent_changes). At scale, running them separately is wasteful. A single dashboard call gives the agent everything it needs to triage wiki health. This merges `find_orphan_pages` and `find_stale_pages`.

**Signature**:
```
wikijs_wiki_health(include_checks: List[str] = None) -> str
```
Returns:
```json
{
  "orphans": [...],
  "stale": [...],
  "link_density": {"average": 4.2, "distribution": {...}},
  "untagged_pages": [...],
  "most_connected": [...],
  "contradictions": [...],
  "disconnected_clusters": [...],
  "summary": {"total_checks": 7, "issues_found": 23, "critical": 2}
}
```

**Dependencies**: `wikijs_get_backlinks` (P1) for orphan/link density checks.

### 9. `wikijs_get_recent_changes` — [subplan](subplans/09-recent-changes.md)

**Goal**: List pages modified within a given time window.

**Why**: For incremental wiki maintenance, the agent needs to know what changed recently. Complementary to `wiki_health`.

**Signature**:
```
wikijs_get_recent_changes(limit: int = 20, since_days: int = 7) -> str
```

**Dependencies**: None (uses Wiki.js GraphQL query with date filtering).

---

## P4 — Scale optimizations

These become essential when the wiki grows beyond 200 pages.

### 10. `wikijs_get_affected_pages` — [subplan](subplans/10-affected-pages.md) **NEW**

**Goal**: Given a page ID, returns which other pages might be impacted by changes (backlinks + semantic similarity + shared tags + graph proximity). Enables proactive ingestion.

**Why**: When ingesting a new source, the agent currently must manually search backlinks, scan tags, and explore the graph to find which pages to update. This tool automates that discovery. It's the proactive counterpart to the reactive `backlinks`.

**Signature**:
```
wikijs_get_affected_pages(page_id: int, max_results: int = 20) -> str
```
Returns: `{direct_backlinks: [...], semantic_similar: [...], shared_tags: [...], graph_neighbors: [...], ranked: [...]}`

**Dependencies**: `wikijs_get_backlinks` (P1), vector search engine (P4-11), tag management (P2), link graph (P2). Can return partial results with available dependencies.

### 11. Vector search engine — [subplan](subplans/11-vector-search.md) **Redesigned from P4 semantic_search**

**Goal**: Embedded vector search engine running within the MCP server (sqlite-vec or sentence-transformers). Powers `smart_query` (P2) and `get_affected_pages` (P4).

**Why**: The original design considered external tools like qmd. For a self-contained MCP server, an embedded engine is simpler to deploy and maintain. It serves as infrastructure for higher-level tools.

**Signatures**:
```
wikijs_vector_search(query: str, limit: int = 10) -> str
wikijs_rebuild_vector_index() -> str
```

**Dependencies**: New Python dependency (sentence-transformers or similar). No other tool dependencies.

### 12. `wikijs_wiki_stats` — [subplan](subplans/12-wiki-stats.md) **NEW**

**Goal**: Aggregate statistics dashboard for the entire wiki. One-call overview of wiki state.

**Why**: At scale, the agent needs a quick snapshot: total pages, link density, orphan rate, staleness distribution, growth rate, most-linked pages. This is the "at a glance" tool that informs high-level decisions.

**Signature**:
```
wikijs_wiki_stats() -> str
```
Returns:
```json
{
  "total_pages": 234,
  "total_links": 1204,
  "avg_links_per_page": 5.1,
  "orphan_count": 12,
  "orphan_rate": 0.051,
  "stale_count": 45,
  "avg_staleness_days": 23,
  "total_tags": 87,
  "growth_last_30d": 18,
  "most_linked": [{"pageId": 7, "title": "Auth", "inbound_links": 34}],
  "newest_page": {"pageId": 234, "title": "...", "createdAt": "..."},
  "oldest_page": {"pageId": 1, "title": "...", "createdAt": "..."}
}
```

**Dependencies**: `wikijs_get_backlinks` (P1) for link counts. `wikijs_page_stats` (P1) for per-page data. Can aggregate from partial data.

---

## Dependency graph

```
P1: bulk_get_pages  ←  no dependencies
P1: backlinks      ←  may depend on bulk_get_pages for scanning all pages
P1: page_stats     ←  may depend on backlinks (for inbound link count)
P2: append_to_page ←  no dependencies
P2: tag_mgmt       ←  no dependencies
P2: smart_query    ←  depends on backlinks (P1), bulk_get_pages (P1), vector_search (P4-11)
P2: link_graph     ←  depends on backlinks (P1)
P3: wiki_health    ←  depends on backlinks (P1), page_stats (P1)
P3: recent_changes ←  no hard dependencies
P4: affected_pages ←  depends on backlinks (P1), tag_mgmt (P2), link_graph (P2), vector_search (P4-11)
P4: vector_search  ←  no hard dependencies (new library)
P4: wiki_stats     ←  depends on backlinks (P1), page_stats (P1)
```

## Priority rationale

P1 features are blockers: without batch read, backlinks, and stats, the agent cannot operate at all on more than a trivial number of pages. P2 features enable the core LLM Wiki workflow (ingest, query, navigate). P3 is the unified health layer. P4 features are optimizations and proactive tooling that become critical above 200 pages.
