# Chapter 4: Planning with Context — Multi-Agent Artifact Chain

## Overview

This chapter implements the full planning workflow as Claude Code Plugins,
each role producing a structured artifact that feeds the next.

**Artifact chain**: DRD → **HLD** → **DMS** → **STM** → DQS → LLD → Stories

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

### Data Modeler Plugin

The plugin lives in `data-modeler-plugin/` and is defined by
`data-modeler-plugin/.claude-plugin/plugin.json`.

- `data-modeler-plugin/skills/` - Skills: create-dms, update-dms, validate-dms
- `data-modeler-plugin/hooks/` - PostToolUse hook for automatic DMS validation
- `data-modeler-plugin/scripts/` - Hook scripts (validate-dms-hook.py, enforce-readonly-queries.py)

**Inputs**: Latest HLD from `outputs/hld/v{N}/` + DRD from `outputs/drd/v{N}/` + `inputs/dms/v{N}/`

**Outputs**: DMS documents in `outputs/dms/v{N}/`

### Mapping Analyst Plugin

The plugin lives in `mapping-analyst-plugin/` and is defined by
`mapping-analyst-plugin/.claude-plugin/plugin.json`.

- `mapping-analyst-plugin/skills/` - Skills: create-stm, update-stm, validate-stm
- `mapping-analyst-plugin/hooks/` - PostToolUse hook for automatic STM validation
- `mapping-analyst-plugin/scripts/` - Hook scripts (validate-stm-hook.py, enforce-readonly-queries.py)

**Inputs**: Latest DMS from `outputs/dms/v{N}/` + HLD from `outputs/hld/v{N}/` + `inputs/stm/v{N}/` (transformation standards, code system mappings)

**Outputs**: STM Excel workbooks (.xlsx) in `outputs/stm/v{N}/`

**Note**: STM output is **.xlsx** (Excel workbook with 8 sheets), not markdown. Uses **openpyxl** for generation and validation.

## Installing Plugins

From the repo root:
```bash
/plugin marketplace add ./chapter-4
/plugin install ba-plugin@rdewai-plugins
/plugin install architect-plugin@rdewai-plugins
/plugin install data-modeler-plugin@rdewai-plugins
/plugin install mapping-analyst-plugin@rdewai-plugins
```

## Directory Layout

- `inputs/drd/v{N}/` - BA Agent input documents (folder-versioned)
- `inputs/architect/v{N}/` - Architect Agent input documents (folder-versioned)
- `inputs/dms/v{N}/` - Data Modeler input documents (folder-versioned)
- `inputs/stm/v{N}/` - Mapping Analyst input documents (folder-versioned)
- `outputs/drd/v{N}/` - Generated DRD files (folder-versioned)
- `outputs/hld/v{N}/` - Generated HLD files (folder-versioned)
- `outputs/dms/v{N}/` - Generated DMS files (folder-versioned)
- `outputs/stm/v{N}/` - Generated STM Excel workbooks (folder-versioned)
- `ba-plugin/` - BA Agent plugin
- `architect-plugin/` - Architect Agent plugin
- `data-modeler-plugin/` - Data Modeler Agent plugin
- `mapping-analyst-plugin/` - Mapping Analyst Agent plugin
- `tests/` - All unit tests

## Versioning Convention

All inputs and outputs use **folder-based versioning** (`v1/`, `v2/`, etc.).
The latest version folder is the source of truth for that component. Agents
auto-discover the latest version via:

```bash
ls -d {path}/v* | sort -V | tail -1
```

## Key Commands

```bash
make dev-setup      # Install dependencies
make test           # Run all tests
make validate-drd   # Validate all DRDs in outputs/drd/
make validate-hld   # Validate all HLDs in outputs/hld/
make validate-dms   # Validate all DMSs in outputs/dms/
make validate-stm   # Validate all STMs in outputs/stm/
make lint           # Run linter
```
