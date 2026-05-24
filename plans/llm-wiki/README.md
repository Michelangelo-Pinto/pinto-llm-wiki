# LLM Wiki — MCP Server Extension Plan

## Goal

Extend the wiki-js-mcp server to fully support the **LLM Wiki pattern**: an agent-driven, incrementally maintained knowledge base where the LLM ingests sources, writes and updates wiki pages, maintains cross-references, and keeps the wiki consistent over time.

The LLM Wiki pattern defines three layers:

1. **Raw sources** — immutable source documents the LLM reads from but never modifies.
2. **The wiki** — a structured, interlinked collection of pages the LLM owns entirely.
3. **The schema** — conventions and workflows telling the LLM how to structure and maintain the wiki.

And three operations:

- **Ingest**: process a new source, write a summary, update entity/concept pages, update the index, append to the log. A single source may touch 10-15 pages.
- **Query**: search the wiki, read relevant pages, synthesize an answer. Good answers get filed back as new pages.
- **Lint**: health-check the wiki for contradictions, stale claims, orphan pages, missing cross-references.

The current MCP server (21 tools) covers basic CRUD and hierarchy, but lacks critical capabilities for discovery, ingestion workflows, and wiki maintenance at scale.

## Scale-first approach

This roadmap is designed for **scale from day one** (200+ pages). Key design decisions:

- **Metadata before content**: page stats are a P1 blocker, not a P2 nice-to-have
- **Unified dashboards**: lint tools (orphans, stale) are merged into a single `wiki_health` call
- **Search is core**: semantic/vector search is P2, not P4, powering the `smart_query` tool
- **Graph awareness**: link graph tools are P2, enabling navigation without reading every page
- **Proactive maintenance**: `get_affected_pages` tells the agent what to update, instead of reactive backlinks scanning

Total: **12 new tools** across 4 priority tiers.

## How this plan system works

### Core files

| File | Purpose |
|------|---------|
| `README.md` | This file — goal, process, and agent instructions |
| `STATUS.md` | Single source of truth for current state of every feature |
| `roadmap.md` | All 12 features grouped by priority with descriptions and dependencies |
| `subplans/*.md` | One file per feature — stubs that will be expanded into full plans |

### The process

1. **Start here**: always read `STATUS.md` first to understand what's been done and what's pending.
2. **Pick a feature**: choose a `pending` feature from `STATUS.md`, starting from highest priority (P1 > P2 > P3 > P4).
3. **Plan before building**: before writing any code for a feature, expand its subplan file into a full plan. The full plan must include:
   - Research findings and design alternatives considered
   - Chosen approach with rationale
   - Implementation steps (specific files to create or modify)
   - **Scale considerations** — how the design handles 200+ pages
   - **Integration points** — how this tool composes with others in the roadmap
   - Acceptance criteria
   - How to verify the feature works
4. **Implement**: switch to Agent mode and implement the plan.
5. **Update status**: after completing or making progress on a feature, update `STATUS.md` immediately. Move the feature's status from `pending` to `in-research` to `planned` to `in-progress` to `completed`.

### Status values

| Status | Meaning |
|--------|---------|
| `pending` | Not started — no research or planning done yet |
| `in-research` | Actively investigating design options and trade-offs |
| `planned` | Full plan created in the subplan file, ready to implement |
| `in-progress` | Implementation underway |
| `completed` | Feature built, tested, and verified |
| `blocked` | Cannot proceed due to a dependency or unresolved question |
| `merged` | Subsumed into another feature |

### Agent checklist

Before starting any work related to this plan:

- [ ] Read `STATUS.md` for current state
- [ ] Read `roadmap.md` for feature overview and dependencies
- [ ] If picking a feature to work on, read its `subplan/*.md` file
- [ ] If the subplan file is a stub (no full plan yet), create the full plan first
- [ ] After completing work, update `STATUS.md` with the new status
- [ ] After implementing a feature, verify it works through the browser (per project rules)

### Rules

- **Do NOT implement a feature without a full plan** in its subplan file. Research and design decisions must be documented before code is written.
- **Update STATUS.md every time you change a feature's state.** The status file is the source of truth.
- **Read STATUS.md before starting work.** Do not rely on memory or context.
- **Respect priority order** unless a lower-priority feature is explicitly requested or becomes a blocker for a higher-priority one.
- **Consider scale** in every subplan: how does this design handle 200+ pages? What degrades at that size?

## Architecture reference

For context on the MCP server's internal architecture:

- [ARCHITECTURE.md](../../doc_v2/architecture/index.md) — system components, request flow, module map
- [TOOL_CATALOG.md](../../doc_v2/reference/tool-catalog.md) — all 45 tools
- [DATABASE.md](../../doc_v2/architecture/database.md) — SQLite models and file mappings

## Current overall state

The plan system (scale-first redesign) is `completed`. All 12 features are `pending`. See `STATUS.md` for the detailed tracker.
