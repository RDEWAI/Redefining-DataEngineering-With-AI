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

## Coding Patterns & Libraries Handbook

Before patching any scaffold file, load the latest coding-patterns handbook:

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required pattern docs for this skill:**

- `$PATTERNS_DIR/project-structure.md` — medallion tree + mandatory dirs
- `$PATTERNS_DIR/makefile-conventions.md` — required Make targets
- `$PATTERNS_DIR/docker-compose-conventions.md` — UC + Marquez stack
- `$PATTERNS_DIR/dependency-management.md` — UV + pyproject.toml layout
- `$PATTERNS_DIR/naming-conventions.md` — file / module naming rules
- `$PATTERNS_DIR/LIBRARIES.md` — pinned library versions

### Library freshness check

```bash
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, pause and call **AskUserQuestion** with options `Refresh now` / `Proceed with cached versions` / `Cancel`. If the user picks Refresh, invoke `/developer-plugin:refresh-libraries` and resume.

### References trailer (in output)

Emit a `### References` section citing the consumed pattern docs + LIBRARIES.md vintage. Add `⚠ Library versions cached $AGE_DAYS days ago; run /developer-plugin:refresh-libraries to refresh.` if the user proceeded with stale cache.

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
