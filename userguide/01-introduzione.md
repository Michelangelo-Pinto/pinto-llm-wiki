# 01 — Introduzione

## Cos'e' wiki-js-mcp

**wiki-js-mcp** trasforma [Wiki.js](https://js.wiki/) in una **knowledge base potenziata da AI**, accessibile e gestibile direttamente da un agente LLM all'interno del tuo IDE (Cursor, Claude Desktop, o qualsiasi client MCP).

In pratica: puoi chiedere all'agente "cerca nella wiki tutto quello che sappiamo sull'argomento X", "crea una pagina che riassuma i documenti Y e Z", o "controlla se ci sono pagine obsolete", e lui lo fa per te.

## Perche' esiste

Una knowledge base tradizionale ha un problema: **invecchia**. Non perche' la conoscenza diventi obsoleta, ma perche' il **bookkeeping** — aggiornare cross-reference, tenere i riassunti allineati, accorgersi delle contraddizioni — e' noioso, ripetitivo e nessuno lo fa volentieri.

E i documenti grezzi (PDF, scansioni, DOCX) non sono cercabili per significato: puoi cercare solo per nome file o, se hai fortuna, per parole chiave nel testo.

## Il pattern LLM Wiki

wiki-js-mcp implementa il **pattern LLM Wiki**: una knowledge base mantenuta interamente da un agente LLM. Tre livelli:

| Livello | Chi lo gestisce | Cosa contiene |
|---------|----------------|---------------|
| **Sorgenti grezze** | Solo umano | PDF, scansioni, DOCX, immagini — immutabili |
| **La wiki** | Solo agente LLM | Pagine markdown interconnesse, indici, riassunti |
| **Lo schema** | Umano + agente | Convenzioni e workflow in `AGENTS.md`, `.cursor/rules/` |

L'umano decide **cosa** e' importante e definisce le regole. L'agente esegue il lavoro ripetitivo: non si annoia, non dimentica un cross-reference e puo' toccare 15 pagine in un colpo solo.

## Le quattro operazioni

1. **Ingest** — carica documenti grezzi, l'agente li processa (OCR, chunking, embedding) e li rende cercabili
2. **Query** — interroga la wiki in linguaggio naturale ("cosa sappiamo di X?")
3. **Lint** — controlla la salute della wiki: pagine orfane, link rotti, contenuti obsoleti
4. **Document Processing** — crea, modifica, organizza e interconnette pagine wiki

## Quali problemi risolve

- **Documenti non cercabili** → ingestion con OCR + ricerca semantica vettoriale (Qdrant)
- **Wiki disordinata e da aggiornare a mano** → l'agente mantiene index, log e cross-reference
- **Necessita' di interrogare la conoscenza dall'IDE** → MCP + `wikijs_smart_query` in linguaggio naturale
- **Pagine orfane o obsolete** → `wikijs_wiki_health` per diagnosticare lo stato della wiki

## Per chi e'

- Sviluppatori che vogliono una knowledge base interrogabile senza uscire dall'IDE
- Team con molti documenti da rendere cercabili e una wiki da mantenere nel tempo
- Ricercatori con archivi di PDF e scansioni da digitalizzare e indicizzare

---

*Approfondisci in: [doc_v3/guides/llm-wiki-workflows.md](../doc_v3/guides/llm-wiki-workflows.md)*

*Prossimo: [02 — Architettura](02-architettura.md) · Torna all'[indice](index.md)*
