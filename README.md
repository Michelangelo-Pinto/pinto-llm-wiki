# pinto-llm-wiki v4

**pinto-llm-wiki** e' una knowledge base file-system potenziata da AI, accessibile direttamente da LLM agent (Cursor IDE, Claude Desktop, e qualsiasi client MCP).

Fornisce **22 strumenti MCP** suddivisi su **3 server indipendenti** in **4 container Docker**: ricerca semantica vettoriale (Qdrant), OCR documentale (Tesseract), e una pipeline di ingestion che processa PDF, DOCX, immagini e Markdown. La conoscenza vive in file `.md` nella cartella `knowledge/`.

> **Nuovo qui?** Parti dalla [Guida Utente](userguide/index.md) — un percorso di onboarding pensato per umani, in italiano.

---

## Perche' esiste

Una knowledge base invecchia. La parte noiosa non e' leggere o pensare, ma il **bookkeeping**: aggiornare i cross-reference, tenere i riassunti allineati, accorgersi delle contraddizioni, mantenere coerenza tra decine di file. I documenti grezzi (PDF, scansioni, DOCX) non sono cercabili per significato.

**pinto-llm-wiki** applica il **pattern LLM Wiki**: una knowledge base mantenuta da un agente LLM. L'agente non si annoia, non dimentica un cross-reference e puo' toccare 15 file in un colpo solo. Tre livelli: **sorgenti grezze** (immutabili, solo umano), **la KB** (file markdown interconnessi in `knowledge/`, gestiti dall'agente), e **lo schema** (convenzioni e workflow in `AGENTS.md` e `.cursor/rules/`, definiti da umano + agente).

## Quali problemi risolve

- **"Ho centinaia di PDF e scansioni e non riesco a cercarli per significato"** — ingestion con OCR automatico (Tesseract) e ricerca semantica vettoriale (Qdrant)
- **"La documentazione e' disordinata e va aggiornata a mano"** — l'agente mantiene index, cross-reference, log e tiene tutto coerente
- **"Voglio interrogare la mia conoscenza in linguaggio naturale dall'IDE"** — MCP + `qdrant_search` direttamente da Cursor
- **"I file diventano orfani o obsoleti"** — l'agente puo' verificare consistenza con `Grep` e `Glob`

## Per chi e'

- **Sviluppatori e ricercatori** che vogliono una knowledge base interrogabile in linguaggio naturale senza uscire dall'IDE
- **Team tecnici** con molti documenti da rendere cercabili e una KB da mantenere viva nel tempo
- **Chiunque voglia delegare il bookkeeping della conoscenza a un agente LLM**, concentrandosi solo sul contenuto che conta

---

## Cosa puoi fare

- **Delegare il bookkeeping all'agente** — crea, modifica, organizza file markdown e tiene aggiornati gli index al posto tuo
- **Cercare per significato, non per parole chiave** — interrogare la KB in linguaggio naturale con embedding vettoriali (all-MiniLM-L6-v2) su Qdrant
- **Mantenere la KB in salute** — verificare frontmatter, consistenza index, link con strumenti filesystem
- **Ingerire documenti eterogenei in automatico** — carica PDF, DOCX, Markdown, immagini; l'agente estrae testo (OCR per scansioni), fa chunking e indicizza semanticamente
- **Digitalizzare documenti scansionati** — OCR con Tesseract e preprocessing adattivo (deskew, denoise, threshold) per estrarre testo cercabile da immagini e PDF

---

## Architettura

```
Cursor IDE / Claude Desktop / MCP client
       │
       ├─── Qdrant MCP         (:8001)  ──► Qdrant Vector DB
       ├─── Ingestion Pipeline (:8002)  ──► Qdrant + Tesseract
       └─── Tesseract MCP      (:8003)  ──► Tesseract OCR
                         │
                   knowledge/ (file-system MD)
```

| Server | Container | Porta | Tool | Descrizione |
|--------|-----------|-------|------|-------------|
| **Qdrant MCP** | `pinto_llm_qdrant_mcp` | 8001 | 8 | Gestione collezioni, upsert/ricerca vettoriale, scroll |
| **Ingestion Pipeline** | `pinto_llm_ingestion` | 8002 | 7 | Detect → Estrai → Chunk → Embed → Upsert (PDF, DOCX, MD, immagini) |
| **Tesseract MCP** | `pinto_llm_tesseract_mcp` | 8003 | 7 | OCR, estrazione HOCR, confidence scoring, preprocessing |

---

## Come si usa (in breve)

1. **Avvia lo stack** — `docker compose up -d` (4 container dopo ~60s)
2. **Configura Cursor** — aggiungi i 3 server a `mcp.json` (tipo `sse` sulle porte 8001-8003)
3. **Chiedi all'agente** — "Ingerisci questo PDF" oppure "Cerca nella KB informazioni su X"

Hai bisogno di un walkthrough passo-passo? Vai alla [Guida Utente → Primo flusso](userguide/04-primo-flusso.md).

---

## Quick Start

### Prerequisiti

- Docker e Docker Compose v2
- Git
- 4 GB RAM

### Avvio

```bash
# 1. Clona e configura
git clone https://github.com/Michelangelo-Pinto/pinto-llm-wiki.git
cd pinto-llm-wiki
cp .env.example .env

# 2. Avvia lo stack completo (4 container)
docker compose up -d

# 3. Verifica che tutto sia attivo
docker compose ps
curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/sse && echo " OK"  # Qdrant MCP
curl -s -o /dev/null -w '%{http_code}' http://localhost:8002/sse && echo " OK"  # Ingestion Pipeline
curl -s -o /dev/null -w '%{http_code}' http://localhost:8003/sse && echo " OK"  # Tesseract MCP
```

### Configura Cursor IDE

Aggiungi a `mcp.json`:

```json
{
  "mcpServers": {
    "qdrant":     { "type": "sse", "url": "http://localhost:8001/sse" },
    "ingestion":  { "type": "sse", "url": "http://localhost:8002/sse" },
    "tesseract":  { "type": "sse", "url": "http://localhost:8003/sse" }
  }
}
```

---

## Testing

```bash
# Test veloci (solo Qdrant)
docker compose --profile test run --rm test-runner

# Test full-stack (richiede docker compose up -d)
docker compose up -d
docker compose --profile integration run --rm test-runner \
  pytest tests/integration/stack/ tests/smoke/ -v

# Unit test (nessun container richiesto)
PYTHONPATH="mcp-servers/qdrant-mcp/src:mcp-servers/ingestion-pipeline/src:mcp-servers/tesseract-mcp/src" \
pytest tests/unit/ -v -m unit
```

---

## Documentazione

Tutta la documentazione dettagliata si trova in **[`doc_v4/`](doc_v4/index.md)**. Ecco i punti di ingresso principali:

| Sezione | Descrizione |
|---------|-------------|
| [Guida Utente](userguide/index.md) | Onboarding narrativo per umani, in italiano |
| [Architettura](doc_v4/architecture/index.md) | Design dello stack, Qdrant, pattern MCP |
| [MCP Servers](doc_v4/mcp-servers/index.md) | Catalogo tool per server, configurazione |
| [Tool Catalog](doc_v4/reference/tool-catalog.md) | Tutti i 22 tool con firme complete |
| [Patterns](doc_v4/patterns/index.md) | Convenzioni di codice, comunicazione |
| [Guide](doc_v4/guides/index.md) | Quickstart, workflow, operazioni Docker |
| [Testing](doc_v4/reference/testing.md) | Piramide dei test, CI, comandi |
| [Migrazione da v3](doc_v4/migration/index.md) | Passaggi per migrare da v3 a v4 |

### Per iniziare subito

- **Operatori umani:** [Guida Utente](userguide/index.md) → [Quickstart](doc_v4/guides/quickstart.md)
- **LLM agent:** [System Overview](doc_v4/architecture/system-overview.md) → [Tool Catalog](doc_v4/reference/tool-catalog.md) → [Workflows](doc_v4/guides/llm-wiki-workflows.md)

---

## v3 → v4: Cosa e' cambiato

| Aspetto | v3 | v4 |
|---------|-----|-----|
| **Container** | 8 | 4 |
| **MCP server** | 4 (Wiki.js MCP incluso) | 3 (Wiki.js MCP rimosso) |
| **Tool totali** | ~65 | 22 |
| **Knowledge store** | Wiki.js + PostgreSQL | File-system `knowledge/` |
| **Wiki.js MCP** | 43 tool CRUD, grafo, health | Rimosso |
| **OCR** | Tesseract (eng+ita) | Tesseract (eng+ita) invariato |
| **Ingestion** | Pipeline completa | Pipeline completa invariata |
| **Ricerca semantica** | Qdrant (RRF con keyword) | Qdrant (semantico puro) |

---

## Licenza

Proprietaria — Tutti i diritti riservati — vedi [LICENSE](LICENSE)
