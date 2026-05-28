# 05 — Casi d'uso e FAQ

## Scenari d'uso tipici

### Ricercatore con archivio PDF

Hai centinaia di paper, relazioni e scansioni in PDF. Vuoi poterli cercare per significato e produrre riassunti.

**Flusso tipico:**
1. Copi i PDF in `/data/shared`
2. Chiedi all'agente: "Ingerisci tutti i PDF nella cartella e crea una pagina wiki per ciascuno"
3. Poi: "Cerca nella wiki tutto quello che riguarda il tema X e fammi un riassunto"

### Team documentation

Il tuo team ha una wiki ma tenerla aggiornata e' un lavoro che nessuno fa volentieri.

**Flusso tipico:**
1. Definisci le convenzioni in `AGENTS.md` (template pagine, naming, struttura)
2. L'agente crea e mantiene le pagine wiki basandosi sui documenti sorgente
3. Periodicamente: "Fai un health check della wiki e sistemiamo le pagine orfane"

### Knowledge base personale

Vuoi una "seconda memoria" digitale dove riversare appunti, articoli, note e poterli interrogare.

**Flusso tipico:**
1. Carichi i documenti via ingestion
2. Interroghi in linguaggio naturale: "Cosa ho salvato sul tema X?"
3. L'agente mantiene indici e riassunti aggiornati

## FAQ

### Che differenza c'e' tra `wikijs_search` e `wikijs_smart_query`?

`wikijs_search` e' una ricerca testuale tradizionale (per parole chiave). `wikijs_smart_query` usa gli embedding vettoriali di Qdrant per cercare per **significato** — capisce che "auto" e "automobile" sono la stessa cosa.

### Quanto ci mette l'ingestion di un documento?

Dipende dalla dimensione e dal tipo. Un PDF di 10 pagine solo testo: pochi secondi. Un PDF scansionato di 100 pagine: qualche minuto, perche' deve passare attraverso OCR (Tesseract).

### Posso usare wiki-js-mcp senza Docker?

No. Lo stack e' interamente containerizzato e richiede Docker Compose v2.

### Quanti documenti posso indicizzare?

Qdrant scala bene fino a centinaia di migliaia di documenti. Il collo di bottiglia e' lo spazio disco e la RAM per gli embedding.

### Perche' ci sono 8 container ma solo 7 a regime?

Un container (`wiki-init`) esegue l'inizializzazione di Wiki.js (migration del DB, configurazione iniziale) e poi esce. Gli altri 7 restano attivi.

### L'agente puo' fare danni alla wiki?

L'agente puo' modificare, creare e cancellare pagine wiki. Le **sorgenti grezze** (PDF, immagini originali) sono immutabili per l'agente — solo l'umano puo' modificarle o cancellarle. Definisci regole chiare in `AGENTS.md` per limitare cosa l'agente puo' fare.

## Cosa l'agente puo' fare

- Creare, modificare, organizzare e cancellare pagine wiki
- Ingerire documenti (PDF, DOCX, MD, immagini)
- Estrarre testo da scansioni con OCR
- Indicizzare semanticamente e cercare per significato
- Generare riassunti e mantenere cross-reference
- Diagnosticare problemi strutturali della wiki (health check)
- Navigare il grafo dei link (backlink, shortest path, orfane)

## Cosa l'agente NON puo' fare

- Modificare o cancellare i file sorgente originali (sono immutabili per l'agente)
- Prendere decisioni editoriali — l'umano definisce cosa e' importante
- Sostituire il giudizio umano su qualita' e accuratezza dei contenuti
- Funzionare senza che lo stack Docker sia attivo

## Problemi? Dove cercare aiuto

1. **Errori noti** → [doc_v3/reference/error-catalog.md](../doc_v3/reference/error-catalog.md)
2. **Guida al troubleshooting** → [doc_v3/guides/troubleshooting.md](../doc_v3/guides/troubleshooting.md)
3. **Test suite** → esegui `docker compose --profile test run --rm test-runner` per verificare lo stato del sistema
4. **Log dei container** → `docker compose logs -f [nome-container]`

---

*Approfondisci in: [doc_v3/guides/troubleshooting.md](../doc_v3/guides/troubleshooting.md) · [doc_v3/reference/error-catalog.md](../doc_v3/reference/error-catalog.md)*

*Precedente: [04 — Primo flusso](04-primo-flusso.md) · Torna all'[indice](index.md)*
