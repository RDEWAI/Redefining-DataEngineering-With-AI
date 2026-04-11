# Chapter 3: Business Analyst Agent for DRD Generation

## Overview

This chapter implements a Claude Business Analyst Agent as a **Claude Code Plugin**
with skills to generate, update, and validate Data Requirements Documents (DRDs).

## Plugin Structure

The plugin lives in `ba-plugin/` and is defined by `ba-plugin/.claude-plugin/plugin.json`.
The marketplace manifest is at `.claude-plugin/marketplace.json`.

- `ba-plugin/skills/` - Skill definitions (create-drd, update-drd, validate-drd, approve-drd, apply-learnings)
- `ba-plugin/agents/` - Agent REFERENCE doc (domain knowledge, not a launchable agent)
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
- **apply-learnings**: Process pending corrections into generalized skill rules

Skills invoke each other via the `Skill` tool (e.g., create-drd invokes validate-drd at the end).

## Hooks

The plugin includes a **PostToolUse** hook that automatically validates DRD files
after every Write or Edit operation. If CRITICAL issues are found, Claude receives
the errors as feedback and auto-fixes them.

## Directory Layout

- `inputs/drd/` - Input documents (business requests, stakeholder notes, source docs, catalogs)
- `outputs/drd/` - Generated DRD output files
- `memory/drd/` - Session notes and learnings queue
- `ba-plugin/` - Plugin directory (skills, hooks, scripts, agent REFERENCE)
- `tests/` - Validator and hook unit tests

## Update Versioning Rules (3 Scenarios)

When the update-drd skill is invoked, it follows one of these scenarios:

**Scenario A — Cross-version (v1 → v2)**
- **Trigger**: `inputs/drd/v{N+1}/` exists but `outputs/drd/v{N+1}/` does not, OR user explicitly requests a new version.
- **Action**: Create `outputs/drd/v{N+1}/`, copy latest DRD from v{N} with today's date, rename original as `.bak`, apply incremental edits. Set version to `{N+1}.0`, status to `Draft`.

**Scenario B — Same version, different date**
- **Trigger**: Latest DRD filename date ≠ today.
- **Action**: Copy old file to new file with today's date, rename old as `.bak`, apply edits. Bump minor version. One active file per version folder.

**Scenario C — Same version, same date (re-run)**
- **Trigger**: Latest DRD filename date = today.
- **Action**: Edit in-place, bump minor version. No `.bak` created.

## Artifact Status Lifecycle

DRDs use a 3-state status tracked in the metadata table:

```
Draft  →  Updated - Pending Review  →  Approved
```

- **Draft**: Set on initial creation
- **Updated - Pending Review**: Set after any update (minor version bump)
- **Approved**: Set explicitly via `approve-drd` skill

## Key Commands

```bash
make dev-setup      # Install dependencies
make test           # Run all tests
make validate-drd   # Validate all DRDs in outputs/
make lint           # Run linter
```
