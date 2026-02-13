# Chapter 3: Business Analyst Agent for DRD Generation

## Overview

This chapter implements a Claude Business Analyst Agent as a **Claude Code Plugin**
with skills to generate, update, and validate Data Requirements Documents (DRDs).

## Plugin Structure

The plugin lives in `ba-plugin/` and is defined by `ba-plugin/.claude-plugin/plugin.json`.
The marketplace manifest is at `.claude-plugin/marketplace.json`.

- `ba-plugin/skills/` - Skill definitions (create-drd, update-drd, validate-drd)
- `ba-plugin/hooks/` - PostToolUse hook for automatic DRD validation
- `ba-plugin/scripts/` - Hook scripts (validate-drd-hook.py)

## Installing the Plugin

From the repo root:
```bash
/plugin marketplace add ./chapter-3
/plugin install ba-plugin@rdewai-plugins
```

## Skills

- **create-drd**: Generate a new DRD from input documents
- **update-drd**: Update an existing DRD with new information
- **validate-drd**: Validate a DRD against completeness standards

## Hooks

The plugin includes a **PostToolUse** hook that automatically validates DRD files
after every Write or Edit operation. If CRITICAL issues are found, Claude receives
the errors as feedback and auto-fixes them.

## Directory Layout

- `inputs/drd/` - Input documents (business requests, stakeholder notes, source docs, catalogs)
- `outputs/drd/` - Generated DRD output files
- `ba-plugin/` - Plugin directory (skills, hooks, scripts)
- `tests/` - Validator and hook unit tests

## Key Commands

```bash
make dev-setup      # Install dependencies
make test           # Run all tests
make validate-drd   # Validate all DRDs in outputs/
make lint           # Run linter
```
