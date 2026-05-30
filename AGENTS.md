# AGENTS.md — wiki-js-mcp v4

Wiki-js-mcp v4 e' una knowledge base file-system potenziata da AI, accessibile da LLM agent via **3 server MCP indipendenti** che espongono complessivamente **22 tool** su trasporto **SSE**.

| Server | Container | Porta | Prefisso | Tool |
|--------|-----------|-------|----------|------|
| Qdrant MCP | `wikijs_qdrant_mcp` | 8001 | `qdrant_*` | 8 |
| Ingestion Pipeline | `wikijs_ingestion` | 8002 | `ingest_*` | 7 |
| Tesseract MCP | `wikijs_tesseract_mcp` | 8003 | `ocr_*` | 7 |

Tutti i server usano SSE su path `/sse`. Lo stack Docker avvia **4 container** (qdrant-db + 3 MCP server).

---

## Mappa del repository

```
mcp-servers/                 # Codice dei 3 server MCP
  qdrant-mcp/                # 8 tool: collezioni, upsert/ricerca vettoriale
  ingestion-pipeline/        # 7 tool: detect → extract → chunk → embed → upsert
  tesseract-mcp/             # 7 tool: OCR, HOCR, confidence, preprocessing
doc_v4/                      # Documentazione di riferimento (architettura, guide, reference)
knowledge/                   # Knowledge base file-system (MD organizzato per categorie)
tests/                       # Test: unit, integration, smoke, e2e, performance
plans/                       # Storico pianificazione (plans/v4-migration/ = archivio v3)
```

---

## Scegli il tuo ruolo

- **Operatore** della knowledge base → leggi `.cursor/rules/10-wiki-operator.mdc` + `.cursor/rules/25-agent-logging.mdc` + `.cursor/rules/30-operational-memory.mdc` + `.cursor/rules/35-web-ingestion.mdc`
- **Sviluppatore** del codice MCP → leggi `.cursor/rules/20-wiki-developer.mdc`
- La regola `.cursor/rules/00-project-overview.mdc` e' sempre attiva con i fatti essenziali.

---

## Golden rules

1. **Prefissi → porte**: `qdrant_*` = porta 8001, `ingest_*` = 8002, `ocr_*` = 8003.
2. **Knowledge base = filesystem**: tutto il contenuto vive in `knowledge/` come file markdown organizzati per categorie/sottocategorie. Ogni directory ha un `index.md` per routing. I contenuti NON sono committati in git (solo la struttura `index.md`).
3. **Metadata-first**: a 200+ file, mai leggere contenuto senza prima triage via `index.md` o `qdrant_search`. Usare `Grep` + `Glob` per navigazione, `qdrant_search` per ricerca semantica.
4. **File esterni prima in Qdrant**: ingerire con `ingest_document` prima che la ricerca semantica (`qdrant_search`) li trovi.
5. **`log.md` e `index.md` in knowledge/**: `log.md` append-only nel path designato. `index.md` di ogni categoria aggiornato a ogni ingest.
6. **`/data/shared`**: montato **ro** su qdrant-mcp, ingestion-pipeline, tesseract-mcp. Per spostare file tra container serve `docker compose cp`.
7. **Contratto JSON**: ogni tool MCP ritorna `json.dumps(...)`; errori = `{"error": "..."}`.
8. **Confini agente**: l'agente puo' eseguire `docker compose build/up/down/restart/logs/ps` **solo su richiesta esplicita dell'utente**. NON puo' editare `.env`/`mcp.json`, eseguire `docker compose cp`, `docker compose down -v` senza conferma.
9. **Qdrant**: collezione `documents`, vector_size=384, distanza Cosine, modello `all-MiniLM-L6-v2`.
10. **Attribuzione fonte obbligatoria**: ogni file MD creato da contenuto esterno deve includere nel frontmatter `source_type`, `source_url` o `source_file`, `source_name`, `fetched_at`. Vedi `.cursor/rules/35-web-ingestion.mdc`.
11. **Strumenti grafici**: i file MD possono usare Mermaid per diagrammi e qualsiasi altra estensione markdown supportata da renderer standard.

---

## Bootstrap di sessione

All'inizio di ogni sessione operativa:

1. Verifica connettivita' Qdrant: `qdrant_list_collections`
2. Leggi `knowledge/index.md` per la mappa attuale delle categorie
3. Leggi `doc_v4/reference/quick-reference.md` e `doc_v4/guides/llm-wiki-workflows.md`

---

## Documenti di riferimento

| Documento | Contenuto |
|-----------|-----------|
| [Quick Reference](doc_v4/reference/quick-reference.md) | Tutti i 22 tool in formato compatto |
| [Stack Lifecycle Guide](doc_v4/guides/stack-lifecycle.md) | Build, start, stop, rebuild dello stack Docker |
| [LLM Wiki Workflows](doc_v4/guides/llm-wiki-workflows.md) | Workflow passo-passo: Ingest, Query, Lint, Document Processing |
| [Tool Catalog](doc_v4/reference/tool-catalog.md) | Firme complete di tutti i tool |
| [File Paths and Volumes](doc_v4/guides/file-paths-and-volumes.md) | Dove mettere i file per ingestion/export |
| [Error Catalog](doc_v4/reference/error-catalog.md) | Catalogo errori comuni e soluzioni |
| [System Overview](doc_v4/architecture/system-overview.md) | Architettura 4-container e data flow |
