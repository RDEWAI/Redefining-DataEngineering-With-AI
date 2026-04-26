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
  - Check a foundation-layer story's implementation
  - Confirm scaffold is ready before running create-dag / create-ingestion
argument-hint: "[STORY-NN-NNN | 'full']"
allowed-tools: Read, Grep, Glob, Bash
context: fork
---

# Validate Project Scaffold

Read-only verifier for the project's foundation layer (everything
create-scaffold owns, per that skill's *Domain of Ownership* section).
Produces `PASS / FAIL / INDETERMINATE` per check; `validate-stories`
consumes the verdicts as a heuristic input.

The checks below are grouped by **domain area**, not by story number —
any foundation-layer story, in any epic, under any project, will land in
one of these areas. When invoked with a specific `STORY-NN-NNN`, the skill
reads the story's AC at runtime and runs only the checks relevant to the
backtick-quoted paths it names.

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

### Area 1 — Directory tree

For each path enumerated in LLD §2.1, `Glob` its existence under
`{project_root}/`. The expected paths are read from the LLD at runtime,
not hardcoded. Typical cookiecutter-chapter projects include:

- `src/{project_name}/<layer>/__init__.py` for each layer LLD §2.1 declares
- `contracts/`, `contracts/dq/`, `dq_rules/`
- `ddl/liquibase/changelogs/` (or whatever migration tool LLD §9 names)
- `tests/<layer>/` per layer
- `_infra/{docker,ci,cd}/`
- `pyproject.toml`, `Makefile`, `CLAUDE.md`

### Area 2 — Utility modules (`src/{project_name}/utils/**`)

Enumerate every `.py` file under `src/{project_name}/utils/` and, for each:

- Module imports without error:
  `uv run python -c "import {project_name}.utils.<name>"` exits 0.
- Each public symbol named in the LLD §2.3 interface contract for that
  module is defined (`Grep` for `def <symbol>` / `class <symbol>`).

The module list is discovered at runtime — NEVER hardcoded. Any story that
declares a `utils/<name>.py` deliverable gets its module checked here.

### Area 3 — Test harness

- `tests/conftest.py` exists.
- Each `tests/<layer>/conftest.py` exists for each layer in LLD §2.1.
- `uv run pytest tests/ --collect-only -q` exits 0.
- `tests/utils/test_<name>.py` exists for each `utils/<name>.py` (if the
  story's AC calls for unit tests).

### Area 4 — StructType schema contracts

- One `contracts/<table>.yml` per table declared in DMS §2 (count and
  table names are read from the DMS — NEVER hardcoded).
- Each YAML references columns present in the corresponding DMS table.
- For each table: all column names from DMS appear in the YAML
  (case-insensitive comparison).

### Area 5 — Infra (`_infra/docker/**`, `docker-compose.yml`)

- The infra files named in LLD §9.1 exist — NOT `.gitkeep` placeholders.
  `_infra/docker/docker-compose.yml` must contain a `services:` block and
  every service name the LLD §9.1 table calls out (e.g. airflow-webserver,
  airflow-scheduler, unity-catalog / unitycatalog, marquez, grafana,
  prometheus, loki — read the list from LLD §9.1 at runtime, not hardcoded).
- `docker compose config -q` succeeds if docker is available; else mark
  the parse check as INDETERMINATE.

### Area 5a — CI workflow skeletons (`_infra/ci/.github/workflows/**`)

- `_infra/ci/.github/workflows/lint.yml` exists and calls `make lint`.
- `_infra/ci/.github/workflows/unit-test.yml` exists and calls `make test`.
- `_infra/ci/.github/workflows/integration-test.yml` exists and calls
  `make dev-up` / `make integration-test` / `make dev-down`.

### Area 5b — Liquibase changelogs (`ddl/liquibase/**`)

- `ddl/liquibase/master-changelog.xml` exists and contains at least one
  `<include file="changelogs/..." .../>` entry (i.e. is not the empty
  template skeleton).
- `ddl/liquibase/changelogs/` contains exactly N `*.xml` files where N is
  the number of Bronze tables declared in DMS §2 (read at runtime).
- Each changelog's filename matches a Bronze table name from DMS §2.

### Area 5c — Contract graph test (`tests/test_contracts.py`)

- `tests/test_contracts.py` exists.
- `pytest tests/test_contracts.py --collect-only -q` reports at least one
  collected test and no collection errors.

### Area 6 — Environment prerequisites

Re-run the same probes that `create-scaffold`'s Phase 1.5 preflight ran
(Python, Java major version vs Spark major in `LIBRARIES.md`, `uv`,
docker/compose if the project uses `_infra/docker/**`). Failures here are
reported as **FAIL** (not INDETERMINATE) — they explain why smoke tests
will fail. Tell the user to re-run `/developer-plugin:create-scaffold` to
re-trigger the install prompt, or to install manually.

### Area 7 — Smoke tests

```bash
cd {project_root}
uv sync --all-extras           # PASS only if exit 0
# Import smoke: discover util modules at runtime, import each.
for m in $(ls src/{project_name}/utils/*.py 2>/dev/null | \
           xargs -n1 basename | sed 's/\.py$//' | grep -v '^__'); do
  uv run python -c "import {project_name}.utils.$m" || echo "FAIL: $m"
done
uv run pytest tests/ --collect-only -q
```

## Output Format

```
Scaffold validation — target: <STORY-NN-NNN | full>

Checks:
  [tree]    src/<project>/<layer>/__init__.py ...... PASS  (per LLD §2.1)
  [utils]   utils/<name>.py imports ................ PASS  (per LLD §2.3)
  [tests]   tests/conftest.py ...................... PASS
  [tests]   pytest --collect-only .................. PASS
  [contracts] <N> YAML files vs DMS §2 ............. PASS
  [infra]   docker compose config -q ............... INDETERMINATE (docker unavailable)
  [smoke]   uv sync --all-extras .................... PASS

Summary: N/M PASS, 0 FAIL, 1 INDETERMINATE
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
