---
name: create-deploy-validation
description: >
  Generates layer-scoped local deploy smoke artifacts: shell scripts
  under _infra/cd/ that re-apply DDL migrations and re-sync the
  Airflow DAG bag, plus a pytest smoke module under tests/integration/
  that drives those scripts and re-triggers the layer DAG end-to-end.
  Pairs with the scrum-master deploy-validation story type 1:1.
  Use when the user asks to:
  - Author the local deploy smoke for a layer (bronze / silver / gold)
  - Wire up _infra/cd/ scripts (DAG sync, liquibase apply) for local
  - Implement a deploy-validation story (STORY-NN-NNN typed deploy-validation)
argument-hint: "[STORY-NN-NNN]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create Deploy Validation

You are a senior Data Engineer. Your job is to translate a
`deploy-validation` story's Acceptance Criteria into:

1. A set of executable scripts under `{project_root}/_infra/cd/` that
   re-apply the layer's deploy steps (Liquibase changelog application,
   DAG bag re-sync) against the **local** docker-compose stack.
2. A matching pytest smoke module under
   `{project_root}/tests/integration/{layer}/` that exercises those
   scripts end-to-end (assert each script exits 0; assert Airflow
   reports no DAG import errors; assert the re-triggered DAG run
   completes successfully).

## Workspace Discovery

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin
is project-agnostic — never hardcode project, chapter, table, DAG,
catalog, or schema names.

## Coding Patterns & Libraries Handbook

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required pattern docs for this skill:**

- `$PATTERNS_DIR/ci-cd-pattern.md` — local CD conventions
- `$PATTERNS_DIR/docker-compose-conventions.md` — service names + exec
  invocation
- `$PATTERNS_DIR/test-pattern.md` — pytest layout + marker conventions
- `$PATTERNS_DIR/LIBRARIES.md` — pinned tool versions (Liquibase,
  docker compose, etc.)

### Library freshness check

```bash
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, pause and call **AskUserQuestion** with options
`Refresh now` / `Proceed with cached versions` / `Cancel`. On Refresh,
invoke `/developer-plugin:refresh-libraries` then resume.

## Phase 0.a — Argument Resolution (mandatory, runs first)

```bash
# Step 1: capture the user's conversational input. Substitute the
# bracketed text below with the EXACT message the user supplied after
# the skill name; if no message was supplied, leave it as an empty
# string. This is the ONLY substitution this skill requires.
CONV_ARG='<<EXACT_CONVERSATIONAL_TEXT_FROM_USER_OR_EMPTY_STRING>>'

# Step 2: run the shared resolver. It auto-discovers the workspace
# from $PWD, so no {workspace_root} substitution is required. Output is
# two lines on stdout: the resolved value, then the source token.
read -r RESOLVED_ARG RESOLVED_SOURCE < <(
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_skill_arg.sh" "$CONV_ARG" \
    | paste -sd' ' -
)
```

Print this banner as the **first line** of skill output:

```
RESOLVED TARGET: <STORY-NN-NNN> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__>)
```

If `$RESOLVED_SOURCE == EMPTY`, ask the user via `AskUserQuestion` which
deploy-validation story applies.

## Domain of Ownership

This skill owns:

- `_infra/cd/**` — every script and config under the local CD root.
- `tests/integration/{layer}/test_{layer}_deploy.py` — the smoke
  pytest for the resolved layer.

ROUTE-OUT for everything else. In particular this skill MUST NOT
modify:

- `_infra/ci/**` (owned by `create-pipeline` / `update-pipeline`)
- `airflow/dags/**` (owned by `create-dag` / `update-dag`)
- `ddl/liquibase/**` (per-table content owned by layer skills;
  master + properties owned by `update-scaffold`)
- `tests/integration/conftest.py` if it already exists (owned by
  `create-integration-test`)

## Workflow

### Phase 0: Upstream Gate

Resolve upstream artifact paths via the shared helper (no hardcoded
chapter / project names):

```bash
eval "$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --export)"
```

The helper exports `$LATEST_LLD_DIR`. Read the latest LLD and verify
`Status: Approved`.

### Phase 1: Read Story + Layer Context

1. Read the resolved STORY-NN-NNN markdown and extract:
   - **The layer** (`bronze` / `silver` / `gold`) — infer from epic
     slug or story slug.
   - **Each script path the AC names** under `_infra/cd/` — they
     appear as backtick-quoted paths in the AC text. Author one
     script per named path; never invent additional scripts.
   - **The deploy commands** the AC names (e.g. `liquibase update
     --changelog-file=…`, `airflow dags reserialize`, `airflow dags
     list-import-errors`, `docker compose exec …`) — these are the
     verbs the smoke test will assert against.
   - **The DAG ID** to re-trigger — read from the AC text; the AC
     names it explicitly.
2. Read the existing docker-compose to discover:
   - The Airflow service name (typically `airflow`, but never assume
     — read `_infra/docker/docker-compose.yml`).
   - Whether `airflow/dags/` is bind-mounted (live-sync) or baked into
     the image. The script's "sync" step differs:
     - Bind-mount: `airflow dags reserialize` is sufficient.
     - Baked: copy the dags into the container, then reserialize.

### Phase 2: Author `_infra/cd/` Scripts

For each script path the AC names, write a POSIX shell script under
`{project_root}/_infra/cd/`. Each script MUST:

- Open with `#!/usr/bin/env bash` and `set -euo pipefail`.
- Source service / compose-file paths from env vars with safe defaults:
  ```sh
  COMPOSE="${COMPOSE:-docker compose}"
  COMPOSE_FILE="${COMPOSE_FILE:-_infra/docker/docker-compose.yml}"
  AIRFLOW_SERVICE="${AIRFLOW_SERVICE:-airflow}"
  ```
  Read the service name **from the project's compose file** at runtime
  if the AC doesn't override it; never hardcode container names.
- Fail-closed: exit with a non-zero status code (and a readable
  message to stderr) if any deploy step fails. Pre-flight: verify the
  expected service is running via `${COMPOSE} -f "${COMPOSE_FILE}"
  ps --status running --services` and fail with a clear hint if not.
- Be idempotent and safe to re-run.
- End with a one-line `[script-name] OK -- <what was done>` so the
  smoke test can grep for success.

Script-specific contents:

| Script the AC asks for | Body |
|---|---|
| `airflow-sync.sh` (or similarly named DAG sync) | `airflow dags reserialize`, then `airflow dags list-import-errors`. Fail if any import errors are listed. |
| `liquibase-apply.sh` (or similarly named DDL apply) | Run Liquibase via a containerized invocation (use the Liquibase image pinned in LIBRARIES.md). Mount the project's `ddl/liquibase/` into the container, point `--changelog-file` at the project-wide `master-changelog.xml`, supply credentials from env vars. |
| Other scripts the AC names | Implement minimally to satisfy the AC; do not invent extra work. |

Set the executable bit on every emitted script (`chmod +x`).

### Phase 3: Author the Smoke Test

Write `{project_root}/tests/integration/{layer}/test_{layer}_deploy.py`.
The module MUST:

- Carry `pytestmark = pytest.mark.integration` at module scope.
- Use the shared `stack` and `_require_stack` fixtures from
  `tests/integration/conftest.py` (do NOT duplicate them — if the
  conftest is missing, ROUTE-OUT to `create-integration-test`).
- One test per AC, named to mirror the AC's intent. Suggested map:

  | AC verb in story | Test name | Assertion |
  |---|---|---|
  | `liquibase update ... succeeds locally` | `test_liquibase_apply` | Run `_infra/cd/liquibase-apply.sh` via `subprocess.run`; assert `returncode == 0`. |
  | `airflow-sync.sh` re-syncs and `list-import-errors` reports none | `test_airflow_sync_no_errors` | Run `_infra/cd/airflow-sync.sh`; assert `returncode == 0` and stdout contains the success sentinel. |
  | Re-triggered DAG run completes | `test_dag_retrigger` | POST a new dagRun via Airflow REST (re-use the `stack.airflow_api` fixture); poll until terminal state; assert `state == "success"`. |
- Where the AC explicitly names a `pytest` node in its Verification
  block, the test function name MUST match that node exactly so the
  block's `pytest:` verifier resolves.

### Phase 4: Wire Coverage

If the project's `pyproject.toml` does not declare the `integration`
marker, ROUTE-OUT a note to `update-scaffold` to add it. Do NOT edit
`pyproject.toml` from this skill.

### Phase 5: Smoke Tests

Run the layer-scoped collect:

```bash
cd {project_root} && uv run pytest -m integration tests/integration/{layer}/test_{layer}_deploy.py --collect-only
```

Confirm the collected node IDs match what the story's Verification
block expects. The integration tests MUST skip honestly when the
stack is down (handled by the shared conftest).

### Phase 6: Verification Compliance Self-Check (MANDATORY)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/../scripts/verify_acs.py STORY-NN-NNN --json
```

Apply the same OK / CRITICAL / WARNING semantics as `create-dag`
Phase 6. Mechanical-failure ACs are CRITICAL and prevent flipping the
plan task to `done`.

## Output Summary

Per file: `PATH | CREATED / EDITED / SKIPPED`. Conclude with
`Next: /developer-plugin:validate-stories STORY-NN-NNN`.

## Hard Rules

1. Never edit files outside `_infra/cd/**` and
   `tests/integration/{layer}/test_{layer}_deploy.py`. ROUTE-OUT
   everything else.
2. Shell scripts MUST be POSIX-compatible with `set -euo pipefail`
   and source service / compose-file paths from env vars. No
   hardcoded container or service names.
3. Liquibase invocation MUST point at the project-wide
   `master-changelog.xml`, never at a layer-specific aggregator (LLD
   §9.1 mandates a single master).
4. The smoke test reads endpoints from the shared `stack` fixture —
   it does not embed `http://localhost:…` URLs anywhere.
5. Idempotent: re-running any emitted script must be safe and not
   leave the local stack in a degraded state.

## Learnings & Corrections

_No learnings recorded yet._
