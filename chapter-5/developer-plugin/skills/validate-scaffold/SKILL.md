---
name: validate-scaffold
description: >
  Validates the project scaffold against the LLD (directory tree, Make
  targets, infra layout) and the DMS (StructType contracts). Read-only:
  reports pass/fail per check without editing anything. Runs the scaffold's
  own smoke tests (`uv sync`, import check, `pytest --collect-only`) and
  surfaces each failure with the exact command to reproduce.
  Use when the user asks to:
  - Validate the scaffold / foundation
  - Check STORY-01-NNN implementation
  - Confirm scaffold is ready before running create-dag / create-ingestion
argument-hint: "[STORY-01-NNN | 'full']"
allowed-tools: Read, Grep, Glob, Bash
context: fork
---

# Validate Project Scaffold

Read-only verifier for EPIC-01 deliverables. Produces the same
`PASS / FAIL / INDETERMINATE` verdict per check that `validate-stories`
consumes as a heuristic input.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Coding Patterns Handbook

Load the pattern docs this skill checks against (read-only; no freshness prompt):

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "WARNING: inputs/code/v*/ not found — pattern-conformance checks will be INDETERMINATE."
fi
```

**Pattern docs consulted:**

- `$PATTERNS_DIR/project-structure.md` — tree + mandatory dirs
- `$PATTERNS_DIR/makefile-conventions.md` — required Make targets
- `$PATTERNS_DIR/LIBRARIES.md` — pinned versions to compare pyproject.toml against

### References trailer (in output)

Cite each pattern doc consulted, e.g. `Checked against inputs/code/v1/project-structure.md §tree`. Flag an INDETERMINATE verdict on any check whose pattern doc was missing.

## Checks

### Directory tree (STORY-01-001)

For each path in LLD §2.1, `Glob` its existence under `{project_root}/`:

- `src/{project_name}/{bronze,silver,gold,utils}/__init__.py`
- `airflow/dags/`, `airflow/configs/`
- `contracts/`, `contracts/dq/`, `dq_rules/`
- `ddl/liquibase/changelogs/`
- `tests/{bronze,silver,gold}/`
- `_infra/{docker,ci,cd}/`
- `pyproject.toml`, `Makefile`, `CLAUDE.md`

### Config loader (STORY-01-002)

- `src/{project_name}/utils/config_loader.py` exists
- `Grep("def load_config", config_loader.py)` returns ≥1 match
- `Grep("yaml", config_loader.py)` (loader imports pyyaml)

### Template config (STORY-01-003)

- `airflow/configs/_template.yml` exists
- Contains keys: `source`, `schema_ref`, `output`, `empty_input_behavior`, `metadata_columns`

### Logging framework (STORY-01-004)

- `src/{project_name}/utils/logging.py` exists
- `Grep("def get_logger", logging.py)` returns ≥1 match

### Test infrastructure (STORY-01-005)

- `tests/conftest.py` exists
- Each of `tests/{bronze,silver,gold}/conftest.py` exists
- `uv run pytest tests/ --collect-only -q` exits 0

### Docker compose (STORY-01-006)

- `_infra/docker/docker-compose.yml` exists and parses (run `docker compose config -q` if docker is available; else skip with INDETERMINATE)
- `_infra/docker/Dockerfile.airflow` exists

### StructType schemas (STORY-01-008)

- 13 YAML files exist in `contracts/` (one per table)
- Each references columns present in the corresponding DMS table
- For each table: all column names from DMS appear in the YAML (compared case-insensitively)

### Smoke tests

```bash
cd {project_root}
uv sync --all-extras           # PASS only if exit 0
uv run python -c "import {project_name}.utils.config_loader; import {project_name}.utils.logging"
uv run pytest tests/ --collect-only -q
```

## Output Format

```
Scaffold validation — target: STORY-01-001

Checks:
  src/{project_name}/bronze/__init__.py ........... PASS
  src/{project_name}/silver/__init__.py ........... PASS
  ...
  tests/bronze/conftest.py ..................... PASS
  Makefile .................................... PASS
  uv sync --all-extras ........................ PASS
  pytest --collect-only ....................... PASS

Summary: 18/18 PASS, 0 FAIL, 0 INDETERMINATE
Overall: PASS
```

## Hard Rules

1. Read-only. Never edit or create a file.
2. Never invoke `docker compose up` or any long-running process — config validation only.
3. Every check emits exactly one verdict. No silent skips.

## Edge Cases

- **`uv` not installed** — INDETERMINATE (not FAIL); tell the user to install it.
- **`{project_root}/` does not exist** — single-line FAIL: "scaffold not generated; run /developer-plugin:create-scaffold".
- **DMS not found** — StructType checks are INDETERMINATE; tree/module checks still run.

## Learnings & Corrections

_No learnings recorded yet._
