# 04 — Primo flusso

Ecco un walkthrough end-to-end del flusso piu' tipico: prendere un PDF, ingerirlo, creare una pagina wiki, interrogare la conoscenza e verificare lo stato di salute.

## Scenario

Hai un PDF (es. `relazione-2024.pdf`) in `/data/shared` e vuoi:
1. Ingerirlo per renderlo cercabile
2. Creare una pagina wiki che lo riassuma
3. Fare una ricerca semantica per verificare che sia indicizzato
4. Controllare lo stato della wiki

## Passo 1 — Ingerire il documento

Copia il PDF nella cartella condivisa:

```bash
cp relazione-2024.pdf /data/shared/
```

In Cursor, scrivi all'agente:

> **Prompt:** Ingerisci il file `/data/shared/relazione-2024.pdf` e indicizzalo su Qdrant.

L'agente chiamera' `ingest_document` sulla Ingestion Pipeline, che esegue il pipeline completo (detect → extract → chunk → embed → upsert). Se il PDF contiene scansioni, Tesseract entrera' in azione automaticamente per l'OCR.

## Passo 2 — Creare una pagina wiki

> **Prompt:** Crea una pagina wiki intitolata "Relazione 2024" che riassuma il contenuto del documento `/data/shared/relazione-2024.pdf`.

L'agente usera' `wikijs_create_page` (o `wikijs_create_or_update_page`) per creare la pagina su Wiki.js, recuperando il contenuto rilevante da Qdrant.

## Passo 3 — Interrogare la conoscenza

> **Prompt:** Cerca nella wiki informazioni sul tema principale della relazione 2024.

L'agente chiamera' `wikijs_smart_query` (o una combinazione di `qdrant_search` + ricerca wiki) e ti restituira' un riassunto basato sui chunk indicizzati.

## Passo 4 — Verificare la salute della wiki

> **Prompt:** Fai un health check della wiki e dimmi se ci sono problemi.

L'agente chiamera' `wikijs_wiki_health` e ti dara' un report: pagine orfane, backlink mancanti, pagine vuote o obsolete.

## Passo 5 — Web ingestion (portare una pagina web nella wiki)

> **Prompt:** Vai su https://it.wikipedia.org/wiki/Grafo_della_conoscenza, estrai il contenuto e crea una pagina wiki.
> (oppure: "usa il browser di Cursor e portami questo articolo nella wiki")

L'agente aprira' il browser MCP (Playwright o Cursor integrato), navighera' all'URL, estrarra' il contenuto, lo formattera' in markdown e creera' una pagina wiki con l'attribuzione della fonte nel frontmatter (`source_type: "web"`, `source_url`, `source_name`, `fetched_at`).

Per contenuti complessi (molte immagini, PDF), l'agente puo' usare il Percorso B (salva file → chiedi copia in `/data/shared/` → `ingest_document`). Vedi `.cursor/rules/35-web-ingestion.mdc`.

## Riassunto del flusso

```
PDF in /data/shared
    │
    ▼
ingest_document ──► OCR (se serve) ──► chunk + embed ──► Qdrant
    │
    ▼
wikijs_create_page ──► Wiki.js (pagina creata, linkata)
    │
    ▼
wikijs_smart_query ──► recupera informazioni per significato
    │
    ▼
wikijs_wiki_health ──► report salute wiki
```

## Cosa fare se qualcosa non funziona

- **Errore "file not found"**: assicurati che il file sia in `/data/shared` (il percorso dentro il container)
- **Timeout sull'ingestion**: i PDF grandi o scansionati possono richiedere tempo; usa `ingest_status` per monitorare
- **Nessun risultato nella ricerca**: verifica che l'ingestion sia completata e che la collezione Qdrant esista (`qdrant_list_collections`)

---

*Approfondisci in: [doc_v3/guides/agent-orientation.md](../doc_v3/guides/agent-orientation.md) · [doc_v3/guides/llm-wiki-workflows.md](../doc_v3/guides/llm-wiki-workflows.md) · [doc_v3/guides/file-paths-and-volumes.md](../doc_v3/guides/file-paths-and-volumes.md)*

*Precedente: [03 — Installazione e setup](03-installazione-e-setup.md) · Prossimo: [05 — Casi d'uso e FAQ](05-casi-duso-e-faq.md) · Torna all'[indice](index.md)*
