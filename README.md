# wiki-js-mcp v3

[![Test Suite](https://github.com/mikep/wiki-js-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/mikep/wiki-js-mcp/actions/workflows/test.yml)

**wiki-js-mcp** trasforma [Wiki.js](https://js.wiki/) in una knowledge base potenziata da AI, accessibile direttamente da LLM agent (Cursor IDE, Claude Desktop, e qualsiasi client MCP).

Fornisce **~65 strumenti MCP** suddivisi su **4 server indipendenti** in **8 container Docker**: gestione pagine wiki, ricerca semantica vettoriale (Qdrant), OCR documentale (Tesseract), e una pipeline di ingestion che processa PDF, DOCX, immagini e Markdown.

> **Nuovo qui?** Parti dalla [Guida Utente](userguide/index.md) — un percorso di onboarding pensato per umani, in italiano.

---

## Perche' esiste

Una knowledge base invecchia. La parte noiosa non e' leggere o pensare, ma il **bookkeeping**: aggiornare i cross-reference, tenere i riassunti allineati, accorgersi delle contraddizioni, mantenere coerenza tra decine di pagine. I documenti grezzi (PDF, scansioni, DOCX) non sono cercabili per significato.

**wiki-js-mcp** applica il **pattern LLM Wiki**: una knowledge base mantenuta da un agente LLM. L'agente non si annoia, non dimentica un cross-reference e puo' toccare 15 pagine in un colpo solo. Tre livelli: **sorgenti grezze** (immutabili, solo umano), **la wiki** (pagine markdown interconnesse, gestite dall'agente), e **lo schema** (convenzioni e workflow in `AGENTS.md` e `.cursor/rules/`, definiti da umano + agente).

## Quali problemi risolve

- **"Ho centinaia di PDF e scansioni e non riesco a cercarli per significato"** — ingestion con OCR automatico (Tesseract) e ricerca semantica vettoriale (Qdrant)
- **"La documentazione e' disordinata e va aggiornata a mano"** — l'agente mantiene index, cross-reference, log e tiene tutto coerente
- **"Voglio interrogare la mia conoscenza in linguaggio naturale dall'IDE"** — MCP + `wikijs_smart_query` direttamente da Cursor
- **"Le pagine diventano orfane o obsolete"** — `wikijs_wiki_health` rileva pagine abbandonate e problemi strutturali

## Per chi e'

- **Sviluppatori e ricercatori** che vogliono una knowledge base interrogabile in linguaggio naturale senza uscire dall'IDE
- **Team tecnici** con molti documenti da rendere cercabili e una wiki da mantenere viva nel tempo
- **Chiunque voglia delegare il bookkeeping della conoscenza a un agente LLM**, concentrandosi solo sul contenuto che conta

---

## Cosa puoi fare

- **Delegare il bookkeeping all'agente** — crea, modifica, organizza pagine Wiki.js e tiene aggiornati i cross-reference al posto tuo
- **Cercare per significato, non per parole chiave** — interrogare la wiki in linguaggio naturale con embedding vettoriali (all-MiniLM-L6-v2) su Qdrant
- **Mantenere la knowledge base in salute** — esplorare backlink, trovare shortest path, rilevare pagine orfane e obsolete con un comando solo
- **Ingerire documenti eterogenei in automatico** — carica PDF, DOCX, Markdown, immagini; l'agente estrae testo (OCR per scansioni), fa chunking e indicizza semanticamente
- **Digitalizzare documenti scansionati** — OCR con Tesseract e preprocessing adattivo (deskew, denoise, threshold) per estrarre testo cercabile da immagini e PDF

---

## Architettura

```
Cursor IDE / Claude Desktop / MCP client
       │
       ├─── Wiki.js MCP        (:8000)  ──► Wiki.js GraphQL  ──► PostgreSQL
       ├─── Qdrant MCP         (:8001)  ──► Qdrant Vector DB
       ├─── Ingestion Pipeline (:8002)  ──► Qdrant + Tesseract
       └─── Tesseract MCP      (:8003)  ──► Tesseract OCR
```

| Server | Container | Porta | Tool | Descrizione |
|--------|-----------|-------|------|-------------|
| **Wiki.js MCP** | `wikijs_mcp` | 8000 | ~43 | CRUD pagine, ricerca semantica, backlink, grafo, health check |
| **Qdrant MCP** | `wikijs_qdrant_mcp` | 8001 | 8 | Gestione collezioni, upsert/ricerca vettoriale, scroll |
| **Ingestion Pipeline** | `wikijs_ingestion` | 8002 | 7 | Detect → Estrai → Chunk → Embed → Upsert (PDF, DOCX, MD, immagini) |
| **Tesseract MCP** | `wikijs_tesseract_mcp` | 8003 | 7 | OCR, estrazione HOCR, confidence scoring, preprocessing |

---

## Come si usa (in breve)

1. **Avvia lo stack** — `docker compose up -d` (8 container, 7 a regime dopo ~60s)
2. **Configura Cursor** — aggiungi i 4 server a `mcp.json` (tipo `sse` sulle porte 8000-8003)
3. **Chiedi all'agente** — "Ingerisci questo PDF e crea una pagina wiki" oppure "Cerca nella wiki informazioni su X"

Hai bisogno di un walkthrough passo-passo? Vai alla [Guida Utente → Primo flusso](userguide/04-primo-flusso.md).

---

## Quick Start

### Prerequisiti

- Docker e Docker Compose v2
- Git

### Avvio

```bash
# 1. Clona e configura
git clone https://github.com/mikep/wiki-js-mcp.git
cd wiki-js-mcp
cp .env.example .env
# Modifica .env: imposta POSTGRES_PASSWORD e WIKIJS_PASSWORD

# 2. Avvia lo stack completo (8 container)
docker compose up -d

# 3. Attendi che Wiki.js completi l'inizializzazione (~60s)
docker compose logs -f wiki

# 4. Verifica che tutto sia attivo (check HTTP status, non bloccante)
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/sse && echo " OK"  # Wiki.js MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/sse && echo " OK"  # Qdrant MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:8002/sse && echo " OK"  # Ingestion Pipeline
curl -s -o /dev/null -w '%{http_code}' http://localhost:8003/sse && echo " OK"  # Tesseract MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 && echo " OK"       # Wiki.js web UI
```

### Configura Cursor IDE

Aggiungi a `mcp.json`:

```json
{
  "mcpServers": {
    "wikijs":     { "type": "sse", "url": "http://localhost:8000/sse" },
    "qdrant":     { "type": "sse", "url": "http://localhost:8001/sse" },
    "ingestion":  { "type": "sse", "url": "http://localhost:8002/sse" },
    "tesseract":  { "type": "sse", "url": "http://localhost:8003/sse" }
  }
}
```

### Primo utilizzo

```bash
# Popola la wiki con dati di test
docker compose exec wiki-js-mcp python3 scripts/seed_wiki_docs.py

# Ingesta un documento (via SSE JSON-RPC; GET /sse → endpoint → POST /messages?session_id=...)
# Nota: il POST diretto su /sse non e' il protocollo SSE standard.
# Preferisci usare i tool via MCP client (Cursor/Claude).
curl -X POST http://localhost:8002/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ingest_document","arguments":{"file_path":"/data/shared/doc.pdf"}},"id":1}'
```

---

## Testing

```bash
# Test veloci (solo Qdrant, nessuno stack completo)
docker compose --profile test run --rm test-runner pytest tests/integration/qdrant/ tests/e2e/ tests/performance/ -v

# Test full-stack (richiede docker compose up -d)
docker compose up -d
docker compose --profile integration run --rm test-runner pytest tests/integration/stack/ tests/regression/ -v

# SSE smoke tests (validazione trasporto reale)
docker compose --profile integration run --rm test-runner pytest tests/smoke/ -v -m smoke

# Unit test (nessun container richiesto)
PYTHONPATH="mcp-servers/qdrant-mcp/src:mcp-servers/ingestion-pipeline/src:mcp-servers/wiki-js-mcp/src:mcp-servers/tesseract-mcp/src" \
pytest tests/unit/ -v -m unit
```

**Risultati attuali:** 60/60 fast test passano. ~109 unit test. ~37 smoke test.

[Guida completa al testing →](doc_v3/reference/testing.md) | [Risultati →](doc_v3/reference/test-results.md)

---

## Documentazione

Tutta la documentazione dettagliata si trova in **[`doc_v3/`](doc_v3/index.md)**. Ecco i punti di ingresso principali:

| Sezione | Descrizione |
|---------|-------------|
| [Guida Utente](userguide/index.md) | Onboarding narrativo per umani, in italiano |
| [Architettura](doc_v3/architecture/index.md) | Design dello stack, Qdrant, pattern multi-MCP |
| [MCP Servers](doc_v3/mcp-servers/index.md) | Catalogo tool per server, configurazione |
| [Features](doc_v3/features/index.md) | Catalogo funzionalità per priorità |
| [Tool Catalog](doc_v3/reference/tool-catalog.md) | Tutti i ~65 tool con firme complete |
| [Patterns](doc_v3/patterns/index.md) | Convenzioni di codice, comunicazione cross-server |
| [Guide](doc_v3/guides/index.md) | Quickstart, workflow, operazioni Docker |
| [Testing](doc_v3/reference/testing.md) | Piramide dei test, CI, comandi |
| [Migrazione da v2](doc_v3/migration/index.md) | Passaggi per migrare da v2 a v3 |
| [Miglioramenti](doc_v3/improvements/index.md) | Roadmap e opportunità future |

### Per iniziare subito

- **Operatori umani:** [Guida Utente](userguide/index.md) → [Quickstart](doc_v3/guides/quickstart.md) → [Multi-MCP Setup](doc_v3/guides/multi-mcp-setup.md)
- **LLM agent:** [System Overview](doc_v3/architecture/system-overview.md) → [Tool Catalog](doc_v3/reference/tool-catalog.md) → [Workflows](doc_v3/guides/llm-wiki-workflows.md)

---

## v2 → v3: Cosa è cambiato

| Aspetto | v2 | v3 |
|---------|-----|-----|
| **Container** | 4 | 8 |
| **Vector engine** | SQLite + MiniLM in-process | Qdrant vettoriale esterno |
| **MCP server** | 1 monolitico | 4 specializzati |
| **OCR** | ❌ | ✅ Tesseract (CPU, eng+ita) |
| **Ingestion** | ❌ | ✅ Pipeline completa (PDF, DOCX, MD, immagini) |
| **Dimensione immagine** | ~1.5 GB (wiki-mcp) | ~200 MB (wiki-mcp) |
| **Tool totali** | 45 | ~65 |
| **Embedding model** | Download lazy a runtime | Pre-download nel Dockerfile |

---

## Licenza

Proprietaria — Tutti i diritti riservati — vedi [LICENSE](LICENSE)
