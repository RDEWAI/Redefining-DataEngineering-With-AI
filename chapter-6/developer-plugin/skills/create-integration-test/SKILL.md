---
name: create-integration-test
description: >
  Generates layer-scoped integration tests under tests/integration/ that
  trigger an Airflow DAG against the local docker-compose stack (Airflow +
  Unity Catalog OSS + Marquez) and assert end-to-end data quality. Reads
  the approved LLD and the target story's ACs, emits a per-layer test
  module (DAG trigger + UC table checks) plus a SE-runtime-evidence module
  (bronze_se_stats / Marquez dq_pass_rate). Pairs with the
  scrum-master integration-test story type 1:1.
  Use when the user asks to:
  - Author the integration test for a layer (bronze / silver / gold)
  - Wire up a pytest-mark integration suite against the docker stack
  - Implement an integration-test story (STORY-NN-NNN typed integration-test)
argument-hint: "[STORY-NN-NNN]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create Integration Test

You are a senior Data Engineer. Your job is to translate an
`integration-test` story's Acceptance Criteria into a layer-scoped pytest
suite under `tests/integration/{layer}/` that exercises the live local
stack: Airflow REST API triggers the layer's DAG, Unity Catalog OSS
serves the landed Delta tables, and Marquez exposes the OpenLineage run
facets.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`.

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

- `$PATTERNS_DIR/test-pattern.md` — pytest layout + marker conventions
- `$PATTERNS_DIR/airflow-dag-pattern.md` — DAG ID + task naming
- `$PATTERNS_DIR/unity-catalog-pattern.md` — UC REST endpoints used by the test
- `$PATTERNS_DIR/openlineage-marquez-pattern.md` — Marquez REST endpoints + facet keys
- `$PATTERNS_DIR/spark-expectations-pattern.md` — SE stats table name + run-evidence schema
- `$PATTERNS_DIR/docker-compose-conventions.md` — host/port map for Airflow + UC + Marquez. The conftest defaults (`AIRFLOW_API`, `UC_API`, `MARQUEZ_API`) MUST be sourced from this doc, never hardcoded.
- `$PATTERNS_DIR/LIBRARIES.md` — pinned `requests` / `pytest` versions

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
integration-test story applies.

## Domain of Ownership

This skill owns paths matching:

- `tests/integration/**` — every file under the integration test root
- A shared `tests/integration/conftest.py` providing the stack-readiness
  fixture and endpoint discovery (idempotent — author once, reused by
  every layer's tests)

ROUTE-OUT any path outside this glob. In particular this skill MUST NOT
write to `tests/bronze/`, `tests/silver/`, `tests/gold/`, `_infra/`, or
the source tree under `src/`.

## Workflow

### Phase 0: Upstream Gate

Resolve upstream artifact paths via the shared helper (no hardcoded
chapter / project names):

```bash
eval "$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --export)"
```

The helper exports `$LATEST_LLD_DIR`, `$LATEST_DMS_DIR`,
`$LATEST_STORIES_DIR`, etc. Read the latest LLD from `$LATEST_LLD_DIR/`
and verify `Status: Approved`.

### Phase 1: Read Story + Layer Context

1. Read the resolved STORY-NN-NNN markdown and extract:
   - The DAG ID it triggers (parse from the story's AC text — the AC
     names the DAG explicitly; do NOT assume a DAG-ID literal).
   - The target layer (`bronze` / `silver` / `gold`) — infer from the
     epic slug (e.g. `EPIC-NN-{layer}-…`) or the story slug.
   - The expected table set — from the LLD's per-layer task inventory
     (typically §5.1 Bronze / §5.2 Silver dim / §5.3 Silver fact /
     §5.4 Gold; read the latest LLD to confirm section numbering),
     filtered to the layer under test.
   - The SE stats table name — from the LLD section that defines the
     SE-RUN-EVIDENCE contract (typically named `{layer}_se_stats`,
     but read the LLD to confirm — never hardcode).
   - Metadata column names — from the LLD §2.3 (or equivalent) module
     interface contract for the ingestion runner. Read the LLD; do
     not hardcode column names.
   - UC catalog + schema names — from the project's runtime config
     (env vars resolved via `pipeline_config` or equivalent — never
     hardcode `unity.bronze` or similar in the test path).
2. Read every existing `airflow/dags/*.py` to confirm the DAG ID is
   real before authoring a test that triggers it.

### Phase 2: Author Shared conftest (idempotent)

If `{project_root}/tests/integration/conftest.py` does not exist, write
it. The conftest MUST:

- Read endpoints from env vars with sensible local defaults. Required
  env var names (project-agnostic): `AIRFLOW_API`, `UC_URI`,
  `MARQUEZ_API`, `AIRFLOW_USER`, `AIRFLOW_PASSWORD`, plus a per-layer
  pair `<LAYER>_DAG_ID` and `UC_<LAYER>_SCHEMA` (e.g. `BRONZE_DAG_ID`,
  `UC_BRONZE_SCHEMA`) where `<LAYER>` is the upper-case layer name.
  The catalog name comes from `UC_CATALOG`. None of these defaults
  should encode a project-specific catalog/schema name — use the
  values declared in the LLD §7.1 (or equivalent) config schema.
- Provide a session-scoped `stack` fixture returning a frozen dataclass
  of the resolved endpoints.
- Provide an `autouse=True` session-scoped `_require_stack` fixture that
  probes `{AIRFLOW_API}/version`, `{UC_URI}/catalogs`, and
  `{MARQUEZ_API}/namespaces` over HTTP (NOT just TCP — TCP-only checks
  false-positive when an unrelated process binds the port). On any
  non-200-or-401 status the fixture calls `pytest.skip(...)` with a
  message that names every missing endpoint.

If the file already exists, leave it alone — do not overwrite a
hand-authored conftest. Use `Edit` to add fields/probes only when
strictly required by the new test module.

### Phase 3: Author Layer Test Module

Write `{project_root}/tests/integration/{layer}/test_{layer}_uc.py`. The
module MUST:

- Carry `pytestmark = [pytest.mark.integration, pytest.mark.e2e]` at module scope. The `e2e` marker is the canonical name (registered in chapter-6/pyproject.toml; gated behind `make eval-e2e` so it is excluded from `make test`). The `integration` marker is kept for compatibility with the chapter-5 inherited test layout — both must be present so collection works under either invocation.
- Constant tuple `LAYER_TABLES` derived from the LLD's per-layer task
  inventory (NOT hardcoded; read the LLD at generation time).
- Constant tuple `METADATA_COLUMNS` populated from the LLD §2.3 (or
  equivalent) ingestion runner contract. Read the LLD; do not
  hardcode column names.
- A module-scoped fixture `successful_dag_run` that:
  - POSTs to `{AIRFLOW_API}/dags/{dag_id}/dagRuns` with a fresh
    `dag_run_id` (e.g. `integration-{uuid4_hex_8}`).
  - Polls `GET {AIRFLOW_API}/dags/{dag_id}/dagRuns/{run_id}` every 10 s
    until `state in ("success", "failed")`, deadline 30 min.
  - `pytest.fail()` if the run ends in `failed` or times out.
- Test `test_dag_run_succeeds` (AC1): asserts the fixture's `state ==
  "success"`.
- Test `test_{N}_{layer}_tables_in_uc` (AC2): GETs
  `{UC_URI}/tables?catalog_name=…&schema_name=…` and asserts every
  table in `LAYER_TABLES` is present.
- Parametrized test `test_metadata_columns_populated[table]` (AC3): for
  each table, GETs `{UC_URI}/tables/{catalog}.{schema}.{table}` and
  asserts the three metadata columns are in the column list.

Also write `{project_root}/tests/integration/{layer}/test_{layer}_se_evidence.py`
covering AC4 (SE stats run evidence) and AC5 (Marquez dq_pass_rate
facet):

- Helper `_latest_successful_run(stack)` queries
  `{AIRFLOW_API}/dags/{dag_id}/dagRuns?state=success&order_by=-start_date`
  and returns the most recent run inside a lookback window (2 h
  default).
- Test `test_se_stats_populated` (AC4): asserts the SE stats table
  (e.g. `{layer}_se_stats`) is present in UC AND a recent successful
  DAG run exists.
- Test `test_dq_pass_rate_in_marquez` (AC5): queries
  `{MARQUEZ_API}/namespaces/{ns}/jobs` for jobs whose name contains the
  DAG ID, then walks each job's runs and asserts at least one run's
  `facets` exposes a DQ key (`dataQuality`, `dataQualityMetrics`,
  `dataQualityAssertions`, or `dq_pass_rate`).

If a layer-specific `__init__.py` is missing under
`{project_root}/tests/integration/{layer}/`, create an empty one.

### Phase 4: Verify Marker Wiring

The project's `pyproject.toml` must declare the `integration` marker. If
absent, ROUTE-OUT a note to `update-scaffold` to add it under
`[tool.pytest.ini_options].markers`. Do NOT edit `pyproject.toml` from
this skill.

### Phase 5: Smoke Tests

Run two commands and report:

```bash
cd {project_root} && uv run pytest -m "not integration" --collect-only tests/integration/   # must collect 0
cd {project_root} && uv run pytest -m integration tests/integration/ -v                     # all skip without stack
```

The integration tests MUST skip honestly when the stack is down (the
conftest autouse fixture handles this). They must NOT be picked up by a
plain `pytest tests/` run that doesn't pass the integration marker.

### Phase 6: Verification Compliance Self-Check (MANDATORY)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/../scripts/verify_acs.py STORY-NN-NNN --json
```

Apply the same OK / CRITICAL / WARNING semantics as create-dag Phase 6.
Mechanical-failure ACs are CRITICAL and prevent flipping the plan task
to `done`.

## Output Summary

Per file: `PATH | CREATED / EDITED / SKIPPED`. Conclude with
`Next: /developer-plugin:validate-stories STORY-NN-NNN`.

## Hard Rules

1. Never overwrite an existing `tests/integration/conftest.py`. Use
   `Edit` for incremental additions; ask via `AskUserQuestion` before
   any structural change.
2. The autouse readiness fixture MUST do an HTTP-level probe (not TCP)
   so unrelated processes binding the port do not produce false-pass
   skip behavior.
3. Every test module created here carries the `integration` marker at
   module scope. No exceptions.
4. Endpoint URLs and credentials come from env vars; never hardcode
   `http://localhost:8080` or similar inside an assertion path — only as
   the env var's default.
5. Never write files outside `tests/integration/**` — ROUTE-OUT for
   `pyproject.toml`, `Makefile`, `_infra/`, source code, etc.

## Learnings & Corrections

_No learnings recorded yet._
