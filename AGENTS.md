# AGENTS.md — wiki-js-mcp v3

Wiki-js-mcp v3 trasforma [Wiki.js](https://js.wiki/) in una knowledge base potenziata da AI, accessibile da LLM agent via **4 server MCP indipendenti** che espongono complessivamente **65 tool** su trasporto **SSE**.

| Server | Container | Porta | Prefisso | Tool |
|--------|-----------|-------|----------|------|
| Wiki.js MCP | `wikijs_mcp` | `8000` | `wikijs_*` | 43 |
| Qdrant MCP | `wikijs_qdrant_mcp` | `8001` | `qdrant_*` | 8 |
| Ingestion Pipeline | `wikijs_ingestion` | `8002` | `ingest_*` | 7 |
| Tesseract MCP | `wikijs_tesseract_mcp` | `8003` | `ocr_*` | 7 |

Tutti i server usano SSE su path `/sse`. Lo stack Docker avvia **8 container** (7 a regime, `wikijs_setup` esce dopo l'inizializzazione).

---

## Mappa del repository

```
mcp-servers/          # Codice dei 4 server MCP
  wiki-js-mcp/        # 43 tool: CRUD pagine, ricerca, grafo, health
  qdrant-mcp/         # 8 tool: collezioni, upsert/ricerca vettoriale
  ingestion-pipeline/ # 7 tool: detect → extract → chunk → embed → upsert
  tesseract-mcp/      # 7 tool: OCR, HOCR, confidence, preprocessing
doc_v3/               # Documentazione di riferimento (fonte autorevole)
tests/                # Test: unit, integration, smoke, e2e, performance
plans/                # Storico pianificazione (plans/llm-wiki/AGENTS.md = v2, obsoleto)
```

---

## Scegli il tuo ruolo

- **Operatore** della knowledge base → leggi `.cursor/rules/10-wiki-operator.mdc` + `.cursor/rules/25-agent-logging.mdc` + `.cursor/rules/30-operational-memory.mdc` + `.cursor/rules/35-web-ingestion.mdc`
- **Sviluppatore** del codice MCP → leggi `.cursor/rules/20-wiki-developer.mdc`
- La regola `.cursor/rules/00-project-overview.mdc` e' sempre attiva con i fatti essenziali.

---

## Golden rules

1. **Prefissi → porte**: `wikijs_*` = porta 8000, `qdrant_*` = 8001, `ingest_*` = 8002, `ocr_*` = 8003.
2. **Metadata-first**: a 200+ pagine, mai leggere contenuto senza prima triage (`wikijs_get_page_stats` / `wikijs_wiki_health`). Mai loop di `wikijs_get_page`: usare `wikijs_bulk_get_pages` (cap **50** per chiamata).
3. **I vettori delle pagine wiki (`wiki_pages`) NON sono auto-indicizzati** su create/update: vanno indicizzati esplicitamente (`qdrant_upsert_chunks`). I backlink sono auto-sincronizzati via hook.
4. **File esterni prima in Qdrant**: ingerire con `ingest_document` prima che `wikijs_smart_query` li trovi semanticamente.
5. **`log.md` e' append-only** (`wikijs_append_to_page`), formato riga `## [YYYY-MM-DD] tipo | descrizione`. `index.md` aggiornato a ogni ingest.
6. **`/data/shared`**: montato **ro** su qdrant-mcp, ingestion-pipeline, tesseract-mcp (NON su wiki-js-mcp). Per spostare file tra container serve `docker compose cp`.
7. **Contratto JSON**: ogni tool ritorna `json.dumps(...)`; errori = `{"error": "..."}`.
8. **Confini agente**: l'agente puo' eseguire `docker compose build/up/down/restart/logs/ps` **solo su richiesta esplicita dell'utente** (vedi [Stack Lifecycle Guide](doc_v3/guides/stack-lifecycle.md)). NON puo' editare `.env`/`mcp.json`, eseguire `docker compose cp`, `docker compose down -v` senza conferma, installare lingue Tesseract (default `eng+ita`), posizionare raw source.
9. **Cancellazioni batch**: `confirm_deletion=True`. Pagine identificate da **ID interi**, gerarchia path-based, `locale: "en"`, `editor: "markdown"`.
10. **Nomi tool rimossi in v3**: `wikijs_vector_search`, `wikijs_rebuild_vector_index` — non usarli.
11. **Attribuzione fonte obbligatoria**: ogni pagina wiki creata da contenuto esterno deve includere nel frontmatter `source_type`, `source_url` o `source_file`, `source_name`, `fetched_at`. Vedi `.cursor/rules/35-web-ingestion.mdc`.

---

## Bootstrap di sessione

All'inizio di ogni sessione operativa:

1. `wikijs_connection_status` — verifica connettivita' Wiki.js e Qdrant
2. `wikijs_repository_context` — contesto del repository Git
3. Leggi `doc_v3/reference/quick-reference.md` e `doc_v3/guides/llm-wiki-workflows.md`

---

## Documenti di riferimento

| Documento | Contenuto |
|-----------|-----------|
| [Quick Reference](doc_v3/reference/quick-reference.md) | Tutti i 65 tool in formato compatto |
| [Stack Lifecycle Guide](doc_v3/guides/stack-lifecycle.md) | Build, start, stop, rebuild dello stack Docker |
| [LLM Wiki Workflows](doc_v3/guides/llm-wiki-workflows.md) | Workflow passo-passo: Ingest, Query, Lint, Document Processing |
| [Tool Catalog](doc_v3/reference/tool-catalog.md) | Firme complete di tutti i tool |
| [File Paths and Volumes](doc_v3/guides/file-paths-and-volumes.md) | Dove mettere i file per ingestion/export |
| [Error Catalog](doc_v3/reference/error-catalog.md) | Catalogo errori comuni e soluzioni |
| [System Overview](doc_v3/architecture/system-overview.md) | Architettura 8-container e data flow |
