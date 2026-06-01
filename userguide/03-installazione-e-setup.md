# 03 — Installazione e setup

Questo capitolo ti guida dallo zero al primo comando funzionante. Se qualcosa va storto, alla fine trovi una checklist di verifica.

## Prerequisiti

- **Docker** e **Docker Compose v2** installati e funzionanti
- **Git** per clonare il repository
- **Cursor IDE** (o un client MCP compatibile) per usare i tool
- Almeno **4 GB di RAM** per i 4 container

## Avvio dello stack

```bash
# 1. Clona il repository
git clone https://github.com/mikep/pinto-llm-wiki.git
cd pinto-llm-wiki

# 2. Configura le variabili d'ambiente
cp .env.example .env
# Non servono password PostgreSQL o Wiki.js in v4

# 3. Avvia lo stack (4 container)
docker compose up -d

# 4. Attendi ~60 secondi che i container completino l'health check
docker compose ps
# Dovresti vedere 4 container "healthy"

# 5. Verifica che tutto risponda
curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/sse && echo " Qdrant MCP OK"
curl -s -o /dev/null -w '%{http_code}' http://localhost:8002/sse && echo " Ingestion OK"
curl -s -o /dev/null -w '%{http_code}' http://localhost:8003/sse && echo " Tesseract OK"
```

Tutti e 3 dovrebbero rispondere con un HTTP status. Lo stack e' pronto.

## Configurare Cursor IDE

Apri (o crea) il file `mcp.json` nella root del progetto e aggiungi:

```json
{
  "mcpServers": {
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

Riavvia Cursor. I 3 server MCP appariranno come tool disponibili per l'agente.

> **Importante:** il tipo di connessione e' `sse` (Server-Sent Events), non `stdio`. Le porte sono 8001, 8002, 8003.

## Checklist di verifica

Prima di passare al primo flusso, assicurati che:

- [ ] `docker compose ps` mostra 4 container `Up` e `healthy`
- [ ] I 3 curl di verifica rispondono tutti (vedi sopra)
- [ ] In Cursor, i 3 server compaiono nella lista MCP (puoi verificarlo con un agente: "quanti tool MCP hai a disposizione?")
- [ ] La cartella `knowledge/` esiste con la sua struttura di base

---

*Approfondisci in: [doc_v4/guides/quickstart.md](../doc_v4/guides/quickstart.md) · [doc_v4/guides/stack-lifecycle.md](../doc_v4/guides/stack-lifecycle.md)*

*Precedente: [02 — Architettura](02-architettura.md) · Prossimo: [04 — Primo flusso](04-primo-flusso.md) · Torna all'[indice](index.md)*
