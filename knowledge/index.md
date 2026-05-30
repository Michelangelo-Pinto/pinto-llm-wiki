---
title: "Knowledge Base Index"
description: "Master index of the v4 file-system knowledge base"
created: "2026-05-30"
updated: "2026-05-30"
---

# Knowledge Base

Mappa delle categorie e scope. Ogni sottodirectory contiene un `index.md` con l'elenco completo delle pagine.

## Categorie

### Software Engineering
- **Scope**: Architettura software, design pattern, linguaggi di programmazione, best practice
- **Path**: [software-engineering/](software-engineering/index.md)
- **Qdrant collection**: `documents`, filter `category=software-engineering`

### Data Science
- **Scope**: Machine learning, statistica, data engineering, AI
- **Path**: [data-science/](data-science/index.md)
- **Qdrant collection**: `documents`, filter `category=data-science`

### Operations
- **Scope**: DevOps, monitoring, infrastructure, SRE
- **Path**: [operations/](operations/index.md)
- **Qdrant collection**: `documents`, filter `category=operations`

### Ingested
- **Scope**: Contenuti ingeriti da fonti esterne (web, PDF, OCR)
- **Path**: [ingested/](ingested/index.md)
- **Qdrant collection**: `documents`, filter `category=ingested`

## Come usare questa knowledge base

1. **Ricerca semantica**: `qdrant_search(collection="documents", query_text="...")` per trovare contenuti per similarità
2. **Ricerca keyword**: `Grep` nella directory `knowledge/` per match esatti
3. **Navigazione**: Segui i link negli `index.md` di ogni categoria
4. **Nuovo contenuto**: Crea file `.md` nella categoria appropriata, aggiorna l'`index.md` corrispondente
