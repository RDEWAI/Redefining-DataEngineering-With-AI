# Chapter 2: AI Engineering with Library Management Data

## Overview

This chapter demonstrates RAG, MCP, and Agentic AI patterns using a fictional library
management dataset. The Library Assistant agent is packaged as a Claude Code plugin.

## Plugin Structure

The plugin lives in `library-assistant-plugin/` and is defined by
`library-assistant-plugin/.claude-plugin/plugin.json`.
The marketplace manifest is at `.claude-plugin/marketplace.json`.

- `library-assistant-plugin/skills/` — Skill definitions (query-library, analyze-library)
- `library-assistant-plugin/hooks/` — PreToolUse hook for read-only query enforcement
- `library-assistant-plugin/scripts/` — Hook scripts (enforce-readonly-queries.py)
- `library-assistant-plugin/agents/` — Agent reference docs (domain knowledge)

## Installing the Plugin

From the repo root:
```bash
/plugin marketplace add ./chapter-2
/plugin install library-assistant-plugin@rdewai-plugins
```

## Skills

- **query-library**: Search books, check availability, locate by cabinet/rack/row,
  list by category or status, identify weak RFID signal books, get library stats.
- **analyze-library**: Analyze sales data — top sellers, revenue by segment/region/channel,
  monthly trends, per-book sales breakdown.

## Database

- **Path**: `data/duckdb/chapter2.db`
- **Schema**: `library`
- **Tables**: `library.books` (200 books), `library.sales` (750 sales records)

```bash
make load-data    # Load books + sales into DuckDB
make verify-data  # Verify 200 books loaded correctly
```

## Hooks

The plugin includes a **PreToolUse** hook that blocks any write operations against
the DuckDB database before execution. Only read-only SELECT queries are permitted.

## Directory Layout

- `data/duckdb/` — DuckDB database files
- `src/agentic/` — Python agent source (RAG, MCP, tool-calling implementations)
- `src/mcp/` — MCP server and client
- `src/rag/` — Simple RAG implementation
- `library-assistant-plugin/` — Claude Code plugin (skills, hooks, scripts)
- `tests/` — Unit and integration tests

## Key Commands

```bash
make dev-setup    # Install dependencies (uv sync)
make load-data    # Load 200 books + 750 sales into DuckDB
make verify-data  # Verify data loaded correctly
make test         # Run all tests
make lint         # Run ruff linter
```
