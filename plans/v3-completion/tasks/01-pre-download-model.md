# Task 01: Pre-download Embedding Model in Dockerfile

| Field | Value |
|-------|-------|
| Status | completed |
| Priority | P1 |
| Effort | Small |
| Depends on | none |
| Blocks | 06 (stack + regression tests benefit from clean first runs) |

## Objective

Eliminate the 5-10 second cold start delay on the first `wikijs_smart_query` or `qdrant_search` call by pre-downloading `all-MiniLM-L6-v2` during Docker image build instead of lazily at first use.

## Background

Currently, the embedding model is loaded via a lazy singleton pattern in both Qdrant MCP and Ingestion Pipeline:

```python
_embedder = None

def compute_embedding(text: str) -> list[float]:
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder.encode(text).tolist()
```

This downloads the ~80 MB model on first call at runtime. In Docker, this download happens inside the container and is not cached across rebuilds. Pre-downloading in the Dockerfile bakes the model into the image.

## Implementation Plan

1. Identify the two Dockerfiles that need modification:
   - `mcp-servers/qdrant-mcp/Dockerfile`
   - `mcp-servers/ingestion-pipeline/Dockerfile`

2. After `pip install sentence-transformers`, add a RUN command that triggers model download:

```dockerfile
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

3. Verify the model is cached in the image:

```bash
docker compose build qdrant-mcp ingestion-pipeline
docker compose run --rm qdrant-mcp python3 -c "
from sentence_transformers import SentenceTransformer
import time
t0 = time.time()
m = SentenceTransformer('all-MiniLM-L6-v2')
print(f'Loaded in {time.time() - t0:.1f}s')
"
```

4. Rebuild and test both services.

## Decisions

### 2026-05-24 — Task 01: Pre-download placement

**Decision:** Place the `RUN python3 -c "..."` command immediately after `pip install` and before `RUN useradd`, in both Dockerfiles.

**Rationale:** This ensures the model is downloaded in a separate Docker layer that can be cached independently, and the model files end up in the correct filesystem location before the non-root user is created.

## Documentation Updates

- [ ] `doc_v3/improvements/index.md` — mark "Pre-download embedding model in Dockerfile" as completed
- [ ] `doc_v3/architecture/mcp-server-registry.md` — update image notes if size changes
- [ ] `doc_v3/guides/docker-operations.md` — update first-run notes about model download

## Completion Criteria

- [ ] `qdrant-mcp` Dockerfile pre-downloads `all-MiniLM-L6-v2`
- [ ] `ingestion-pipeline` Dockerfile pre-downloads `all-MiniLM-L6-v2`
- [ ] `docker compose build` succeeds for both images
- [ ] First embedding call is sub-second (no cold start delay)
- [ ] Both services pass existing tests

## Notes

- Modified `mcp-servers/qdrant-mcp/Dockerfile` and `mcp-servers/ingestion-pipeline/Dockerfile`
- The model download adds ~80 MB to both images (was already the size when model downloaded at runtime, now pre-baked)
- No code changes needed to the lazy singleton pattern — the model is loaded from cache instantly
