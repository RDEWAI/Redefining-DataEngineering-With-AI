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
  `MARQUEZ_API`, `AIRFLOW_USER`, `AIRFLOW_PASSWORD`, `AIRFLOW_AUTH_URL`,
  plus a per-layer pair `<LAYER>_DAG_ID` and `UC_<LAYER>_SCHEMA` (e.g.
  `BRONZE_DAG_ID`, `UC_BRONZE_SCHEMA`) where `<LAYER>` is the upper-case
  layer name. The catalog name comes from `UC_CATALOG`. Defaults:
  `AIRFLOW_API` = `http://localhost:8081/api/v2` (host port 8081 →
  container 8080; the `/api/v1` path returns 404 on Airflow 3.x), keep
  `UC_URI` and `MARQUEZ_API` defaults as-is. None of these defaults
  should encode a project-specific catalog/schema name — use the
  values declared in the LLD §7.1 (or equivalent) config schema.
- Auth is **JWT bearer for Airflow 3.x SimpleAuthManager**, not basic
  auth. The conftest MUST:
  - Read `AIRFLOW_USER` (default `admin`), `AIRFLOW_PASSWORD`
    (default `admin`), and `AIRFLOW_AUTH_URL` (default the stack's
    `/auth/token` root endpoint — derivable from `AIRFLOW_API` by
    removing the trailing `/api/v2` and appending `/auth/token`, i.e.
    `http://localhost:8081/auth/token`).
  - Provide a session-scoped **token fixture** (e.g. `airflow_token`)
    that POSTs JSON `{"username": <user>, "password": <pass>}` to
    `AIRFLOW_AUTH_URL` and returns the response's `access_token`. The
    fixture MUST accept **HTTP 200 OR 201** as success — Airflow 3.x's
    `POST /auth/token` returns **201 Created** (verified on Airflow
    3.2.1), while some builds return 200. Only `pytest.skip(...)` when
    the status is neither 200 nor 201 (or the request raises). Do NOT
    hardcode a 200-only check — that skips every integration test on a
    stack that returns 201.
  - Provide an `airflow_headers()` helper returning
    `{"Authorization": f"Bearer {token}"}`.
  - Do NOT provide an `airflow_auth()` basic-auth tuple method — basic
    auth returns HTTP 401 on Airflow 3.x.
- Provide a session-scoped `stack` fixture returning a frozen dataclass
  of the resolved endpoints.
- Provide an `autouse=True` session-scoped `_require_stack` fixture that
  probes `{AIRFLOW_API}/monitor/health` (no auth — the v2 health
  endpoint is unauthenticated and returns 200 when ready),
  `{UC_URI}/catalogs`, and `{MARQUEZ_API}/namespaces` over HTTP (NOT
  just TCP — TCP-only checks false-positive when an unrelated process
  binds the port). On any non-200 status the fixture calls
  `pytest.skip(...)` with a message that names every missing endpoint.
  Keep the UC/Marquez probe semantics unchanged.

> Note: Airflow 3.x REST is JWT-only; basic-auth tuples return 401. The
> token endpoint lives at the server root (`/auth/token`), not under
> `/api/v2`.

The conftest MUST ALSO provide a **shared session-scoped successful-run
fixture per layer** (e.g. `successful_{layer}_run`, such as
`successful_gold_run`) so the layer's UC test module and its SE-evidence
module read the SAME fresh successful DAG run regardless of pytest
collection order. Without it the suite is order-dependent: pytest
collects `test_{layer}_se_evidence.py` BEFORE `test_{layer}_uc.py`
(alphabetical), so an evidence test that scans for "the latest
successful run" can latch a STALE prior run (e.g. a `prestart-*` run
that predates the layer's terminal `reconciliation_{layer}` task) and
fail with a bogus `reconciliation_{layer} state is None`. The fixture
removes both the per-test independent trigger (in the UC module) and the
independent latest-successful scan (in the evidence module). It MUST:

- **Fast path (reuse):** query
  `{AIRFLOW_API}/dags/{dag_id}/dagRuns?state=success&order_by=-end_date&limit=10`
  with the `airflow_headers()` bearer header. If the most recent success
  ended within a reuse window (~45 min; parse `end_date` as ISO-8601 —
  accept both a trailing `Z` and an explicit offset — and compare to
  `datetime.now(timezone.utc)`), RETURN that run payload with no new
  trigger. This is what makes re-runs fast (no ~30-min DAG wait).
- **Slow path (trigger):** otherwise **unpause the DAG first** (`PATCH
  {AIRFLOW_API}/dags/{dag_id}` with `update_mask=is_paused` and body
  `{"is_paused": false}`; idempotent), then trigger a fresh run reusing
  the SAME JWT auth + `logical_date` contract used by the UC module's
  trigger helper (`{"dag_run_id": "integration-{uuid4_hex_8}",
  "logical_date": "<current UTC ISO-8601>"}`, accept HTTP 200/201), and
  poll `{AIRFLOW_API}/dags/{dag_id}/dagRuns/{run_id}` every 10 s to a
  terminal state (deadline 30 min). `pytest.fail(...)` on `failed`/timeout.
- Return the run **payload** (so consumers can both assert
  `state == "success"` for AC1 and address `dag_run_id` for task-instance
  / SE-evidence lookups). Guarantee `state == "success"` on return.
- Depend on `airflow_headers` (hence `airflow_token`) so it honestly
  `pytest.skip`s when the stack is down, matching the autouse probe.

If the file already exists, leave it alone — do not overwrite a
hand-authored conftest. Use `Edit` to add fields/probes only when
strictly required by the new test module (adding the shared
`successful_{layer}_run` fixture is a sanctioned incremental addition).

### Phase 3: Author Layer Test Module

Write `{project_root}/tests/integration/{layer}/test_{layer}_uc.py`. The
module MUST:

- Carry `pytestmark = pytest.mark.integration` at module scope.
- Constant tuple `LAYER_TABLES` derived from the LLD's per-layer task
  inventory (NOT hardcoded; read the LLD at generation time).
- Constant tuple `METADATA_COLUMNS` populated from the LLD §2.3 (or
  equivalent) ingestion runner contract. Read the LLD; do not
  hardcode column names.
- **Do NOT declare a module-scoped trigger fixture here.** Every test in
  this module consumes the shared session-scoped `successful_{layer}_run`
  fixture from the conftest (Phase 2). This is what keeps the UC module
  and the SE-evidence module reading the SAME fresh successful run — a
  per-module trigger reintroduces the collection-order defect.
- Test `test_dag_run_succeeds` (AC1): consumes `successful_{layer}_run`
  and asserts its `state == "success"`.
- Test `test_{N}_{layer}_tables_in_uc` (AC2): depends on
  `successful_{layer}_run` (so a run exists) and GETs
  `{UC_URI}/tables?catalog_name=…&schema_name=…`, asserting every table
  in `LAYER_TABLES` is present. Keep the UC-table assertions unchanged.
- Parametrized test `test_metadata_columns_populated[table]` (AC3): for
  each table, GETs `{UC_URI}/tables/{catalog}.{schema}.{table}` and
  asserts the three metadata columns are in the column list. (For layers
  whose AC3 is a fail-closed reconciliation gate — e.g. a Gold row-count
  gate — instead read `successful_{layer}_run["dag_run_id"]` and assert
  the terminal `reconciliation_{layer}` task instance is `success`.)

Also write `{project_root}/tests/integration/{layer}/test_{layer}_se_evidence.py`
covering AC4 (SE stats run evidence) and AC5 (Marquez dq_pass_rate
facet):

- **Do NOT scan for the latest successful run here.** Consume the shared
  session-scoped `successful_{layer}_run` fixture (Phase 2) instead of an
  independent `_latest_successful_run(...)` scan — the independent scan is
  exactly what made an alphabetically-earlier evidence module latch a
  stale run. Read `successful_{layer}_run["dag_run_id"]` for task-instance
  and SE-evidence lookups.
- Test `test_se_stats_populated` (AC4): consumes `successful_{layer}_run`
  and asserts the SE stats table(s) are present in UC AND (where the AC
  demands it) the terminal `reconciliation_{layer}` task instance of that
  run is `success`.
- Test `test_dq_pass_rate_in_marquez` (AC5): also consumes
  `successful_{layer}_run`, then queries
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

- (2026-07-18): Airflow 3.2.1 standalone uses SimpleAuthManager: REST is
  `/api/v2` on host port 8081, JWT bearer only (basic-auth tuple → 401).
  Token via `POST /auth/token` (server root). Health probe is
  `/api/v2/monitor/health` (unauthenticated). v2 dagRuns POST requires
  `logical_date`.
- (2026-07-18): `POST /auth/token` returns **201 Created** (not 200) on
  Airflow 3.2.1 — the `airflow_token` fixture MUST accept **200 OR 201**
  and only `pytest.skip(...)` on any other status (or a request
  exception). A 200-only check skips every integration test (no token →
  no DAG trigger) against a 201-returning stack.
- (2026-07-19): A layer's integration suite splits across two modules
  (`test_{layer}_uc.py` + `test_{layer}_se_evidence.py`) that pytest
  collects ALPHABETICALLY — `se_evidence` BEFORE `uc`. If the UC module
  triggers its own run (module fixture) and the evidence module
  independently scans for "latest successful run", the evidence test runs
  FIRST and can latch a STALE prior run (e.g. a `prestart-*` run with no
  terminal `reconciliation_{layer}` task) → `reconciliation_{layer} state
  is None`. Fix: a SHARED session-scoped `successful_{layer}_run` fixture
  in the conftest that reuses a recent success (parse `end_date`, ~45-min
  window) or else unpauses + triggers + polls; EVERY layer test consumes
  it. This makes collection order irrelevant. Do NOT keep any per-module
  trigger or per-module latest-successful scan once the shared fixture
  exists.
