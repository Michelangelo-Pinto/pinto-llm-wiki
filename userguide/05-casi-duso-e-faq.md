# 05 — Casi d'uso e FAQ

## Scenari d'uso tipici

### Ricercatore con archivio PDF

Hai centinaia di paper, relazioni e scansioni in PDF. Vuoi poterli cercare per significato e produrre riassunti.

**Flusso tipico:**
1. Copi i PDF in `to_ingest/`
2. Chiedi all'agente: "Ingerisci tutti i PDF nella cartella e crea un riepilogo per ciascuno in knowledge/"
3. Poi: "Cerca nella KB tutto quello che riguarda il tema X e fammi un riassunto"

### Team documentation

Il tuo team ha una knowledge base ma tenerla aggiornata e' un lavoro che nessuno fa volentieri.

**Flusso tipico:**
1. Definisci le convenzioni in `AGENTS.md` (template file, naming, struttura)
2. L'agente crea e mantiene i file markdown basandosi sui documenti sorgente
3. Periodicamente: "Fai un controllo della KB e sistemiamo i file obsoleti"

### Knowledge base personale

Vuoi una "seconda memoria" digitale dove riversare appunti, articoli, note e poterli interrogare.

**Flusso tipico:**
1. Carichi i documenti via ingestion
2. Interroghi in linguaggio naturale: "Cosa ho salvato sul tema X?"
3. L'agente mantiene indici e riassunti aggiornati

### Ricerca web e archiviazione nella KB

Vuoi salvare pagine web, articoli, o documentazione online nella tua knowledge base, con tracciamento della fonte.

**Flusso tipico:**
1. Chiedi all'agente: "Vai su questo URL e salvalo nella KB"
2. L'agente usa il browser MCP per navigare, estrarre il contenuto e creare un file in `knowledge/ingested/`
3. Il file include automaticamente la fonte (URL, data acquisizione) nel frontmatter
4. Puoi sempre risalire a dove hai preso ogni informazione

## FAQ

### Come funziona la ricerca in v4?

Due modalita' complementari:
- **Ricerca semantica** (`qdrant_search`): cerca per significato usando embedding vettoriali. Capisce che "auto" e "automobile" sono la stessa cosa.
- **Ricerca testuale** (`Grep`): cerca parole esatte nei file `.md` della knowledge base.

### Quanto ci mette l'ingestion di un documento?

Dipende dalla dimensione e dal tipo. Un PDF di 10 pagine solo testo: pochi secondi. Un PDF scansionato di 100 pagine: qualche minuto, perche' deve passare attraverso OCR (Tesseract).

### Posso usare pinto-llm-wiki senza Docker?

No. Lo stack e' interamente containerizzato e richiede Docker Compose v2.

### Quanti documenti posso indicizzare?

Qdrant scala bene fino a centinaia di migliaia di documenti. Il collo di bottiglia e' lo spazio disco e la RAM per gli embedding.

### Quanti container ci sono in v4?

4 container: Qdrant DB, Qdrant MCP, Ingestion Pipeline, Tesseract MCP. In v3 ce n'erano 8 (inclusi PostgreSQL, Wiki.js e Wiki.js MCP — tutti rimossi in v4).

### L'agente puo' fare danni alla KB?

L'agente puo' creare, modificare e cancellare file in `knowledge/`. Le **sorgenti grezze** (PDF, immagini originali) sono immutabili per l'agente — solo l'umano puo' modificarle o cancellarle. Definisci regole chiare in `AGENTS.md` per limitare cosa l'agente puo' fare.

### Come faccio a portare una pagina web nella KB?

Chiedi all'agente: "Vai su questo URL e salvalo nella knowledge base". L'agente usera' un browser MCP (Playwright DevTools o Cursor integrato) per navigare, estrarre il contenuto, e creare un file in `knowledge/ingested/` con l'attribuzione della fonte. Vedi `.cursor/rules/35-web-ingestion.mdc` per i dettagli.

### Come vengono tracciate le fonti?

Ogni file creato da contenuto esterno include nel **frontmatter**:
- `source_type`: `web` (da browser), `file` (da PDF/DOCX), o `upload` (da scansione)
- `source_url`: l'URL completo se proviene dal web
- `source_file`: il nome del file originale
- `source_name`: un nome descrittivo (titolo articolo, nome libro)
- `fetched_at`: data di acquisizione

Queste informazioni sono visibili nei metadati del file e nel `knowledge/log.md`.

## Cosa l'agente puo' fare

- Creare, modificare, organizzare e cancellare file markdown in `knowledge/`
- Ingerire documenti (PDF, DOCX, MD, immagini)
- Estrarre testo da scansioni con OCR
- Indicizzare semanticamente e cercare per significato
- Generare riassunti e mantenere cross-reference
- Diagnosticare problemi strutturali della KB (frontmatter mancanti, index obsoleti)
- **Navigare sul web con un browser MCP** ed estrarre contenuti da pagine, articoli e documentazione online
- **Tracciare automaticamente la fonte** di ogni contenuto (URL, nome file, data)

## Cosa l'agente NON puo' fare

- Modificare o cancellare i file sorgente originali (sono immutabili per l'agente)
- Prendere decisioni editoriali — l'umano definisce cosa e' importante
- Sostituire il giudizio umano su qualita' e accuratezza dei contenuti
- Funzionare senza che lo stack Docker sia attivo

## Problemi? Dove cercare aiuto

1. **Errori noti** → [doc_v4/reference/error-catalog.md](../doc_v4/reference/error-catalog.md)
2. **Guida al troubleshooting** → [doc_v4/guides/troubleshooting.md](../doc_v4/guides/troubleshooting.md)
3. **Test suite** → esegui `docker compose --profile test run --rm test-runner` per verificare lo stato del sistema
4. **Log dei container** → `docker compose logs -f [nome-container]`

---

*Approfondisci in: [doc_v4/guides/troubleshooting.md](../doc_v4/guides/troubleshooting.md) · [doc_v4/reference/error-catalog.md](../doc_v4/reference/error-catalog.md)*

*Precedente: [04 — Primo flusso](04-primo-flusso.md) · Torna all'[indice](index.md)*
