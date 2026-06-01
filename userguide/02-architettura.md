# 02 — Architettura

## Come funziona per un umano

pinto-llm-wiki v4 e' composto da **3 server MCP indipendenti**, ciascuno specializzato in una funzione. Tu (o meglio, il tuo agente LLM) parli con questi server tramite il protocollo MCP (Model Context Protocol) in modalita' **SSE** (Server-Sent Events). I server girano in **4 container Docker**.

Il concetto chiave: l'agente LLM **orchestra** i 3 server. Tu chiedi cose in linguaggio naturale e l'agente decide quali tool chiamare, su quale server, in quale ordine.

La knowledge base e' basata su **file-system**: tutti i contenuti sono file `.md` nella cartella `knowledge/`, organizzati per categorie e sottocategorie con `index.md` per il routing.

```mermaid
flowchart TD
    Agent["Agente LLM (Cursor IDE)"]
    QMCP["Qdrant MCP<br/>:8001 — 8 tool"]
    IMCP["Ingestion Pipeline<br/>:8002 — 7 tool"]
    TMCP["Tesseract MCP<br/>:8003 — 7 tool"]
    Qdrant["Qdrant Vector DB<br/>:6334"]
    KB["knowledge/ (file-system MD)"]

    Agent -->|"MCP/SSE"| QMCP
    Agent -->|"MCP/SSE"| IMCP
    Agent -->|"MCP/SSE"| TMCP
    Agent -->|"read/write MD"| KB
    QMCP --> Qdrant
    IMCP --> Qdrant
    IMCP --> TMCP
```

## I tre server spiegati

### Qdrant MCP (`:8001`, 8 tool)

Il **motore di ricerca semantica**. Gestisce collezioni di embedding vettoriali e permette di cercare per **significato**, non per parole chiave. Usa il modello `all-MiniLM-L6-v2` per generare embedding.

Tool principali: `qdrant_search`, `qdrant_upsert_chunks`, `qdrant_list_collections`.

### Ingestion Pipeline (`:8002`, 7 tool)

La **catena di montaggio** dei documenti. Prende un file grezzo (PDF, DOCX, Markdown, immagine), lo processa in 5 fasi: Detect (tipo file) → Extract (testo) → Chunk (spezzetta in porzioni) → Embed (genera vettori) → Upsert (carica su Qdrant).

Tool principali: `ingest_document`, `ingest_get_status`.

### Tesseract MCP (`:8003`, 7 tool)

Il **lettore OCR**. Estrae testo da immagini e PDF scansionati usando Tesseract, con preprocessing adattivo (raddrizza, riduce il rumore, regola la soglia) per massimizzare la qualita' del riconoscimento. Supporta inglese e italiano.

Tool principali: `ocr_extract_text`, `ocr_extract_hocr`, `ocr_get_confidence`.

## La knowledge base file-system

In v4, la conoscenza non vive piu' in un database (Wiki.js + PostgreSQL) ma in file markdown su disco:

```
knowledge/
  index.md                     # Indice master
  software-engineering/
    index.md                   # Indice di categoria
    architecture/
      index.md                 # Indice di sottocategoria
      microservizi.md          # Pagina di conoscenza
```

L'agente legge e scrive direttamente i file `.md`. La ricerca funziona cosi':
- **Ricerca semantica**: `qdrant_search` su Qdrant
- **Ricerca testuale**: `Grep` sui file `.md`
- **Navigazione strutturata**: segui i link negli `index.md`

## Come l'agente li orchestra

Quando chiedi all'agente _"Ingerisci questo PDF e dimmi cosa contiene"_, lui ragiona cosi':

1. Chiama `ingest_document` sulla **Ingestion Pipeline** per processare il PDF
2. La pipeline internamente usa **Tesseract** se il PDF contiene scansioni
3. Il testo viene chunk-ato, embedded e caricato su **Qdrant**
4. L'agente chiama `qdrant_search` per recuperare i chunk rilevanti
5. Se serve salvare le informazioni, scrive un file `.md` in `knowledge/` con `Write`

Tutto questo senza che tu debba sapere quali tool esistono o su che porta girano.

---

*Approfondisci in: [doc_v4/architecture/system-overview.md](../doc_v4/architecture/system-overview.md)*

*Precedente: [01 — Introduzione](01-introduzione.md) · Prossimo: [03 — Installazione e setup](03-installazione-e-setup.md) · Torna all'[indice](index.md)*
