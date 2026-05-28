# 03 — Installazione e setup

Questo capitolo ti guida dallo zero al primo comando funzionante. Se qualcosa va storto, alla fine trovi una checklist di verifica.

## Prerequisiti

- **Docker** e **Docker Compose v2** installati e funzionanti
- **Git** per clonare il repository
- **Cursor IDE** (o un client MCP compatibile) per usare i tool

## Avvio dello stack

```bash
# 1. Clona il repository
git clone https://github.com/mikep/wiki-js-mcp.git
cd wiki-js-mcp

# 2. Configura le variabili d'ambiente
cp .env.example .env
# Modifica .env: imposta POSTGRES_PASSWORD e WIKIJS_PASSWORD

# 3. Avvia lo stack (8 container, 7 a regime)
docker compose up -d

# 4. Attendi ~60 secondi che Wiki.js completi l'inizializzazione
docker compose logs -f wiki
# Premi Ctrl+C quando vedi il messaggio di avvio completato

# 5. Verifica che tutto risponda
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/sse && echo " Wiki.js MCP OK"
curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/sse && echo " Qdrant MCP OK"
curl -s -o /dev/null -w '%{http_code}' http://localhost:8002/sse && echo " Ingestion OK"
curl -s -o /dev/null -w '%{http_code}' http://localhost:8003/sse && echo " Tesseract OK"
curl -s -o /dev/null -w '%{http_code}' http://localhost:3000     && echo " Wiki.js UI OK"
```

Tutti e 5 dovrebbero rispondere con un HTTP status. Lo stack e' pronto.

## Configurare Cursor IDE

Apri (o crea) il file `mcp.json` nella root del progetto e aggiungi:

```json
{
  "mcpServers": {
    "wikijs": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    },
    "qdrant": {
      "type": "sse",
      "url": "http://localhost:8001/sse"
    },
    "ingestion": {
      "type": "sse",
      "url": "http://localhost:8002/sse"
    },
    "tesseract": {
      "type": "sse",
      "url": "http://localhost:8003/sse"
    }
  }
}
```

Riavvia Cursor. I 4 server MCP appariranno come tool disponibili per l'agente.

> **Importante:** il tipo di connessione e' `sse` (Server-Sent Events), non `stdio`. Le porte sono 8000, 8001, 8002, 8003.

## Checklist di verifica

Prima di passare al primo flusso, assicurati che:

- [ ] `docker compose ps` mostra 7 container `Up` (piu' eventualmente uno `Exited` che e' l'init di Wiki.js)
- [ ] I 5 curl di verifica rispondono tutti (vedi sopra)
- [ ] In Cursor, i 4 server compaiono nella lista MCP (puoi verificarlo con un agente: "quanti tool MCP hai a disposizione?")
- [ ] La Wiki.js UI e' raggiungibile su `http://localhost:3000`

---

*Approfondisci in: [doc_v3/guides/quickstart.md](../doc_v3/guides/quickstart.md) · [doc_v3/guides/multi-mcp-setup.md](../doc_v3/guides/multi-mcp-setup.md)*

*Precedente: [02 — Architettura](02-architettura.md) · Prossimo: [04 — Primo flusso](04-primo-flusso.md) · Torna all'[indice](index.md)*
