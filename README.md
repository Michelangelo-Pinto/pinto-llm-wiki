# wiki-js-mcp v3

[![Test Suite](https://github.com/mikep/wiki-js-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/mikep/wiki-js-mcp/actions/workflows/test.yml)

**wiki-js-mcp** trasforma [Wiki.js](https://js.wiki/) in una knowledge base potenziata da AI, accessibile direttamente da LLM agent (Cursor IDE, Claude Desktop, e qualsiasi client MCP).

Fornisce **~65 strumenti MCP** suddivisi su **4 server indipendenti** in **8 container Docker**: gestione pagine wiki, ricerca semantica vettoriale (Qdrant), OCR documentale (Tesseract), e una pipeline di ingestion che processa PDF, DOCX, immagini e Markdown.

---

## Cosa puoi fare

- **Gestire pagine wiki** — creare, modificare, cercare, importare/esportare e organizzare gerarchicamente pagine Wiki.js, tutto tramite LLM
- **Ricerca semantica** — interrogare la wiki con linguaggio naturale usando embedding vettoriali (all-MiniLM-L6-v2) su Qdrant
- **Grafo dei link** — esplorare backlink, trovare shortest path e rilevare pagine orfane
- **Ingestion documentale** — caricare PDF, DOCX, Markdown, immagini; estrarre testo (con OCR per documenti scansionati); chunk-are e indicizzare semanticamente su Qdrant
- **OCR** — estrarre testo da immagini e PDF scansionati con Tesseract, incluso preprocessing adattivo (deskew, denoise, threshold)

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

# 4. Verifica che tutto sia attivo
curl http://localhost:8000/sse   # Wiki.js MCP
curl http://localhost:8001/sse   # Qdrant MCP
curl http://localhost:8002/sse   # Ingestion Pipeline
curl http://localhost:8003/sse   # Tesseract MCP
curl http://localhost:3000       # Wiki.js web UI
```

### Configura Cursor IDE

Aggiungi a `mcp.json`:

```json
{
  "mcpServers": {
    "wiki-js":     { "url": "http://localhost:8000/sse" },
    "qdrant":      { "url": "http://localhost:8001/sse" },
    "ingestion":   { "url": "http://localhost:8002/sse" },
    "tesseract":   { "url": "http://localhost:8003/sse" }
  }
}
```

### Primo utilizzo

```bash
# Popola la wiki con dati di test
docker compose exec wiki-js-mcp python3 scripts/seed_wiki_docs.py

# Ingesta un documento
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

- **Operatori umani:** [Quickstart](doc_v3/guides/quickstart.md) → [Multi-MCP Setup](doc_v3/guides/multi-mcp-setup.md)
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
