# Import / Export Markdown

Wiki pages can be exported to and imported from local markdown files, enabling offline editing in Obsidian, VS Code, or any markdown editor. The export format uses YAML frontmatter to preserve metadata.

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `wikijs_export_wiki` | `(output_dir, include_frontmatter=True)` | Export all wiki pages as `.md` files |
| `wikijs_export_page` | `(page_id, output_path="", include_frontmatter=True)` | Export a single page |
| `wikijs_import_page` | `(file_path, target_path="", parent_id="", update_existing=True)` | Import a single `.md` file |
| `wikijs_import_directory` | `(dir_path, base_parent_path="", update_existing=True)` | Import all `.md` files recursively |

## Format Specification

Each exported `.md` file consists of YAML frontmatter followed by the page body:

```
---
title: Getting Started with React
wiki_path: tech/frontend/react
tags: [react, frontend, tutorial]
created: 2026-05-20T10:00:00Z
updated: 2026-05-23T12:00:00Z
---

React is a JavaScript library for building user interfaces.
```

### Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Page display title |
| `wiki_path` | string | Yes | Wiki hierarchy path (e.g. `tech/frontend/react`) |
| `tags` | list | No | Tags assigned to the page |
| `created` | datetime | No | ISO 8601 creation timestamp |
| `updated` | datetime | No | ISO 8601 modification timestamp |

### Body Format

- **Standard markdown only**: tables, lists, code fences, headings, links
- **Link format**: Use absolute wiki paths: `[text](/path/to/page)`
- **No proprietary syntax**: Avoid `:::` callouts, `[toc]`, wiki.js-specific directives
- **Tags in frontmatter**: Do not place `#tag` hashtags in the markdown body

## Hierarchy Mapping

### Export: wiki paths -> directory structure

| Wiki path | File path |
|-----------|-----------|
| `tech` | `tech.md` |
| `tech/frontend` | `tech/frontend.md` |
| `tech/frontend/react` | `tech/frontend/react.md` |

### Import: directory structure -> wiki paths

A file at `tech/frontend/react.md` is imported to wiki path `tech/frontend/react`. Use `base_parent_path` to prefix all imported paths.

## Human Workflow

> **Important:** The export/import tools operate on the container filesystem. The `output_dir` and `file_path` parameters are paths **inside the Docker container**, not on your host machine. Use `docker compose cp` to move files between host and container.

**Export → Edit → Import cycle:**

```bash
# 1. Export the wiki (agent runs this in Cursor):
# wikijs_export_wiki("/data/shared/my-export")

# 2. Extract exported files to your host
docker compose cp wiki-js-mcp:/data/shared/my-export ./my-export

# 3. Edit files locally in Obsidian, VS Code, or any editor

# 4. Load edited files back into the container
docker compose cp ./my-export wiki-js-mcp:/data/shared/my-export

# 5. Import changes (agent runs this in Cursor):
# wikijs_import_directory("/data/shared/my-export", update_existing=True)
```

## Agent Workflow

> **Important:** The agent can call the export/import tools directly, but it cannot copy files between host and container. You (the human) must handle the `docker compose cp` steps.

**Safety checkpoint before batch changes:**

```bash
# 1. Agent exports (in Cursor):
# wikijs_export_wiki("/data/shared/backup-2026-05-23")

# 2. Human extracts to host for safekeeping:
docker compose cp wiki-js-mcp:/data/shared/backup-2026-05-23 ./backup-2026-05-23

# 3. Agent performs batch edits on wiki pages (in Cursor)
# wikijs_update_page(...)  -- batch changes

# 4. If something goes wrong, human can restore from backup:
docker compose cp ./backup-2026-05-23 wiki-js-mcp:/data/shared/restore
# Agent re-imports:
# wikijs_import_directory("/data/shared/restore", update_existing=True)
```

Always use `update_existing=True` for re-imports to update existing pages rather than creating duplicates.

## Alternative: Use Shared Volume Directly

Instead of `docker compose cp`, you can bind-mount a host directory. Create `docker-compose.override.yml`:

```yaml
services:
  wiki-js-mcp:
    volumes:
      - ./wiki-exports:/data/shared:rw
```

Then the agent can export to `/data/shared/` and the files appear directly in `./wiki-exports/` on your host. No `docker compose cp` needed.

## Common Pitfalls

### Nested frontmatter delimiters

If page body contains `---`, use `* * *` for horizontal rules instead.

### Link format

All internal links must use absolute paths: `[text](/path/to/page)`, not relative paths like `[text](../page)`.

Incorrect: `[React Hooks](../react/hooks)`
Correct: `[React Hooks](/tech/frontend/react/hooks)`

### Tag placement

Tags belong in YAML frontmatter, not in the markdown body. Body-level `#tags` are not recognized as wiki tags.

### File extension

Only `.md` files are processed. Files with `.txt`, `.markdown`, `.mdown` extensions are ignored during directory import.
