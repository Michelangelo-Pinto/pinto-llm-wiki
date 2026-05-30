#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")
from qdrant_mcp.tools import qdrant_upsert_chunks


def main() -> None:
    bulk = json.loads(Path("/data/pages_bulk.json").read_text())
    pages = bulk.get("results", bulk.get("pages", []))
    chunks = []
    for p in pages:
        pid = p.get("pageId") or p.get("id")
        if pid is None:
            continue
        title = p.get("title", "")
        path = p.get("path", "")
        content = (p.get("content") or "")[:8000]
        text = f"{title}\n\n{content}"
        chunks.append({
            "text": text,
            "payload": {
                "page_id": int(pid),
                "title": title,
                "path": path,
                "locale": "en",
                "text": text[:1500],
            },
        })
    r = json.loads(qdrant_upsert_chunks("wiki_pages", chunks))
    print(json.dumps({"chunks": len(chunks), "result": r}))


if __name__ == "__main__":
    main()
