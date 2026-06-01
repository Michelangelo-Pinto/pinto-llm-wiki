# 04 — Primo flusso

Ecco un walkthrough end-to-end del flusso piu' tipico: prendere un PDF, ingerirlo, cercarlo semanticamente e creare un file di conoscenza.

## Scenario

Hai un PDF (es. `relazione-2024.pdf`) in `/data/shared` e vuoi:
1. Ingerirlo per renderlo cercabile
2. Cercare informazioni al suo interno
3. Creare un file di riepilogo nella knowledge base
4. Verificare che tutto sia coerente

## Passo 1 — Ingerire il documento

Copia il PDF nella cartella condivisa:

```bash
cp relazione-2024.pdf to_ingest/
```

In Cursor, scrivi all'agente:

> **Prompt:** Ingerisci il file `/data/shared/relazione-2024.pdf` e indicizzalo su Qdrant.

L'agente chiamera' `ingest_document` sulla Ingestion Pipeline, che esegue il pipeline completo (detect → extract → chunk → embed → upsert). Se il PDF contiene scansioni, Tesseract entrera' in azione automaticamente per l'OCR.

## Passo 2 — Cercare informazioni

> **Prompt:** Cerca informazioni sul tema principale della relazione 2024.

L'agente chiamera' `qdrant_search` e ti restituira' i risultati con i punteggi di similarita'. Puoi anche chiedere una ricerca testuale: _"Cerca tutti i file che parlano di X"_.

## Passo 3 — Creare un file di conoscenza

> **Prompt:** Crea un file `knowledge/ingested/2026-06-01-relazione/riepilogo.md` con un riassunto del documento e i metadati della fonte.

L'agente scrivera' il file `.md` con frontmatter completo:
```yaml
---
title: "Relazione 2024"
source_type: file
source_file: "relazione-2024.pdf"
source_name: "Relazione Annuale 2024"
fetched_at: "2026-06-01"
---
```

E aggiornera' `knowledge/ingested/index.md` con la nuova entry.

## Passo 4 — Verificare la consistenza

> **Prompt:** Controlla che tutti i file in knowledge/ abbiano il frontmatter corretto e siano elencati negli index.md delle loro categorie.

L'agente fara' un lint della knowledge base: `Glob`, `Grep`, verifica dei frontmatter e degli index.

## Passo 5 — Web ingestion (portare una pagina web nella KB)

> **Prompt:** Vai su https://it.wikipedia.org/wiki/Grafo_della_conoscenza, estrai il contenuto e salvalo nella knowledge base.
> (oppure: "usa il browser di Cursor e portami questo articolo nella KB")

L'agente aprira' il browser MCP, navighera' all'URL, estrarra' il contenuto, lo formattera' in markdown e creera' un file in `knowledge/ingested/` con l'attribuzione della fonte.

Per contenuti complessi, l'agente puo' usare il Percorso B (salva file → chiedi copia in `/data/shared/` → `ingest_document`). Vedi `.cursor/rules/35-web-ingestion.mdc`.

## Riassunto del flusso

```
PDF in /data/shared
    │
    ▼
ingest_document ──► OCR (se serve) ──► chunk + embed ──► Qdrant
    │
    ▼
qdrant_search ──► recupera informazioni per significato
    │
    ▼
Write ──► knowledge/ingested/.../riepilogo.md (file creato, indicizzato)
    │
    ▼
Grep + Glob ──► verifica consistenza
```

## Cosa fare se qualcosa non funziona

- **Errore "file not found"**: assicurati che il file sia in `/data/shared` (il percorso dentro il container)
- **Timeout sull'ingestion**: i PDF grandi o scansionati possono richiedere tempo; usa `ingest_get_status` per monitorare
- **Nessun risultato nella ricerca**: verifica che l'ingestion sia completata e che la collezione Qdrant esista (`qdrant_list_collections`)

---

*Approfondisci in: [doc_v4/guides/agent-orientation.md](../doc_v4/guides/agent-orientation.md) · [doc_v4/guides/llm-wiki-workflows.md](../doc_v4/guides/llm-wiki-workflows.md) · [doc_v4/guides/file-paths-and-volumes.md](../doc_v4/guides/file-paths-and-volumes.md)*

*Precedente: [03 — Installazione e setup](03-installazione-e-setup.md) · Prossimo: [05 — Casi d'uso e FAQ](05-casi-duso-e-faq.md) · Torna all'[indice](index.md)*
