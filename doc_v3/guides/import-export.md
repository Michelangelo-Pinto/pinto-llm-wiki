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

```python
# 1. Export the wiki
wikijs_export_wiki("./my-export")

# 2. Edit files in Obsidian, VS Code, or any editor

# 3. Import changes
wikijs_import_directory("./my-export")
```

## Agent Workflow

```python
# 1. Export before batch changes (safety checkpoint)
wikijs_export_wiki("./backup-2026-05-23")

# 2. Perform batch edits on the exported files

# 3. Re-import
wikijs_import_directory("./backup-2026-05-23", update_existing=True)
```

Always use `update_existing=True` for re-imports to update existing pages rather than creating duplicates.

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
