#!/usr/bin/env python3
"""Seed Wiki.js documentation pages for wiki-js-mcp project."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

API_URL = os.environ.get("WIKIJS_API_URL", "http://localhost:3000").rstrip("/")
USERNAME = os.environ.get("WIKIJS_USERNAME", "admin@example.com")
PASSWORD = os.environ.get("WIKIJS_PASSWORD", "admin123")

TOOL_CATALOG = [
    ("wikijs_create_page", "tools_pages", "pages", "tools-page-management", "title, content, space_id?, parent_id?"),
    ("wikijs_update_page", "tools_pages", "pages", "tools-page-management", "page_id, title?, content?"),
    ("wikijs_get_page", "tools_pages", "pages", "tools-page-management", "page_id? | slug?"),
    ("wikijs_search_pages", "tools_pages", "pages", "tools-page-management", "query, space_id?"),
    ("wikijs_list_spaces", "tools_pages", "pages", "tools-page-management", "(none)"),
    ("wikijs_create_space", "tools_pages", "pages", "tools-page-management", "name, description?"),
    ("wikijs_create_repo_structure", "tools_hierarchy", "hierarchy", "tools-hierarchy", "repo_name, description?, sections?"),
    ("wikijs_create_nested_page", "tools_hierarchy", "hierarchy", "tools-hierarchy", "title, content, parent_path"),
    ("wikijs_get_page_children", "tools_hierarchy", "hierarchy", "tools-hierarchy", "page_id? | page_path?"),
    ("wikijs_create_documentation_hierarchy", "tools_hierarchy", "hierarchy", "tools-hierarchy", "project_name, file_mappings"),
    ("wikijs_link_file_to_page", "tools_files", "files", "tools-file-integration", "file_path, page_id, relationship?"),
    ("wikijs_sync_file_docs", "tools_files", "files", "tools-file-integration", "file_path, change_summary, snippet?"),
    ("wikijs_generate_file_overview", "tools_files", "files", "tools-file-integration", "file_path, include_*, target_page_id?"),
    ("wikijs_bulk_update_project_docs", "tools_files", "files", "tools-file-integration", "summary, affected_files, context"),
    ("wikijs_delete_page", "tools_deletion", "deletion", "tools-deletion", "page_id? | page_path?"),
    ("wikijs_batch_delete_pages", "tools_deletion", "deletion", "tools-deletion", "ids/paths/pattern, confirm_deletion"),
    ("wikijs_delete_hierarchy", "tools_deletion", "deletion", "tools-deletion", "root_path, delete_mode?, confirm_deletion"),
    ("wikijs_cleanup_orphaned_mappings", "tools_deletion", "deletion", "tools-deletion", "(none)"),
    ("wikijs_manage_collections", "tools_system", "system", "tools-system", "collection_name, description?, space_ids?"),
    ("wikijs_connection_status", "tools_system", "system", "tools-system", "(none)"),
    ("wikijs_repository_context", "tools_system", "system", "tools-system", "(none)"),
]

SITE_MAP = [
    ("Documentation Index", "docs/index", "index", "Central hub for all technical documentation"),
    ("Project Overview", "docs/overview", "guide", "What wiki-js-mcp is and who it is for"),
    ("Architecture", "docs/architecture", "reference", "System components and data flows"),
    ("Glossary", "docs/glossary", "reference", "Terms: MCP, SSE, GraphQL, mappings"),
    ("MCP Server", "docs/mcp-server", "index", "Hub for MCP server internals"),
    ("MCP Tool Catalog", "docs/mcp-server/tool-catalog", "tool-catalog", "All 21 MCP tools with links"),
    ("Server Entry Point", "docs/mcp-server/server-entry-point", "reference", "FastMCP bootstrap and transport"),
    ("GraphQL Client", "docs/mcp-server/graphql-client", "reference", "Wiki.js API client and auth"),
    ("Configuration", "docs/mcp-server/configuration", "reference", "Environment variables and settings"),
    ("Database Layer", "docs/mcp-server/database-layer", "reference", "SQLite file-to-page mappings"),
    ("Tool - Page Management", "docs/mcp-server/tools-page-management", "reference", "CRUD and search tools"),
    ("Tool - Hierarchy", "docs/mcp-server/tools-hierarchy", "reference", "Nested pages and repo structures"),
    ("Tool - File Integration", "docs/mcp-server/tools-file-integration", "reference", "Link code files to wiki pages"),
    ("Tool - Deletion", "docs/mcp-server/tools-deletion", "reference", "Safe page and hierarchy deletion"),
    ("Tool - System", "docs/mcp-server/tools-system", "reference", "Connection status and repository context"),
    ("Docker Deployment", "docs/docker-deployment", "guide", "Full stack with docker compose"),
    ("Development Guide", "docs/development-guide", "guide", "Local setup, testing, contributing"),
]


def meta(
    path: str,
    page_type: str,
    tags: list[str],
    sources: str,
    related: list[str],
    prerequisites: list[str] | None = None,
) -> str:
    rel = ", ".join(f"`{r}`" for r in related) if related else "(none)"
    pre = ", ".join(f"`{p}`" for p in (prerequisites or [])) if prerequisites else "(none)"
    tag_str = ", ".join(tags)
    return f"""> **Agent metadata**
> - path: `{path}`
> - type: {page_type}
> - tags: {tag_str}
> - sources: {sources}
> - related: {rel}
> - prerequisites: {pre}
"""


def see_also(links: list[tuple[str, str]]) -> str:
    lines = ["## Vedi anche", ""]
    for title, path in links:
        lines.append(f"- [{title}]({path})")
    return "\n".join(lines) + "\n"


def tool_table_rows() -> str:
    rows = []
    for tool, module, cat, doc_slug, params in TOOL_CATALOG:
        label = doc_slug.replace("tools-", "").replace("-", " ").title()
        rows.append(
            f"| `{tool}` | {module} | {cat} | {params} | "
            f"[{label}](/docs/mcp-server/{doc_slug}) |"
        )
    return "\n".join(rows)


def site_map_table() -> str:
    rows = []
    for title, path, ptype, desc in SITE_MAP:
        rows.append(f"| [{title}]({path}) | `{path}` | {ptype} | {desc} |")
    return "\n".join(rows)


def build_pages() -> list[dict[str, Any]]:
    catalog_table = tool_table_rows()
    smap = site_map_table()

    pages: list[dict[str, Any]] = [
        {
            "path": "docs/index",
            "title": "Documentation Index",
            "tags": ["docs", "index", "mcp", "navigation"],
            "content": f"""{meta("docs/index", "index", ["docs", "index", "navigation"], "mcp-servers/wiki-js-mcp/scripts/seed_wiki_docs.py", ["home", "docs/overview"], [])}

## In questa pagina

Indice centrale della documentazione tecnica **wiki-js-mcp**. Punto di partenza per umani e agenti.

## Indice locale

- [Mappa del sito](#mappa-del-sito)
- [Percorso consigliato (umano)](#percorso-consigliato-umano)
- [Percorso consigliato (agent)](#percorso-consigliato-agent)
- [Cerca in questo wiki](#cerca-in-questo-wiki)

## Mappa del sito

| Pagina | Path | Tipo | Descrizione |
|--------|------|------|-------------|
| [Home](/home) | `home` | hub | Pagina principale del wiki |
{smap}

## Percorso consigliato (umano)

1. [Project Overview](/docs/overview) — capire il progetto
2. [Architecture](/docs/architecture) — componenti e flussi
3. [MCP Server](/docs/mcp-server) — server MCP in dettaglio
4. [Docker Deployment](/docs/docker-deployment) — deploy con Docker
5. [Development Guide](/docs/development-guide) — sviluppo locale

## Percorso consigliato (agent)

1. [Configuration](/docs/mcp-server/configuration) — variabili d'ambiente e auth
2. [MCP Tool Catalog](/docs/mcp-server/tool-catalog) — elenco tool con parametri
3. Pagina tool specifica (es. [Page Management](/docs/mcp-server/tools-page-management))
4. [GraphQL Client](/docs/mcp-server/graphql-client) — per errori API

## Cerca in questo wiki

Keyword utili per `wikijs_search_pages`:

- `mcp`, `graphql`, `docker`, `tool`, `hierarchy`, `deletion`, `configuration`

{see_also([("Home", "/home"), ("MCP Server", "/docs/mcp-server"), ("Glossary", "/docs/glossary")])}

## Riferimenti codice

- Repository: `wiki-js-mcp/`
- README: `README.md`
""",
        },
        {
            "path": "docs/overview",
            "title": "Project Overview",
            "tags": ["overview", "mcp", "wikijs"],
            "content": f"""{meta("docs/overview", "guide", ["overview", "mcp", "wikijs"], "README.md", ["docs/index", "docs/architecture"], ["docs/index"])}

## In questa pagina

Panoramica del progetto **wiki-js-mcp**: MCP server per integrare Wiki.js con agenti AI (Cursor).

## Indice locale

- [Cos'è wiki-js-mcp](#cosè-wiki-js-mcp)
- [Componenti principali](#componenti-principali)
- [Casi d'uso](#casi-duso)

## Cos'è wiki-js-mcp

**wiki-js-mcp** espone Wiki.js tramite il **Model Context Protocol (MCP)**. Gli agenti possono creare, aggiornare, cercare e organizzare pagine wiki in modo programmatico, con supporto per gerarchie, mapping file→pagina e operazioni batch.

## Componenti principali

| Componente | Ruolo |
|------------|-------|
| Wiki.js | Wiki self-hosted (GraphQL API) |
| PostgreSQL | Database Wiki.js |
| MCP Server | FastMCP + 21 tool, trasporto SSE |
| SQLite locale | Mapping file sorgente ↔ pagine wiki |

## Casi d'uso

- Documentazione documentation-first con Cursor
- Sync automatica codice → wiki (`wikijs_sync_file_docs`)
- Strutture gerarchiche per repo multipli (`wikijs_create_repo_structure`)
- Deploy stack completo con Docker Compose

{see_also([("Documentation Index", "/docs/index"), ("Architecture", "/docs/architecture"), ("MCP Server", "/docs/mcp-server")])}

## Riferimenti codice

- `README.md`
- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/`
""",
        },
        {
            "path": "docs/architecture",
            "title": "Architecture",
            "tags": ["architecture", "mcp", "graphql", "docker"],
            "content": f"""{meta("docs/architecture", "reference", ["architecture", "graphql", "sse"], "docker-compose.yml, mcp-servers/wiki-js-mcp/src/", ["docs/mcp-server", "docs/docker-deployment"], ["docs/overview"])}

## In questa pagina

Architettura del sistema: come Cursor, MCP Server, Wiki.js e PostgreSQL interagiscono.

## Indice locale

- [Diagramma](#diagramma)
- [Flusso richiesta](#flusso-richiesta)
- [Moduli MCP](#moduli-mcp)

## Diagramma

```mermaid
flowchart LR
  Cursor[Cursor IDE]
  MCP[MCP Server SSE :8000]
  Wiki[Wiki.js :3000]
  PG[(PostgreSQL)]
  SQLite[(SQLite mappings)]
  Cursor -->|MCP tools| MCP
  MCP -->|GraphQL| Wiki
  MCP --> SQLite
  Wiki --> PG
```

## Flusso richiesta

1. Cursor invoca un tool MCP (es. `wikijs_create_page`) via SSE `http://localhost:8000/sse`
2. Il server autentica su Wiki.js (JWT da username/password o token)
3. Il tool esegue mutation/query GraphQL
4. Risposta JSON al client MCP

## Moduli MCP

| Modulo | File | Responsabilità |
|--------|------|----------------|
| Entry | `server.py` | FastMCP, registrazione tool, SSE/stdio |
| Client | `client.py` | HTTP GraphQL, login, retry |
| Config | `config.py` | Settings da env |
| DB | `db.py` | SQLAlchemy mappings |
| Tools | `tools_*.py` | 21 tool MCP |

{see_also([("MCP Server", "/docs/mcp-server"), ("Docker Deployment", "/docs/docker-deployment"), ("GraphQL Client", "/docs/mcp-server/graphql-client")])}

## Riferimenti codice

- `docker-compose.yml`
- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/server.py`
- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/client.py`
""",
        },
        {
            "path": "docs/glossary",
            "title": "Glossary",
            "tags": ["glossary", "mcp", "terms"],
            "content": f"""{meta("docs/glossary", "reference", ["glossary", "terms"], "—", ["docs/index"], [])}

## In questa pagina

Definizioni dei termini usati in questa documentazione.

## Indice locale

- [Termini](#termini)

## Termini

| Termine | Definizione |
|---------|-------------|
| **MCP** | Model Context Protocol — protocollo per tool esposti agli LLM |
| **SSE** | Server-Sent Events — trasporto HTTP per MCP in Docker |
| **FastMCP** | Framework Python per server MCP |
| **GraphQL** | API Wiki.js per pagine, auth, search |
| **Tool** | Funzione MCP invocabile dall'agente (es. `wikijs_search_pages`) |
| **Path** | Percorso wiki stabile (es. `docs/mcp-server/tool-catalog`) |
| **File mapping** | Record SQLite che collega un file repo a una pagina wiki |
| **Locale** | Lingua pagina Wiki.js — usare `en` dopo auto-setup |

{see_also([("Documentation Index", "/docs/index"), ("MCP Tool Catalog", "/docs/mcp-server/tool-catalog")])}

## Riferimenti codice

- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/db.py` (FileMapping)
""",
        },
        {
            "path": "docs/mcp-server",
            "title": "MCP Server",
            "tags": ["mcp", "server", "fastmcp"],
            "content": f"""{meta("docs/mcp-server", "index", ["mcp", "server", "fastmcp"], "mcp-servers/wiki-js-mcp/src/wiki_mcp_server/", ["docs/mcp-server/tool-catalog", "docs/architecture"], ["docs/mcp-server/configuration"])}

## In questa pagina

Hub per la documentazione interna del **MCP Server**: moduli, flusso e link a ogni sotto-sezione.

## Indice locale

- [Architettura MCP](#architettura-mcp)
- [Moduli](#moduli)
- [Flusso tipico](#flusso-tipico)

## Architettura MCP

```mermaid
flowchart TB
  FastMCP[FastMCP server.py]
  Tools[tools_pages hierarchy files deletion system]
  Client[WikiJSClient client.py]
  WikiAPI[Wiki.js GraphQL]
  FastMCP --> Tools
  Tools --> Client
  Client --> WikiAPI
```

## Moduli

| Modulo | Documentazione |
|--------|----------------|
| Server entry | [Server Entry Point](/docs/mcp-server/server-entry-point) |
| GraphQL client | [GraphQL Client](/docs/mcp-server/graphql-client) |
| Configuration | [Configuration](/docs/mcp-server/configuration) |
| Database | [Database Layer](/docs/mcp-server/database-layer) |
| **Tutti i tool** | **[MCP Tool Catalog](/docs/mcp-server/tool-catalog)** |
| Page tools | [Tool - Page Management](/docs/mcp-server/tools-page-management) |
| Hierarchy tools | [Tool - Hierarchy](/docs/mcp-server/tools-hierarchy) |
| File tools | [Tool - File Integration](/docs/mcp-server/tools-file-integration) |
| Deletion tools | [Tool - Deletion](/docs/mcp-server/tools-deletion) |
| System tools | [Tool - System](/docs/mcp-server/tools-system) |

## Flusso tipico

1. Cursor → `http://localhost:8000/sse`
2. Tool `wikijs_connection_status` per verificare auth
3. `wikijs_search_pages` o `wikijs_get_page` per leggere
4. `wikijs_create_page` / `wikijs_update_page` per scrivere

{see_also([("MCP Tool Catalog", "/docs/mcp-server/tool-catalog"), ("Architecture", "/docs/architecture"), ("Configuration", "/docs/mcp-server/configuration")])}

## Riferimenti codice

- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/server.py`
- `mcp-servers/wiki-js-mcp/Dockerfile`
""",
        },
        {
            "path": "docs/mcp-server/tool-catalog",
            "title": "MCP Tool Catalog",
            "tags": ["mcp", "tools", "catalog"],
            "content": f"""{meta("docs/mcp-server/tool-catalog", "tool-catalog", ["mcp", "tools", "catalog"], "mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_*.py", ["docs/mcp-server"], ["docs/mcp-server/configuration"])}

## In questa pagina

Catalogo completo dei **21 tool MCP** con modulo, categoria, parametri e link alla documentazione dettagliata.

## Indice locale

- [Tabella tool](#tabella-tool)
- [Categorie](#categorie)

## Tabella tool

| Tool | Modulo | Categoria | Parametri principali | Documentazione |
|------|--------|-----------|----------------------|----------------|
{catalog_table}

## Categorie

| Categoria | Tool count | Pagina |
|-----------|------------|--------|
| pages | 6 | [Page Management](/docs/mcp-server/tools-page-management) |
| hierarchy | 4 | [Hierarchy](/docs/mcp-server/tools-hierarchy) |
| files | 4 | [File Integration](/docs/mcp-server/tools-file-integration) |
| deletion | 4 | [Deletion](/docs/mcp-server/tools-deletion) |
| system | 3 | [System](/docs/mcp-server/tools-system) |

{see_also([("MCP Server", "/docs/mcp-server"), ("Configuration", "/docs/mcp-server/configuration")])}

## Riferimenti codice

- `tools_pages.py`, `tools_hierarchy.py`, `tools_files.py`, `tools_deletion.py`, `tools_system.py`
""",
        },
        {
            "path": "docs/mcp-server/server-entry-point",
            "title": "Server Entry Point",
            "tags": ["mcp", "server", "sse", "stdio"],
            "content": f"""{meta("docs/mcp-server/server-entry-point", "reference", ["server", "sse", "fastmcp"], "mcp-servers/wiki-js-mcp/src/wiki_mcp_server/server.py", ["docs/mcp-server", "docs/mcp-server/configuration"], ["docs/mcp-server"])}

## In questa pagina

Punto di ingresso del server MCP: istanza FastMCP, registrazione tool, trasporto SSE o stdio.

## Indice locale

- [Bootstrap](#bootstrap)
- [Trasporti](#trasporti)

## Bootstrap

Il file `server.py` crea `mcp = FastMCP("Wiki.js Integration")` e importa i moduli tool per registrare i decorator `@mcp.tool()`.

All'avvio (`main()`):
1. `_register_tools()` importa `tools_pages`, `tools_hierarchy`, `tools_files`, `tools_deletion`, `tools_system`
2. `wikijs.authenticate()` prima di accettare connessioni
3. `mcp.run()` con transport da `MCP_TRANSPORT`

## Trasporti

| Valore | Uso |
|--------|-----|
| `sse` | Docker / Cursor via URL `http://host:8000/sse` |
| `stdio` | Sviluppo locale con script `start-server.sh` |

Variabili: `MCP_HOST`, `MCP_PORT` (default `0.0.0.0:8000`).

{see_also([("Configuration", "/docs/mcp-server/configuration"), ("GraphQL Client", "/docs/mcp-server/graphql-client"), ("Docker Deployment", "/docs/docker-deployment")])}

## Riferimenti codice

- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/server.py`
- `mcp-servers/wiki-js-mcp/docker-entrypoint.sh`
""",
        },
        {
            "path": "docs/mcp-server/graphql-client",
            "title": "GraphQL Client",
            "tags": ["graphql", "client", "auth", "jwt"],
            "content": f"""{meta("docs/mcp-server/graphql-client", "reference", ["graphql", "client", "jwt"], "mcp-servers/wiki-js-mcp/src/wiki_mcp_server/client.py", ["docs/mcp-server/configuration", "docs/mcp-server/tools-page-management"], ["docs/mcp-server"])}

## In questa pagina

Client HTTP per l'API GraphQL di Wiki.js: autenticazione, retry e gestione errori.

## Indice locale

- [Autenticazione GraphQL](#autenticazione-graphql)
- [graphql_request](#graphql_request)

## Autenticazione GraphQL

Ordine di priorità:
1. `WIKIJS_TOKEN` o `WIKIJS_API_KEY` → header `Bearer`
2. `WIKIJS_USERNAME` + `WIKIJS_PASSWORD` → mutation `authentication.login` con `strategy: "local"`

Wiki.js 2.5 richiede `responseResult.succeeded` nella risposta login.

## graphql_request

- URL: `{{WIKIJS_API_URL}}/graphql`
- Retry: 3 tentativi con backoff esponenziale (tenacity)
- Errori GraphQL sollevati come eccezione con messaggio aggregato

{see_also([("Configuration", "/docs/mcp-server/configuration"), ("Tool - Page Management", "/docs/mcp-server/tools-page-management")])}

## Riferimenti codice

- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/client.py`
""",
        },
        {
            "path": "docs/mcp-server/configuration",
            "title": "Configuration",
            "tags": ["configuration", "env", "settings"],
            "content": f"""{meta("docs/mcp-server/configuration", "reference", ["configuration", "env"], "mcp-servers/wiki-js-mcp/src/wiki_mcp_server/config.py, .env.example", ["docs/mcp-server/tool-catalog", "docs/docker-deployment"], ["docs/mcp-server"])}

## In questa pagina

Variabili d'ambiente e classe `Settings` (pydantic-settings) per il MCP server.

## Indice locale

- [Variabili principali](#variabili-principali)
- [File env](#file-env)

## Variabili principali

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `WIKIJS_API_URL` | `http://localhost:3000` | Base URL Wiki.js (in Docker: `http://wiki:3000`) |
| `WIKIJS_USERNAME` | — | Email admin per login GraphQL |
| `WIKIJS_PASSWORD` | — | Password admin |
| `WIKIJS_TOKEN` | — | JWT/API token (alternativa a user/pass) |
| `WIKIJS_MCP_DB` | `./wikijs_mappings.db` | SQLite mappings |
| `MCP_TRANSPORT` | `sse` | `sse` o `stdio` |
| `MCP_HOST` | `0.0.0.0` | Bind host SSE |
| `MCP_PORT` | `8000` | Porta SSE |
| `REPOSITORY_ROOT` | `./` | Root per tool file |
| `LOG_LEVEL` | `INFO` | Logging |

## File env

- Root Docker: `.env` (postgres + wiki + mcp)
- Sviluppo MCP: `mcp-servers/wiki-js-mcp/config/example.env` → `mcp-servers/wiki-js-mcp/.env`

**Nota:** usare sempre `locale: "en"` nelle mutation pagine dopo auto-setup.

{see_also([("GraphQL Client", "/docs/mcp-server/graphql-client"), ("Docker Deployment", "/docs/docker-deployment"), ("Development Guide", "/docs/development-guide")])}

## Riferimenti codice

- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/config.py`
- `.env.example`
""",
        },
        {
            "path": "docs/mcp-server/database-layer",
            "title": "Database Layer",
            "tags": ["database", "sqlite", "mapping"],
            "content": f"""{meta("docs/mcp-server/database-layer", "reference", ["sqlite", "mapping"], "mcp-servers/wiki-js-mcp/src/wiki_mcp_server/db.py", ["docs/mcp-server/tools-file-integration", "docs/mcp-server/tools-deletion"], ["docs/mcp-server"])}

## In questa pagina

Layer SQLite per mapping file sorgente ↔ pagine Wiki.js e contesto repository.

## Indice locale

- [Modelli](#modelli)
- [Sessione DB](#sessione-db)

## Modelli

**FileMapping**
- `file_path` (unique), `page_id`, `relationship_type`, `file_hash`, `repository_root`, `space_name`

**RepositoryContext**
- `root_path`, `space_name`, `space_id`

## Sessione DB

`get_db()` restituisce sessione SQLAlchemy. Usata da tool file e deletion (`wikijs_cleanup_orphaned_mappings`).

{see_also([("Tool - File Integration", "/docs/mcp-server/tools-file-integration"), ("Tool - Deletion", "/docs/mcp-server/tools-deletion")])}

## Riferimenti codice

- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/db.py`
""",
        },
    ]

    tool_pages = [
        (
            "docs/mcp-server/tools-page-management",
            "Tool - Page Management",
            ["tools", "pages", "graphql"],
            "tools_pages.py",
            [
                ("wikijs_create_page", "title, content, space_id?, parent_id?", "Crea pagina; path da slugify o parent"),
                ("wikijs_update_page", "page_id, title?, content?", "Aggiorna titolo/contenuto"),
                ("wikijs_get_page", "page_id? | slug?", "Legge pagina per ID o path"),
                ("wikijs_search_pages", "query, space_id?", "Ricerca full-text"),
                ("wikijs_list_spaces", "—", "Elenco space"),
                ("wikijs_create_space", "name, description?", "Crea nuovo space"),
            ],
            ["docs/mcp-server/tool-catalog", "docs/mcp-server/graphql-client"],
        ),
        (
            "docs/mcp-server/tools-hierarchy",
            "Tool - Hierarchy",
            ["tools", "hierarchy", "nested"],
            "tools_hierarchy.py",
            [
                ("wikijs_create_repo_structure", "repo_name, description?, sections?", "Struttura doc per repository"),
                ("wikijs_create_nested_page", "title, content, parent_path", "Pagina sotto parent path"),
                ("wikijs_get_page_children", "page_id? | page_path?", "Figli di una pagina"),
                ("wikijs_create_documentation_hierarchy", "project_name, file_mappings", "Gerarchia da mapping file"),
            ],
            ["docs/mcp-server/tool-catalog", "docs/mcp-server/tools-page-management"],
        ),
        (
            "docs/mcp-server/tools-file-integration",
            "Tool - File Integration",
            ["tools", "files", "sync"],
            "tools_files.py",
            [
                ("wikijs_link_file_to_page", "file_path, page_id, relationship?", "Salva mapping SQLite"),
                ("wikijs_sync_file_docs", "file_path, change_summary, snippet?", "Sync doc da cambio file"),
                ("wikijs_generate_file_overview", "file_path, include_*, target_page_id?", "Overview strutturata file"),
                ("wikijs_bulk_update_project_docs", "summary, affected_files, context", "Update batch multi-file"),
            ],
            ["docs/mcp-server/database-layer", "docs/mcp-server/tool-catalog"],
        ),
        (
            "docs/mcp-server/tools-deletion",
            "Tool - Deletion",
            ["tools", "deletion", "batch"],
            "tools_deletion.py",
            [
                ("wikijs_delete_page", "page_id? | page_path?", "Elimina singola pagina"),
                ("wikijs_batch_delete_pages", "ids/paths/pattern, confirm_deletion", "Eliminazione batch"),
                ("wikijs_delete_hierarchy", "root_path, delete_mode, confirm_deletion", "Elimina albero pagine"),
                ("wikijs_cleanup_orphaned_mappings", "—", "Pulisce mapping senza pagina"),
            ],
            ["docs/mcp-server/tool-catalog", "docs/mcp-server/database-layer"],
        ),
        (
            "docs/mcp-server/tools-system",
            "Tool - System",
            ["tools", "system", "status"],
            "tools_system.py",
            [
                ("wikijs_manage_collections", "collection_name, description?, space_ids?", "Placeholder collections"),
                ("wikijs_connection_status", "—", "Stato connessione e auth"),
                ("wikijs_repository_context", "—", "Contesto repo da DB"),
            ],
            ["docs/mcp-server/tool-catalog", "docs/mcp-server/configuration"],
        ),
    ]

    for path, title, tags, source, tools, related in tool_pages:
        tool_rows = "\n".join(
            f"| `{name}` | {params} | {when} |"
            for name, params, when in tools
        )
        fixed_related = []
        for r in related:
            p = r if r.startswith("/") else f"/{r}"
            label = r.split("/")[-1].replace("-", " ").title()
            fixed_related.append((label, p))

        pages.append({
            "path": path,
            "title": title,
            "tags": tags,
            "content": f"""{meta(path, "reference", tags, f"mcp-servers/wiki-js-mcp/src/wiki_mcp_server/{source}", related, ["docs/mcp-server/configuration"])}

## In questa pagina

Documentazione dei tool MCP del modulo **{source}**.

## Indice locale

- [Tabella tool](#tabella-tool)
- [Errori comuni](#errori-comuni)

## Tabella tool

| Tool | Parametri | Quando usare |
|------|-----------|--------------|
{tool_rows}

Tutti i tool restituiscono una **stringa JSON** con esito o errore.

## Errori comuni

- **Login failed** — verificare `WIKIJS_USERNAME`/`PASSWORD` o token in [Configuration](/docs/mcp-server/configuration)
- **Locale error** — usare `locale: "en"` (non `it` dopo auto-setup)
- **Path conflict** — path wiki deve essere unico; usare `wikijs_get_page` con slug prima di creare

{see_also(fixed_related + [("MCP Tool Catalog", "/docs/mcp-server/tool-catalog")])}

## Riferimenti codice

- `mcp-servers/wiki-js-mcp/src/wiki_mcp_server/{source}`
""",
        })

    pages.extend([
        {
            "path": "docs/docker-deployment",
            "title": "Docker Deployment",
            "tags": ["docker", "compose", "deployment"],
            "content": f"""{meta("docs/docker-deployment", "guide", ["docker", "compose"], "docker-compose.yml, mcp-servers/wiki-js-mcp/Dockerfile", ["docs/architecture", "docs/mcp-server/configuration"], ["docs/overview"])}

## In questa pagina

Deploy dello stack completo: PostgreSQL, Wiki.js, auto-setup e MCP server.

## Indice locale

- [Servizi](#servizi)
- [Avvio](#avvio)
- [Cursor MCP](#cursor-mcp)

## Servizi

| Service | Immagine | Porta |
|---------|----------|-------|
| `db` | postgres:15-alpine | 5432 (interno) |
| `wiki` | ghcr.io/requarks/wiki:2 | 3000 |
| `setup` | curl (one-shot) | — |
| `wiki-js-mcp` | build `./mcp-servers/wiki-js-mcp` | 8000 |

## Avvio

```bash
cp .env.example .env
# Impostare POSTGRES_PASSWORD, WIKIJS_USERNAME, WIKIJS_PASSWORD
docker compose up -d --build
```

- Wiki.js: http://localhost:3000
- MCP SSE: http://localhost:8000/sse

Il servizio `setup` chiama `POST /finalize` per configurazione automatica admin.

## Cursor MCP

`~/.cursor/mcp.json`:
```json
{{
  "mcpServers": {{
    "wikijs": {{
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }}
  }}
}}
```

{see_also([("Architecture", "/docs/architecture"), ("Configuration", "/docs/mcp-server/configuration"), ("Development Guide", "/docs/development-guide")])}

## Riferimenti codice

- `docker-compose.yml`
- `mcp-servers/wiki-js-mcp/Dockerfile`
""",
        },
        {
            "path": "docs/development-guide",
            "title": "Development Guide",
            "tags": ["development", "testing", "local"],
            "content": f"""{meta("docs/development-guide", "guide", ["development", "testing"], "mcp-servers/wiki-js-mcp/scripts/, README.md", ["docs/docker-deployment", "docs/mcp-server"], ["docs/mcp-server/configuration"])}

## In questa pagina

Sviluppo locale del MCP server, test e struttura repository.

## Indice locale

- [Setup locale](#setup-locale)
- [Script utili](#script-utili)
- [Struttura repo](#struttura-repo)

## Setup locale

```bash
cp mcp-servers/wiki-js-mcp/config/example.env mcp-servers/wiki-js-mcp/.env
./mcp-servers/wiki-js-mcp/scripts/setup.sh
./mcp-servers/wiki-js-mcp/scripts/start-server.sh
```

Per stdio: `MCP_TRANSPORT=stdio` in `mcp-servers/wiki-js-mcp/.env`.

## Script utili

| Script | Scopo |
|--------|-------|
| `setup.sh` | Install dipendenze |
| `test-server.sh` | Test connessione |
| `start-server.sh` | Avvio server |
| `seed_wiki_docs.py` | Popola documentazione wiki |

## Struttura repo

```
wiki-js-mcp/
├── docker-compose.yml
├── mcp-servers/wiki-js-mcp/
│   ├── src/wiki_mcp_server/
│   ├── scripts/
│   └── Dockerfile
└── README.md
```

{see_also([("MCP Server", "/docs/mcp-server"), ("Docker Deployment", "/docs/docker-deployment"), ("MCP Tool Catalog", "/docs/mcp-server/tool-catalog")])}

## Riferimenti codice

- `README.md`
- `mcp-servers/wiki-js-mcp/scripts/`
""",
        },
    ])

    return pages


HOME_CONTENT = """# Wiki.js MCP — Home

Benvenuto nel wiki del progetto **wiki-js-mcp**.

## Documentazione

| Pagina | Descrizione |
|--------|-------------|
| [Documentation Index](/docs/index) | Indice completo (umano + agent) |
| [Project Overview](/docs/overview) | Panoramica progetto |
| [MCP Server](/docs/mcp-server) | Hub server MCP e 21 tool |
| [Docker Deployment](/docs/docker-deployment) | Deploy con Docker Compose |
| [Development Guide](/docs/development-guide) | Sviluppo locale |

## Accesso rapido

- Wiki: http://localhost:3000
- MCP SSE: http://localhost:8000/sse
- Credenziali default (dev): vedi `.env`

## Per agenti

Iniziare da [Documentation Index](/docs/index) → [Configuration](/docs/mcp-server/configuration) → [MCP Tool Catalog](/docs/mcp-server/tool-catalog).
"""


class WikiClient:
    def __init__(self) -> None:
        self.token: str | None = None

    def gql(self, query: str, variables: dict | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        req = urllib.request.Request(
            f"{API_URL}/graphql",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(e.read().decode()) from e
        if data.get("errors"):
            raise RuntimeError(json.dumps(data["errors"], indent=2))
        return data

    def login(self) -> None:
        data = self.gql(
            """
            mutation($u: String!, $p: String!, $s: String!) {
              authentication {
                login(username: $u, password: $p, strategy: $s) {
                  responseResult { succeeded message }
                  jwt
                }
              }
            }
            """,
            {"u": USERNAME, "p": PASSWORD, "s": "local"},
        )
        login = data["data"]["authentication"]["login"]
        if not login["responseResult"]["succeeded"]:
            raise RuntimeError(f"Login failed: {login['responseResult']['message']}")
        self.token = login["jwt"]
        print("Logged in as", USERNAME)

    def list_pages(self) -> dict[str, int]:
        data = self.gql("{ pages { list { id path title } } }")
        return {p["path"]: p["id"] for p in data["data"]["pages"]["list"]}

    def create_page(self, path: str, title: str, content: str, tags: list[str]) -> int:
        data = self.gql(
            """
            mutation($content: String!, $description: String!, $editor: String!,
                     $isPublished: Boolean!, $isPrivate: Boolean!, $locale: String!,
                     $path: String!, $tags: [String]!, $title: String!) {
              pages {
                create(content: $content, description: $description, editor: $editor,
                       isPublished: $isPublished, isPrivate: $isPrivate, locale: $locale,
                       path: $path, tags: $tags, title: $title) {
                  responseResult { succeeded message }
                  page { id path title }
                }
              }
            }
            """,
            {
                "content": content,
                "description": "",
                "editor": "markdown",
                "isPublished": True,
                "isPrivate": False,
                "locale": "en",
                "path": path,
                "tags": tags,
                "title": title,
            },
        )
        result = data["data"]["pages"]["create"]
        if not result["responseResult"]["succeeded"]:
            raise RuntimeError(result["responseResult"]["message"])
        page = result["page"]
        print(f"  CREATED {path} (id={page['id']})")
        return page["id"]

    def update_page(self, page_id: int, title: str, content: str, tags: list[str], path: str) -> None:
        data = self.gql(
            """
            mutation($id: Int!, $content: String!, $description: String!, $editor: String!,
                     $isPrivate: Boolean!, $isPublished: Boolean!, $locale: String!,
                     $path: String!, $tags: [String]!, $title: String!) {
              pages {
                update(id: $id, content: $content, description: $description, editor: $editor,
                       isPrivate: $isPrivate, isPublished: $isPublished, locale: $locale,
                       path: $path, tags: $tags, title: $title) {
                  responseResult { succeeded message }
                  page { id path }
                }
              }
            }
            """,
            {
                "id": page_id,
                "content": content,
                "description": "",
                "editor": "markdown",
                "isPrivate": False,
                "isPublished": True,
                "locale": "en",
                "path": path,
                "tags": tags,
                "title": title,
            },
        )
        result = data["data"]["pages"]["update"]
        if not result["responseResult"]["succeeded"]:
            raise RuntimeError(result["responseResult"]["message"])
        print(f"  UPDATED {path} (id={page_id})")


def main() -> int:
    client = WikiClient()
    client.login()
    existing = client.list_pages()
    pages = build_pages()
    pages.sort(key=lambda p: p["path"].count("/"))

    created = 0
    updated = 0
    for p in pages:
        path = p["path"]
        if path in existing:
            client.update_page(existing[path], p["title"], p["content"], p["tags"], path)
            updated += 1
        else:
            pid = client.create_page(path, p["title"], p["content"], p["tags"])
            existing[path] = pid
            created += 1

    home_id = existing.get("home", 6)
    client.update_page(home_id, "Home", HOME_CONTENT, ["home", "hub", "docs"], "home")
    print(f"\nDone: {created} created, {updated} updated, home refreshed")
    print(f"Index: {API_URL}/docs/index")
    return 0


if __name__ == "__main__":
    sys.exit(main())
