---
name: update-scaffold
description: >
  Updates an existing project scaffold: adds missing directories/modules,
  patches pyproject.toml / Makefile / docker-compose when the LLD changes,
  and brings StructType schema contracts in sync with a revised DMS. Never
  deletes files. Use when the user asks to:
  - Refresh scaffold after LLD revision
  - Sync contracts/ against a new DMS version
  - Add a new foundation module to an existing project
argument-hint: "[STORY-01-NNN | 'sync-contracts' | 'sync-infra']"
allowed-tools: Read, Edit, Write, Grep, Glob, Bash, AskUserQuestion
context: fork
---

# Update Project Scaffold

This skill patches existing scaffold files in place. It is the safer
counterpart to `create-scaffold` — use it when `{project_root}/` already
exists and you just need to add, reconcile, or refresh a foundation piece.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## When to use vs create-scaffold

| Situation                                       | Skill             |
|-------------------------------------------------|-------------------|
| `{project_root}/` does not exist                | `create-scaffold` |
| Directory tree absent                           | `create-scaffold` |
| Everything present, need to add one module      | `update-scaffold` |
| DMS revised → need to regenerate schema YAMLs   | `update-scaffold` (`sync-contracts`) |
| LLD §9.1 changed infra layout                   | `update-scaffold` (`sync-infra`)     |

## Workflow

### Phase 0: Resolve Target

- `STORY-01-NNN` — update the deliverables for that one story.
- `sync-contracts` — rewrite every `contracts/{table}.yml` from the latest DMS.
- `sync-infra` — reconcile `_infra/docker/`, `pyproject.toml`, and `Makefile` against the latest LLD §9.
- No arg — ask via `AskUserQuestion` which of the three.

### Phase 1: Diff

Compute the delta between what LLD/DMS says and what is on disk:

- List every target file and its status: `present-and-matches`, `present-and-differs`, or `missing`.
- Show the user the diff preview before any writes.

### Phase 2: Apply

- `missing` → `Write` the new file.
- `present-and-differs` → `Edit` with minimal context patches; never `Write` over a user-edited module without `AskUserQuestion` confirmation.
- `present-and-matches` → no-op.

### Phase 3: Smoke Tests

Same three commands as `create-scaffold` Phase 3 (`uv sync`, import check, `pytest --collect-only`).

### Phase 4: Output Summary

Per file: `PATH | MATCH / PATCHED / CREATED / SKIPPED`.

End with: `Next: /developer-plugin:validate-scaffold <same-arg>`.

## Hard Rules

1. Never delete a file. Renames are two steps: write the new path, tell the user to remove the old one.
2. Never overwrite a Python module whose `git blame` shows human edits without `AskUserQuestion` confirmation.
3. StructType schemas MUST come from DMS — no invented columns.
4. Do not touch `airflow/dags/`, `src/{project_name}/bronze/`, or `dq_rules/`.

## Edge Cases

- **File present but not tracked by git** (user's local work) → treat as user-edited; require confirmation.
- **DMS has new table not in `contracts/`** → create it.
- **Contract has table no longer in DMS** → flag, do not delete (Rule 1).

## Learnings & Corrections

_No learnings recorded yet._
