#!/usr/bin/env python3
"""Create PROGETTO_AUTOLEGAL wiki pages (run inside wikijs_mcp container)."""
import asyncio
import json
import os
import subprocess
from datetime import date
from pathlib import Path

SRC = Path(os.environ.get("INGEST_SRC", "/data/import-autolegal"))
TODAY = date.today().isoformat()

FRONTMATTER = """---
source_type: file
source_file: "{source_file}"
source_name: "{source_name}"
fetched_at: "{today}"
tags: [autolegal, pst, processo-telematico]
---

"""


def fm(source_file: str, source_name: str) -> str:
    return FRONTMATTER.format(source_file=source_file, source_name=source_name, today=TODAY)


async def main() -> None:
    import sys
    sys.path.insert(0, "/app")
    from wiki_mcp_server.tools_pages import wikijs_create_page
    from wiki_mcp_server.tools_hierarchy import wikijs_create_nested_page

    pdf_summaries_path = Path(os.environ.get("PDF_SUMMARIES", "/data/pdf_summaries.json"))
    pdf_summaries = json.loads(pdf_summaries_path.read_text()) if pdf_summaries_path.exists() else {}

    created = []

    # Hub
    hub = f"""{fm("to_ingest/PROGETTO_AUTOLEGAL/", "PROGETTO AUTOLEGAL — Hub")}
# PROGETTO AUTOLEGAL

Knowledge base per documentazione **Processo Telematico / PST** (Ministero della Giustizia): servizi web, catalogo WSDL, certificati, test esterni.

## Contenuto ingerito

| Categoria | File | Note |
|-----------|------|------|
| Markdown | 7 | Pagine wiki sotto questa gerarchia |
| PDF | 2 | Sintesi + testo completo in Qdrant |
| WSDL/XML/XSD | 91 | Indicizzati in Qdrant (`documents`) |
| Certificati `.cer` | 7 | Indice metadati (no binari in wiki) |

## Sotto-pagine

- [/progetto-autolegal/watchlist](/progetto-autolegal/watchlist) — link ufficiali e monitoraggio
- [/progetto-autolegal/servizi-web-esposti](/progetto-autolegal/servizi-web-esposti)
- [/progetto-autolegal/certificati-cifratura](/progetto-autolegal/certificati-cifratura)
- [/progetto-autolegal/certificati-proxy-pda-pst](/progetto-autolegal/certificati-proxy-pda-pst)
- [/progetto-autolegal/iscrizione-pda](/progetto-autolegal/iscrizione-pda)
- [/progetto-autolegal/test-esterni](/progetto-autolegal/test-esterni)
- [/progetto-autolegal/documentazione-servizi-web-v1-69](/progetto-autolegal/documentazione-servizi-web-v1-69)
- [/progetto-autolegal/pct-test-esterni-v10](/progetto-autolegal/pct-test-esterni-v10)
- [/progetto-autolegal/certificati-indice](/progetto-autolegal/certificati-indice)
- [/progetto-autolegal/wsdl-catalog-indice](/progetto-autolegal/wsdl-catalog-indice)

## Fonti PST

- [Documentazione servizi web v1.69](https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571)
- [PDF servizi web](https://pst.giustizia.it/PST/resources/cms/documents/Documentazione_servizi_web_v1.69.pdf)

* * *
Ricerca semantica su file tecnici: collezione Qdrant `documents` (ingest da `/data/shared/PROGETTO_AUTOLEGAL`).
"""
    r = json.loads(await wikijs_create_page("PROGETTO AUTOLEGAL", hub))
    if "error" in r:
        print("hub error", r)
    else:
        created.append(("hub", r.get("pageId"), r.get("path", "progetto-autolegal")))

    md_pages = [
        ("watchlist", "PST Watchlist", "pst_documentation_watchlist.md", "PST Documentation Watchlist"),
        ("servizi-web-esposti", "Servizi web esposti", "servizi_web_esposti.md", "Documentazione servizi web esposti"),
        ("certificati-cifratura", "Certificati di cifratura", "Certificati_di_cifratura.md", "Certificati di cifratura"),
        ("certificati-proxy-pda-pst", "Certificati proxy PdA e PST", "Certificati_proxy_PdA_e_PST.md", "Certificati proxy PdA e PST"),
        ("iscrizione-pda", "Iscrizione PdA", "iscrizione _pda.md", "Iscrizione PdA"),
        ("test-esterni", "Test servizi telematici esterni", "test_dei_servizi_telematici_da_parte_di_enti_o_società_esterne.md", "Test servizi telematici esterni"),
    ]

    for slug_hint, title, filename, source_name in md_pages:
        path = SRC / filename
        if not path.exists():
            print("missing", path)
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        content = fm(f"to_ingest/PROGETTO_AUTOLEGAL/{filename}", source_name) + body
        r = json.loads(await wikijs_create_nested_page(title, content, "progetto-autolegal"))
        created.append((slug_hint, r.get("pageId"), r.get("full_path")))
        print("md", slug_hint, r)

    # PDF summaries from Qdrant chunks
    pdf_specs = [
        ("documentazione-servizi-web-v1-69", "Documentazione servizi web v1.69", "Documentazione_servizi_web_v1.69.pdf", "servizi"),
        ("pct-test-esterni-v10", "PCT Test esterni v10", "PCT_Test_esterni_v10.0_a.pdf", "pct"),
    ]
    for slug, title, pdf_file, summary_key in pdf_specs:
        raw_bullets = pdf_summaries.get(summary_key, [])
        bullets = [f"- {t}…" for t in raw_bullets]
        summary_body = "\n".join(bullets[:10]) if bullets else "_Nessun chunk trovato; consultare il PDF in Qdrant._"
        content = fm(f"to_ingest/PROGETTO_AUTOLEGAL/{pdf_file}", title) + f"""# {title}

Sintesi estratta dai chunk indicizzati in Qdrant (`documents`).

**File sorgente:** `{pdf_file}`

## Punti salienti

{summary_body}

* * *
Per il testo completo usare `ingest_search_chunks` o la ricerca semantica sulla collezione `documents`.
"""
        r = json.loads(await wikijs_create_nested_page(title, content, "progetto-autolegal"))
        created.append((slug, r.get("pageId"), r.get("full_path")))
        print("pdf", slug, r)

    # Certificates index
    cer_rows = []
    cer_root = SRC
    for cer in sorted(cer_root.rglob("*.cer")):
        rel = f"to_ingest/PROGETTO_AUTOLEGAL/{cer.relative_to(cer_root)}"
        try:
            out = subprocess.check_output(
                ["openssl", "x509", "-in", str(cer), "-noout", "-subject", "-issuer", "-dates"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip().replace("\n", " | ")
        except Exception as e:
            out = str(e)
        cer_rows.append(f"| `{cer.name}` | `{rel}` | {out} |")

    cer_content = fm("to_ingest/PROGETTO_AUTOLEGAL/", "Indice certificati") + f"""# Indice certificati

Metadati estratti con OpenSSL. I file `.cer` non sono caricati in wiki (solo riferimento).

| File | Percorso sorgente | Subject / Issuer / Validità |
|------|-------------------|------------------------------|
{chr(10).join(cer_rows)}
"""
    r = json.loads(await wikijs_create_nested_page("Indice certificati", cer_content, "progetto-autolegal"))
    created.append(("certificati-indice", r.get("pageId"), r.get("full_path")))
    print("cer", r)

    # WSDL catalog index
    catalog_root = SRC / "A1_WSDL_CATALOG_v1.52b(1)" / "A1_WSDL_CATALOG_v1.52"
    wsdl_count = len(list(catalog_root.rglob("*.wsdl"))) if catalog_root.exists() else 0
    xml_count = len(list(catalog_root.rglob("*.xml"))) if catalog_root.exists() else 0
    xsd_count = len(list(catalog_root.rglob("*.xsd"))) if catalog_root.exists() else 0
    areas = []
    if catalog_root.exists():
        for sub in ["WSDL", "Catalog", "YAML"]:
            p = catalog_root / sub
            if p.is_dir():
                areas.append(f"- **{sub}/** — {sum(1 for _ in p.rglob('*') if _.is_file())} file")
        for area in ["SICID", "SIECIC", "SIGP", "CASSCI", "CASSPE"]:
            n = len(list(catalog_root.rglob(f"*{area}*")))
            if n:
                areas.append(f"- Area **{area}**: ~{n} riferimenti nel tree")

    wsdl_content = fm("to_ingest/PROGETTO_AUTOLEGAL/A1_WSDL_CATALOG_v1.52b(1)/", "WSDL Catalog v1.52") + f"""# WSDL Catalog — indice

Catalogo tecnico **A1_WSDL_CATALOG v1.52** (estratto da ZIP PST).

## Conteggi

| Tipo | N |
|------|---|
| WSDL | {wsdl_count} |
| XML (catalog) | {xml_count} |
| XSD | {xsd_count} |

## Struttura principale

{chr(10).join(areas)}

## Ricerca

Il contenuto testuale di ogni file è in Qdrant (`documents`). Esempio: cercare `fascicolo informatico SICID` via `ingest_search_chunks` o `wikijs_smart_query`.

## Path deposito

`A1_WSDL_CATALOG_v1.52b(1)/A1_WSDL_CATALOG_v1.52/` — WSDL, Catalog, YAML.
"""
    r = json.loads(await wikijs_create_nested_page("WSDL Catalog indice", wsdl_content, "progetto-autolegal"))
    created.append(("wsdl-catalog-indice", r.get("pageId"), r.get("full_path")))
    print("wsdl", r)

    print("CREATED_JSON", json.dumps(created, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
