# Reference

Technical reference documentation for wiki-js-mcp v4. Look up tool signatures, configuration variables, test suites, and metadata templates.

## Quick Navigation

| Document | Description | Use when |
|----------|-------------|----------|
| [Quick Reference](quick-reference.md) | Single-page cheat sheet: all tools, collections, SQLite tables, workflows, ports, Docker commands, common errors | You need a quick lookup — start here |
| [Tool Catalog](tool-catalog.md) | All 22 tools across 3 servers with signatures, parameters, and return types | You need to know what a tool does or what parameters it accepts |
| [Error Catalog](error-catalog.md) | All common errors across 3 servers with causes and resolutions | You encounter an error and need to fix it |
| [Configuration](config.md) | Environment variables, Docker profiles, port defaults | You need to set up `.env` or understand Docker Compose profiles |
| [Testing Guide](testing.md) | Test suites, profile commands, fixture generation | You need to run or understand the test suites |
| [Test Results](test-results.md) | Latest run results, per-suite pass/fail counts | You want to see current test health |

## For Agents

- **[Tool Catalog](tool-catalog.md)** is the primary reference — every tool your LLM agent can call is listed here with its full signature.
- **[Configuration](config.md)** documents the environment variables. Read for port assignments and Qdrant connection strings.
- **[Testing Guide](testing.md)** explains how tests work and what Docker profiles to use.

## Related Sections

- [MCP Servers](../mcp-servers/index.md) — Per-server details, container configs, and tool descriptions
- [Architecture](../architecture/index.md) — System design, Qdrant, module map
- [Patterns](../patterns/index.md) — Code conventions and communication patterns
- [Guides](../guides/index.md) — Workflows and how-to instructions
