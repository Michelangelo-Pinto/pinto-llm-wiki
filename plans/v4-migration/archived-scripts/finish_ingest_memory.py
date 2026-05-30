#!/usr/bin/env python3
"""Finalize PROGETTO_AUTOLEGAL ingest: export pages, log, index."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")
from wiki_mcp_server.tools_pages import (
    wikijs_append_to_page,
    wikijs_bulk_get_pages,
    wikijs_update_page,
)


async def main() -> None:
    ids = list(range(1, 14))
    bulk = json.loads(await wikijs_bulk_get_pages(ids, include_content=True))
    Path("/data/pages_bulk.json").write_text(json.dumps(bulk))
    print("exported", bulk.get("returned"), "failed", bulk.get("failed_ids"))

    log_line = "## [2026-05-29] document-processing | PROGETTO_AUTOLEGAL: 99 file Qdrant, 11 pagine wiki + hub"
    print("append", await wikijs_append_to_page(12, log_line))

    index_body = """# Index

Catalogo pagine per categoria.

## progetto-autolegal

- [/progetto-autolegal](/progetto-autolegal) — Hub PROGETTO AUTOLEGAL
- [/progetto-autolegal/pst-watchlist](/progetto-autolegal/pst-watchlist) — Watchlist PST
- [/progetto-autolegal/servizi-web-esposti](/progetto-autolegal/servizi-web-esposti)
- [/progetto-autolegal/certificati-di-cifratura](/progetto-autolegal/certificati-di-cifratura)
- [/progetto-autolegal/certificati-proxy-pda-e-pst](/progetto-autolegal/certificati-proxy-pda-e-pst)
- [/progetto-autolegal/iscrizione-pda](/progetto-autolegal/iscrizione-pda)
- [/progetto-autolegal/test-servizi-telematici-esterni](/progetto-autolegal/test-servizi-telematici-esterni)
- [/progetto-autolegal/documentazione-servizi-web-v1-69](/progetto-autolegal/documentazione-servizi-web-v1-69)
- [/progetto-autolegal/pct-test-esterni-v10](/progetto-autolegal/pct-test-esterni-v10)
- [/progetto-autolegal/indice-certificati](/progetto-autolegal/indice-certificati)
- [/progetto-autolegal/wsdl-catalog-indice](/progetto-autolegal/wsdl-catalog-indice)

## Operativo

- [/log](/log) — Log append-only
"""
    print("index", await wikijs_update_page(13, content=index_body))


if __name__ == "__main__":
    asyncio.run(main())
