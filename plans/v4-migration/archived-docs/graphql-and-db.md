# GraphQL and DB Patterns

Patterns for Wiki.js GraphQL communication and SQLite persistence in wiki-js-mcp v3.

## GraphQL query constants

Named GraphQL queries are defined as module-level `_UPPER_CASE` string constants in [`tools_pages.py`](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/tools_pages.py):

| Constant | Line | Purpose |
|----------|------|---------|
| `_GET_PAGE_BY_ID_QUERY` | 28 | Single page by ID (all fields + tags) |
| `_RESOLVE_PATH_QUERY` | 52 | Page ID from path via `singleByPath` |
| `_LIST_ALL_PAGES_WITH_TAGS_QUERY` | 62 | All pages with tags, updatedAt |

One-off queries (search, mutations) are inline strings inside tool functions.

## GraphQL call pattern

```python
response = await wikijs.graphql_request(query_string, variables_dict)
data = response.get("data", {})
result = data.get("pages", {}).get("single")  # or .create, .update, .list, .search
```

- **Safe navigation**: Chained `.get()` with empty defaults prevents KeyError
- **Variables**: Passed as `{"id": page_id}` dict, matching `$id: Int!` in query

## Parallel queries

For bulk operations, queries are fired simultaneously via `asyncio.gather`:

```python
tasks = [wikijs.graphql_request(query, {"id": pid}) for pid in unique_ids]
responses = await asyncio.gather(*tasks, return_exceptions=True)

for pid, response in zip(unique_ids, responses):
    if isinstance(response, Exception):
        errors.append({"pageId": pid, "error": str(response)})
        continue
    # Process successful response
```

- `return_exceptions=True`: Prevents one failure from crashing the entire batch
- `BULK_GET_MAX_PAGES = 50`: Hard cap per call

Used by: `wikijs_bulk_get_pages`, `_resolve_paths_to_ids`, `wikijs_rebuild_backlink_index`.

## Mutation pattern

Page create/update mutations require the full field set and return a `responseResult` wrapper:

```graphql
mutation($id: Int!, $content: String!, ...) {
  pages {
    update(...) {
      responseResult { succeeded, errorCode, slug, message }
      page { id, path, title, updatedAt }
    }
  }
}
```

All mutations return `responseResult { succeeded }`. Check `succeeded` before using the result.

## Client retry

[`client.py` line 82](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/client.py):

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def graphql_request(self, query, variables=None) -> Dict:
```

- 3 attempts, exponential backoff starting at 4s, max 10s
- Retries on HTTP errors and GraphQL errors
- Timeout: 30 seconds (httpx.AsyncClient)

## Database session lifecycle

[`db.py` line 53](../../mcp-servers/wiki-js-mcp/src/wiki_mcp_server/db.py):

```python
def get_db():
    return SessionLocal()

# Usage:
db = get_db()
try:
    rows = db.query(Model).filter(...).all()
    db.commit()           # Only for writes
except Exception as e:
    logger.warning("...")
    db.rollback()
finally:
    db.close()            # ALWAYS present
```

**Critical rules**:
- `db.close()` in `finally` — no connection leaks
- `commit()` only for writes — reads don't need commit
- `rollback()` on error — prevents partial writes
- One session per operation — no session reuse across calls

Engine config: `sqlite:///{WIKIJS_MCP_DB}`, `autocommit=False`, `autoflush=False`.

## SQLAlchemy models (v3)

| Model | Table | Purpose |
|-------|-------|---------|
| `FileMapping` | `file_mappings` | File path → page ID |
| `RepositoryContext` | `repository_contexts` | Repo root → space mapping |
| `BacklinkIndex` | `backlinks` | Cross-reference links |

**Removed in v3**: `PageVector` (vectors now in Qdrant). See [Database](../architecture/database.md).

## SQLAlchemy query patterns

| Pattern | Example |
|---------|---------|
| Filter + all | `db.query(Model).filter(Model.col == val).all()` |
| Filter + count | `db.query(Model).filter(Model.col == val).count()` |
| Filter + delete | `db.query(Model).filter(Model.col == val).delete()` |
| Group by + count | `db.query(Model.col, func.count(Model.id)).group_by(Model.col).all()` |
| Filter by list | `db.query(Model).filter(Model.col.in_([1,2,3])).all()` |
| Upsert | Query first, update if exists, else add new |

## Ingestion Pipeline DB

Ingestion Pipeline uses a separate SQLite database (`ingestion.db`) with models in [`ingestion_pipeline/db.py`](../../mcp-servers/ingestion-pipeline/src/ingestion_pipeline/db.py): `IngestedDocument`, `DocumentChunk`, `PageChunkReference`. Same session lifecycle pattern applies.
