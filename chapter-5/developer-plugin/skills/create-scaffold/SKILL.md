---
name: create-scaffold
description: >
  Generates the foundational project scaffold for a cookiecutter-chapter
  project: directory tree, __init__.py files, pyproject.toml, Makefile,
  config loader, logging framework, test infrastructure, docker-compose, and
  StructType schema contracts. Wraps the `cookiecutter-chapter` template for
  the initial tree and fills in foundation modules that other generators
  (create-dag, create-ingestion, create-pipeline) depend on. Covers EPIC-01
  stories except STORY-01-007 (dag-skeleton), which is owned by create-dag.
  Use when the user asks to:
  - Scaffold the project / bootstrap the chapter
  - Implement STORY-01-NNN (foundation stories)
  - Create config loader / logging / test harness / docker-compose
argument-hint: "[STORY-01-NNN | 'full']"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
context: fork
---

# Create Project Scaffold

You generate the foundation that every other create-* skill assumes exists:
the directory tree, Python packaging, developer tooling, and a handful of
utility modules. This is the first skill any new cookiecutter-chapter project runs.

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

Before any code generation, load the latest coding-patterns handbook:

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

If `AGE_DAYS > 30` (per `freshness_policy: warn-after-30-days`), pause and call **AskUserQuestion**:

- **Question**: "Libraries in `LIBRARIES.md` were last verified $LAST_VERIFIED ($AGE_DAYS days ago). How should I proceed?"
- **Options**:
  - `Refresh now` — invoke `/developer-plugin:refresh-libraries`, then resume this skill with the updated versions.
  - `Proceed with cached versions` — continue; add a stale-cache warning to the References trailer.
  - `Cancel` — abort cleanly, no partial output.

If `LIBRARIES.md` is missing, halt and tell the user to run `/developer-plugin:refresh-libraries` to initialize the catalogue.

### References trailer (in output)

Every run MUST emit a `### References` section citing the consumed docs + LIBRARIES.md vintage. If the user chose "Proceed with cached versions", prepend: `⚠ Library versions cached $AGE_DAYS days ago; run /developer-plugin:refresh-libraries to refresh.`

## Story → Deliverable Map (EPIC-01)

| Story ID       | Title                      | Primary deliverables                                                                                                       |
|----------------|----------------------------|----------------------------------------------------------------------------------------------------------------------------|
| STORY-01-001   | Project directory structure | Cookiecutter render → `src/{project_name}/{bronze,silver,gold,utils}/__init__.py`, `airflow/`, `contracts/`, `dq_rules/`, `ddl/liquibase/changelogs/`, `tests/{bronze,silver,gold}/`, `_infra/{docker,ci,cd}/`, `pyproject.toml`, `Makefile`, `CLAUDE.md` |
| STORY-01-002   | Config loader              | `src/{project_name}/utils/config_loader.py` — YAML loader + env interpolation + schema validation                             |
| STORY-01-003   | Config template            | `airflow/configs/_template.yml` — canonical per-table ingestion config schema                                              |
| STORY-01-004   | Logging framework          | `src/{project_name}/utils/logging.py` — structured JSON logger, correlation IDs                                               |
| STORY-01-005   | Test infrastructure        | `tests/conftest.py`, `tests/{bronze,silver,gold}/conftest.py`, pytest markers, fixtures for Spark/DuckDB                   |
| STORY-01-006   | Docker compose             | `_infra/docker/docker-compose.yml`, `_infra/docker/Dockerfile.airflow`                                                      |
| STORY-01-008   | StructType schemas         | `contracts/{table}.yml` (13 tables) — StructType-compatible schema with nullability + metadata columns                     |

STORY-01-007 (DAG skeleton) is NOT in scope — route it to `create-dag`.

## Workflow

### Phase 0: Resolve Target

**Single story mode** (`STORY-01-NNN`):
- Normalize argument (uppercase, zero-padded).
- Look up deliverables in the Story → Deliverable Map above.
- Stop if the story is not in EPIC-01 or is STORY-01-007 (point the user at `create-dag`).

**Full mode** (no arg or `full`):
- Run every story in the map, topo-sorted by Depends On
  (STORY-01-001 must precede 002/003/004/005/006/008).

### Phase 1: Pre-flight

- Read the latest LLD (`{workspace_root}/inputs/lld/v*/LLD-*.md`) for the canonical directory tree (§2.1), Makefile targets (§9.3), and Decision 13 (cookiecutter).
- Check which deliverables already exist on disk. If ALL exist → tell the user to use `update-scaffold` instead and exit.
- Check that the cookiecutter template path exists
  (`{workspace_root}/inputs/lld/v*/templates/cookiecutter-chapter/` or the repo-root
  `templates/cookiecutter-chapter/`).

### Phase 2: Generate

**Step 1 — STORY-01-001 (directory tree).**

If target includes 001 AND `{project_root}/` is empty/missing:

```bash
uvx cookiecutter templates/cookiecutter-chapter/ --overwrite-if-exists \
  chapter_name=chapter-5 project_name=patient_360 python_version=3.12  # example inputs
```

Otherwise verify each path from the LLD §2.1 tree exists. For any missing
directory, create it and drop a `.gitkeep` in otherwise-empty dirs. For any
missing `__init__.py` in a Python package dir, write an empty file.

**Step 2 — Utility modules (stories 002, 004).**

Use `Write` to create each module. Keep them minimal but complete: imports,
docstring, one working entry point. Reference the LLD for behavior
requirements — do not invent functionality.

**Step 3 — Template config (story 003).**

Emit `airflow/configs/_template.yml` that matches the YAML schema the
create-ingestion skill expects (source, schema_ref, output, se_rules,
empty_input_behavior, metadata_columns).

**Step 4 — Test infrastructure (story 005).**

Write `tests/conftest.py` with shared fixtures (temp dir, Spark session
factory, DuckDB connection). Per-layer `conftest.py` files re-export the
fixtures each layer needs.

**Step 5 — Docker compose (story 006).**

Write `_infra/docker/docker-compose.yml` + `Dockerfile.airflow` reflecting
LLD §9.1 infra. Pin image versions.

**Step 6 — StructType schemas (story 008).**

For each of the 13 tables (patients, encounters, allergies, careplans,
claims, conditions, immunizations, medications, observations, organizations,
payers, procedures, providers), emit `contracts/{table}.yml` with the
StructType-compatible schema. Schema content comes from the DMS
(`{workspace_root}/inputs/dms/v*/` or `chapter-4/outputs/dms/v*/`). Do NOT invent columns — if a DMS table is
missing, stop with CRITICAL.

### Phase 3: Smoke Tests

```bash
cd {project_root}
uv sync --all-extras
uv run python -c "import {project_name}.utils.config_loader; import {project_name}.utils.logging"
uv run pytest tests/ --collect-only -q
```

All three must succeed. A failure blocks completion — report it with the
failing command and stderr.

### Phase 4: Output Summary

Print a per-story row: `STORY-01-NNN | N files created | OK / FAIL`.

End with: `Next: /developer-plugin:validate-scaffold <same-arg>`.

## Hard Rules

1. Never overwrite a non-template file without AskUserQuestion confirmation.
2. StructType schemas MUST come from DMS — no invented columns or types.
3. Do not touch `airflow/dags/` — that belongs to `create-dag`.
4. Do not touch `src/{project_name}/bronze/` — that belongs to `create-ingestion`.
5. The `dq_rules/` directory is created empty; SE rules are owned by the DQ Engineer plugin.

## Edge Cases

- **Cookiecutter template missing** — fall back to hand-created directory tree per LLD §2.1; warn the user.
- **Partial scaffold already exists** — create only the missing pieces; never overwrite existing Python modules.
- **DMS file not found for a table** — stop with CRITICAL listing the missing table(s).
- **`uv sync` fails** — surface the stderr; do not retry silently.

## Learnings & Corrections

_No learnings recorded yet._
