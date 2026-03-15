# Chapter 4: Planning with Context — Multi-Agent Artifact Chain

## Overview

This chapter implements the full planning workflow as Claude Code Plugins,
each role producing a structured artifact that feeds the next.

**Artifact chain**: DRD → **HLD** → Data Model → DMD → DQS → LLD → Stories

## Plugins

### BA Plugin (from Chapter 3)

The plugin lives in `ba-plugin/` and is defined by `ba-plugin/.claude-plugin/plugin.json`.

- `ba-plugin/skills/` - Skills: create-drd, update-drd, validate-drd
- `ba-plugin/hooks/` - PostToolUse hook for automatic DRD validation
- `ba-plugin/scripts/` - Hook scripts (validate-drd-hook.py, enforce-readonly-queries.py)

### Architect Plugin

The plugin lives in `architect-plugin/` and is defined by
`architect-plugin/.claude-plugin/plugin.json`.

- `architect-plugin/skills/` - Skills: create-hld, update-hld, validate-hld
- `architect-plugin/hooks/` - PostToolUse hook for automatic HLD validation
- `architect-plugin/scripts/` - Hook scripts (validate-hld-hook.py, enforce-readonly-queries.py)

**Inputs**: Latest DRD from `outputs/drd/v{N}/` + `inputs/architect/v{N}/` (infrastructure constraints, team capabilities, technology catalog)

**Outputs**: HLD documents in `outputs/hld/v{N}/`

## Installing Plugins

From the repo root:
```bash
/plugin marketplace add ./chapter-4
/plugin install ba-plugin@rdewai-plugins
/plugin install architect-plugin@rdewai-plugins
```

## Directory Layout

- `inputs/drd/v{N}/` - BA Agent input documents (folder-versioned)
- `inputs/architect/v{N}/` - Architect Agent input documents (folder-versioned)
- `outputs/drd/v{N}/` - Generated DRD files (folder-versioned)
- `outputs/hld/v{N}/` - Generated HLD files (folder-versioned)
- `ba-plugin/` - BA Agent plugin
- `architect-plugin/` - Architect Agent plugin
- `tests/` - All unit tests

## Versioning Convention

All inputs and outputs use **folder-based versioning** (`v1/`, `v2/`, etc.).
The latest version folder is the source of truth for that component. Agents
auto-discover the latest version via:

```bash
ls -d chapter-4/{path}/v* | sort -V | tail -1
```

## Key Commands

```bash
make dev-setup      # Install dependencies
make test           # Run all tests
make validate-drd   # Validate all DRDs in outputs/drd/
make validate-hld   # Validate all HLDs in outputs/hld/
make lint           # Run linter
```
