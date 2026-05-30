#!/usr/bin/env python3
"""Index wiki pages into Qdrant wiki_pages collection."""
import asyncio
import json
import sys

sys.path.insert(0, "/app")

from wiki_mcp_server.tools_pages import wikijs_bulk_get_pages


async def main() -> None:
    from qdrant_mcp.tools import qdrant_upsert_chunks

    page_ids = list(range(1, 15))  # hub + children + log/index if created
    raw = json.loads(await wikijs_bulk_get_pages(page_ids, include_content=True))
    pages = raw.get("pages", raw.get("results", []))
    if isinstance(pages, dict):
        pages = list(pages.values())

    chunks = []
    for p in pages:
        if not p or p.get("error"):
            continue
        pid = p.get("id") or p.get("pageId")
        title = p.get("title", "")
        path = p.get("path", "")
        content = (p.get("content") or "")[:8000]
        text = f"{title}\n\n{content}"
        if not text.strip():
            continue
        chunks.append({
            "id": f"wiki-{pid}-0",
            "text": text,
            "payload": {
                "page_id": int(pid),
                "title": title,
                "path": path,
                "locale": "en",
                "text": text[:1500],
            },
        })

    if not chunks:
        print("no pages to index")
        return

    r = json.loads(qdrant_upsert_chunks("wiki_pages", chunks))
    print(json.dumps({"indexed": len(chunks), "result": r}))


if __name__ == "__main__":
    asyncio.run(main())
