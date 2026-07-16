---
name: create-gold
description: >
  Generates the Gold layer of the Patient 360 Medallion pipeline from the
  approved LLD §2.3 / §5.3, DMS §4, STM Silver-to-Gold sheet, DQS §2-3
  (Gold rules), and a given story. Emits PySpark builder modules for the
  Gold consumer tables declared in LLD §5.3 (currently `patient_summary`,
  `patient_clinical_history`, `patient_billing_summary` — derived at
  runtime, not hardcoded), per-table contracts, per-table Spark
  Expectations DQ rule files, unit tests, and the DAG wiring for the
  `gold_build` task group.

  Modes:
  - Story mode: STORY-NN-NNN — emit only Gold deliverables in scope
  - Full mode: process every un-Done story classified as `gold`,
    topo-sorted by Depends On, until the Gold layer is complete

  Project-agnostic: the table list, source-table joins, business-invariant
  DQ rules, and module names are ALL read from the LLD §5.3, DMS §4, STM
  Silver-to-Gold sheet, and DQS §2-3 at runtime.

  Use when the user asks to:
  - Generate or update Gold layer code for a story or epic
  - Build the Gold consumer tables (patient_summary, etc.)
  - Wire the gold_build TaskGroup into the DAG
argument-hint: "[STORY-NN-NNN | EPIC-NN | 'full']"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create Gold Layer

You are a senior Data Engineer building the Gold layer of a Medallion
pipeline. Your job is to translate LLD §5.3 (Gold Tasks), DMS §4 (Gold
Schemas), STM Silver-to-Gold mapping, and DQS §2-3 (Gold rules) into
production-ready builder modules.

This skill carries **no inline pipeline code**. Every module it emits is
rendered from the reference template
`inputs/code/v*/scripts/gold_builder.py.snippet` and the prose
`inputs/code/v*/gold-aggregation-pattern.md`, filled in from the upstream
artifacts. The LLD + DMS + STM + DQS are the single source of truth: every
join, column, and rule MUST already exist upstream — never invent.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. Never hardcode
project or chapter names in edits.

Writes (substitute the discovered tokens):
- Builders → `{project_root}/src/patient_360/gold/build_<table>.py`
- Contracts → `{project_root}/contracts/<gold_table>.yml` (+ DQ pointer under `contracts/dq/`)
- DQ rules → `{project_root}/dq_rules/<gold_table>.yml`
- Unit tests → `{project_root}/tests/gold/test_build_<table>_unit.py`
- DAG edits → `{project_root}/airflow/dags/patient360_hourly_v1.py`

## Coding Patterns & Libraries Handbook

Before generating any builder, load the latest coding-patterns handbook:

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required references for this skill (read, do not re-derive):**

- `$PATTERNS_DIR/scripts/gold_builder.py.snippet` — the authoritative builder template (render one per LLD §5.3 row)
- `$PATTERNS_DIR/gold-aggregation-pattern.md` — the Gold pattern (full-overwrite insertInto, natural-key current-state joins, DQ-before-write)
- `$PATTERNS_DIR/naming-conventions.md` — module/table/task naming
- `$PATTERNS_DIR/LIBRARIES.md` — pinned PySpark / Delta / Spark-Expectations versions

**Library freshness check** — compute the age of `LIBRARIES.md`
`last_verified:` against today; if `> 30` days, pause and call
`AskUserQuestion` with `Refresh now` / `Proceed with cached versions` /
`Cancel`. On Refresh, invoke `/developer-plugin:refresh-libraries` then
resume.

## Phase 0 — Resolve the Effective Argument

The Skill-tool argument frequently fails to reach forked subagents. Resolve
the target via the shared resolver, which checks four sources in order:
`$SKILL_ARG` → `{workspace_root}/.skill-arg` → conversational arg → auto-mode.

```bash
CONV_ARG='<<EXACT_CONVERSATIONAL_TEXT_FROM_USER_OR_EMPTY_STRING>>'
read -r RESOLVED_ARG RESOLVED_SOURCE < <(
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_skill_arg.sh" "$CONV_ARG" | paste -sd' ' -
)
```

Print this banner as the **first line** of skill output:
`RESOLVED TARGET: <value> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__>)`.
Use `$RESOLVED_ARG` (NOT `$ARGUMENTS`) everywhere below. If it is `__AUTO__`
or empty/an `.md` path, treat it as **full mode**. If `$RESOLVED_SOURCE == EMPTY`,
fall through to `AskUserQuestion`. DO NOT ask the user before running the resolver.

## Phase 0.4 — Upstream Approval Gate

Resolve upstream versions via the shared helper (uses `outputs/dev-lock.yaml`
when present, else latest `v{N}`):

```bash
eval "$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --export)"
```

Refuse to run unless **LLD, DMS, STM, DQS, and Stories** are all
`Approved`. The Silver layer is upstream of Gold: Silver tables must
already exist at `warehouse/{env}/silver/<domain>/<table>/` and the Silver
story must be `Done`. (Silver contracts carry no `Status` field, so gate on
the Silver story status + table presence, not a contract "Approved" flag.)
If any upstream is missing, stop with a `CRITICAL` message naming each
unapproved artifact or missing Silver table.

## Phase 0.5 — Path Scoping (optional, set by the orchestrator)

If `{workspace_root}/.skill-paths` exists, read it — each non-empty line is
a path in scope for THIS invocation. Process ONLY those paths; ignore other
paths the story AC names (they belong to other skills and the orchestrator
dispatches them separately). Delete `.skill-paths` after consuming it. When
the file is absent (direct human invocation), fall through to the standard
phases that scan every candidate deliverable against the Gold Domain of
Ownership.

## Phase 1 — Read Upstream Artifacts

1. **LLD §5.3 (Gold Tasks)** — derive the full Gold task list from the
   §5.3 table at runtime; do NOT hardcode the count or names. Each row
   gives the Module Path, Contract File, DQ Rules File, Inputs (Silver
   tables to read), Output (`unity.gold.<table>`), Transform Ref (STM
   sheet), and empty-input behavior (Fail task). Join keys are **per the
   STM Silver-to-Gold sheet** — dimensions join on their natural key
   (`patient_id`, `provider_id`, `organization_id`, `payer_id`); there is
   no surrogate FK. Never assume a fixed `patient_id` join for every row.
2. **DMS §4 (Gold Schemas)** — the column list + types per Gold table.
   Gold schemas are fenced YAML (`table:` / `columns:`) blocks in DMS §4,
   not markdown pipe tables. This is the `OUTPUT_COLUMNS` order.
3. **STM Silver-to-Gold sheet** — per-Gold-table transformation rules
   (joins, aggregations, derived columns, code-system lookups), in row order.
4. **DQS Gold rules** — the `DQ-FLD-NNN` IDs that apply to each Gold table
   (e.g. DQ-FLD-105..DQ-FLD-140 for patient_summary). Verify the per-table
   SE-rules YAML exists at
   `{workspace_root}/outputs/dqs/v*/se-rules/se-rules-<gold_table-hyphenated>.yaml`
   (hyphenated upstream, e.g. `se-rules-patient-summary.yaml`).

**Schema-name reconciliation (do not silently merge):** LLD §5.3, the
stories, and the DDL migrations target `unity.gold.*`. The DMS §4 / DQS §2
`analytics` schema name is **stale** — treat `unity.gold` as authoritative
and, if the divergence is material, recommend a `data-modeler:update-dms` /
`dq-engineer:update-dqs` cycle rather than inventing a merged schema.

## Phase 2 — Generate Per-Table Gold Builder Modules

For each Gold table declared in LLD §5.3, render
`{project_root}/src/patient_360/gold/build_<table>.py` **from**
`$PATTERNS_DIR/scripts/gold_builder.py.snippet`, consulting
`$PATTERNS_DIR/gold-aggregation-pattern.md`. Fill the template placeholders
from the upstream artifacts read in Phase 1:

- `<gold_table>` / module path ← LLD §5.3
- `OUTPUT_COLUMNS` ← DMS §4 `columns:` block, in order
- Silver reads ← LLD §5.3 Inputs column (SCD2 dims via the current-state
  read helper on the natural key; plain facts via `spark.table(...)`)
- Joins + aggregations ← STM Silver-to-Gold rows, preserving row order
- `dq_rules/<gold_table>.yml` ← DQS §2-3 range for the table
- Docstring ← cite LLD §5.3 row / STM row / DMS §4 subsection / DQS range

**Hard rules (the template already encodes these — verify, never weaken):**

- **Full-overwrite `insertInto` into the pre-created EXTERNAL Delta table**:
  `df.write.mode("overwrite").insertInto("unity.gold.<table>")`. NEVER
  `.save(path)`, `saveAsTable`, `partitionBy`, `CREATE TABLE`,
  `createOrReplace*`, or any catalog DDL at runtime (LLD §3.3 / Decision 15;
  stories' `forbidden_grep`). `OUTPUT_COLUMNS` and the `insertInto` are
  **positional against the DMS §4 schema** — add a `ds`/build-stamp column
  ONLY if DMS §4 lists one for this table; omit it otherwise (an extra column
  breaks the insert arity). Most consumer tables (e.g. `patient_summary`) have
  no `ds` column. A `ds`, when present, is a build stamp, never a partition.
- **Keep the generated builder's comments free of the `forbidden_grep`
  literals.** The story AC `forbidden_grep` is a plain regex over the whole
  `build_*.py` file, so the literal writer-method names and
  `.save(...warehouse...)` trip it **even inside comments**. State the
  prohibition in words; do not paste the banned tokens into the module.
- **`run_dq` returns a SINGLE validated DataFrame, keyword-only**
  (`validated_df = se_runner.run_dq(df=..., table=..., env=..., action_if_failed=..., dq_rules_dir=None)`).
  It is NOT a tuple — do not write `validated_df, _ = run_dq(...)`. The DQ
  gate runs BEFORE the write; write the returned frame.
- **Gold has NO SCD2** — Gold tables are rebuilt each run. Never import or
  call `apply_scd2` from a Gold builder.
- **Every SCD2 dimension read filters `F.col("is_current") == True`** and
  joins on the dimension's NATURAL key (current-state Gold report, LLD §5.2
  SCD2 implications). A historical Gold report would use the
  `effective_from`/`effective_to` range-overlap form instead.
- **Empty required Silver input → Fail the task** (LLD §5.3 empty-input =
  Fail; the template raises). Gold never writes an empty consumer table.
- Joins follow STM Silver-to-Gold row order; never reorder for
  "performance" without an LLD §6 entry authorizing it.

## Phase 3 — Generate Contracts and DQ Pointers

Same mechanism as `create-silver` Phase 4, with `layer: gold` (see that
skill for the contract + DDL migration structure — do not paste code here):

- `contracts/<gold_table>.yml` — schema column list from DMS §4 (`columns:`
  block); `ddl_path` → the dated `ddl/migrations/*_3<NN>_<gold_table>.sql`;
  `dq_path` → `dq_rules/<gold_table>.yml`.
- `contracts/dq/<gold_table>.yml` — thresholds pointer. Read the actual
  values from the DQS Gold SE-rules that apply to each table; copy the
  upstream thresholds verbatim — never pin a placeholder like
  `completeness_min: 0.99`.
- Hydrate the stubbed `ddl/migrations/*_3<NN>_<gold_table>.sql` business
  columns from DMS §4 if still stubbed (or route to
  `update-scaffold sync-contracts`).

`dq_rules/<gold_table>.yml` carries only the `rules:` subtree plus the
`dq_env` block. **`dq_env.<ENV>.table_name` MUST be the fully-qualified
`unity.gold.<table>`** (3-part) — it is the SE rule-filter key (must equal
the `target_table` passed to `with_expectations`) and the base for the
managed `<target>_error`/`_stats` FQNs. A bare name triggers the UC
empty-namespace `fullTableNameForApi` AIOOBE on the error-table write.

## Phase 4 — Generate Unit Tests

For each builder, emit
`{project_root}/tests/gold/test_build_<table>_unit.py` covering:

- Schema invariant: output columns match DMS §4
- Join correctness: one positive and one orphan case per STM join rule
- `is_current=True` filter is applied for every SCD2 dim read
- `run_dq` mocked + asserted (env-resolved action; under PROD → `fail`)
- Empty Silver input → task fails (LLD §5.3 Fail-task empty-input behavior)

## Phase 5 — Wire the DAG

### 5.1 Generate the Gold SparkSubmit entry shim

The `gold_build` SparkSubmitOperators need an `application=` target: a
parameterised `--table` entry shim that builds the SparkSession and calls
`{project}.gold.build_<table>.build(spark, env, ds)`. Bronze uses the
`run_layer_entrypoint.py.j2` template, but that template renders a shim that
importlib-imports ONE fixed runner module and calls `entry_function(args)`
(the argparse Namespace) — it CANNOT express table-parameterised module
selection, the in-shim SparkSession build, or the `(spark, env, ds)` call
shape the Gold/Silver builders use. Silver solved this with a dedicated shim
(`run_silver_transform.py`); Gold mirrors it.

Render `{project_root}/airflow/jobs/run_gold_build.py` **from**
`$PATTERNS_DIR/scripts/run_gold_build.py.snippet` (modeled on
`run_silver_transform.py`), substituting the discovered `{project_name}`
token and filling `GOLD_TABLES` (the `--table` allow-list) with one bare
OUTPUT table name per LLD §5.3 Gold row. Do NOT re-render the j2 template for
Gold — the snippet is the authoritative source for this shim.

### 5.2 Edit the DAG

Edit `{project_root}/airflow/dags/patient360_hourly_v1.py`:

1. Add a `gold_build` TaskGroup containing exactly the builder tasks
   declared in LLD §5.3, mirroring the existing `silver_facts` TaskGroup
   (one `SparkSubmitOperator` per table; `conf=build_spark_conf({})`;
   `packages`; `application_args=["--table", <table>, "--ds", "{{ ds }}"]`).
   The `application=` resolves from a `GOLD_BUILD_APP` env var falling back
   to the container path of `run_gold_build.py` (same env-indirection the
   silver `SILVER_TRANSFORM_APP` uses — never hardcode an absolute path).
   The DAG owns the LLD §5.4 table→task_id map (e.g. `patient_summary` →
   `build_patient_summary_gold`, `patient_clinical_history` →
   `build_clinical_history_gold`, `patient_billing_summary` →
   `build_billing_summary_gold`) — the task ids are NOT a uniform
   `build_<table>_gold` f-string, so wire them from an explicit map.
2. Set the dependency edge:
   `reconciliation_silver >> gold_build >> reconciliation_gold`.
3. Each builder is a `SparkSubmitOperator` (IL-011) pointing at
   `run_gold_build.py` (see `$PATTERNS_DIR/scripts/dag_factory.py.snippet`
   for the generic task-wiring reference; the concrete pattern to mirror is
   the in-DAG `silver_facts` TaskGroup).

**Endpoint-existence rule for the §5.4 edge (do NOT invent nodes).**
`reconciliation_silver` and `reconciliation_gold` are separate tasks NOT
owned by this skill (create-gold owns `gold_build` only, exactly as
create-silver owns `silver_dimensions`/`silver_facts` but NOT
`reconciliation_silver`). Wire each edge only against a node that already
exists in the DAG:

- If `reconciliation_silver` exists as a node, wire
  `reconciliation_silver >> gold_build`. If it does not (its owning story /
  `run_silver_recon.py` shim not yet implemented), gate `gold_build` on the
  existing silver terminal state instead — `[silver_dims, silver_facts] >>
  gold_build` — so Gold still runs only after ALL Silver completes (which is
  what `reconciliation_silver` would gate), and leave a NOTE that the edge
  should be re-pointed to `reconciliation_silver >> gold_build` once that
  node is wired. Reference the silver groups ONLY as upstream anchors; never
  modify their internals.
- If `reconciliation_gold` exists as a node, wire
  `gold_build >> reconciliation_gold`. If a **gold-reconciliation story is in
  scope for this run** (its AC backtick-quotes `gold/reconciliation.py` +
  `run_gold_recon.py`), generate the node via **Phase 5.3** below and wire
  `gold_build >> reconciliation_gold`. If NO gold-reconciliation story is in
  scope (the `emit_lineage` / `emit_metrics` observability tasks remain owned
  by their own stories per LLD §4.2), do NOT invent a half-baked recon task.
  Leave a NOTE naming `reconciliation_gold` + the observability tasks as
  not-yet-wired with the reason, and REPORT them as such. (The NOTE keeps the
  `reconciliation_gold` / `reconciliation_silver` identifiers present in the
  DAG source for traceability.)

The `silver_dimensions` / `silver_facts` task groups must already exist
(from `create-silver`); if missing, stop with a CRITICAL message asking the
operator to run `create-silver` first.

### 5.3 Generate the Gold reconciliation task (story-scoped)

Run this phase ONLY when a gold-reconciliation story is in scope (its AC
backtick-quotes `src/patient_360/gold/reconciliation.py` +
`airflow/jobs/run_gold_recon.py` + `tests/gold/test_reconciliation_unit.py` and
wires `reconciliation_gold` with the edge `gold_build >> reconciliation_gold`).
`gold_build` remains this skill's primary deliverable; the reconciliation task
is the Gold layer-terminal gate (LLD §4.2 `reconciliation_gold`, §5.5) and is
generated here so the `gold_build >> reconciliation_gold` edge in Phase 5.2 has
a real endpoint.

Where `reconciliation_bronze` proves SE *ran*, `reconciliation_gold` proves
Gold *landed the right rows*. It is NOT a Gold builder (no `insertInto`, no
SCD2) — it mirrors the shape of the Bronze reconciliation runner
`src/patient_360/bronze/reconciliation.py`: same `main(args)` runner contract,
same fail-closed raise, same `run_<layer>_recon.py` SparkSubmit entry shim.

Deliverables (substitute the discovered `{project_root}` / `{project_name}`):

1. **`{project_root}/src/patient_360/gold/reconciliation.py`** — render **from**
   `$PATTERNS_DIR/scripts/gold_reconciliation.py.snippet` (substitute
   `{project}`), modeled on `bronze/reconciliation.py`. It encodes, from the
   upstream artifacts (verify against them — never invent a rule):
   - **Silver-vs-Gold row-count reconciliation** within tolerance, one
     `RowCountRule` per LLD §5.3 Gold table, sourced from **DQS §5
     Reconciliation Rules** + **DQS §4 Statistical Baselines**
     (e.g. DQ-REC-003 `clinical_patients(is_current)` → `patient_summary` ±0.1%;
     DQ-REC-005 `clinical_encounters` → `patient_clinical_history` ±0.1%;
     DQ-STA-019 `clinical_encounters` → `patient_billing_summary` ±5% at the
     encounter grain when a table has only an aggregate DQ-REC rule). The
     SOURCE count is NOT `ds`-scoped — Gold is a full-overwrite rebuild of the
     whole table; SCD2 dim sources filter `is_current = TRUE`.
   - **Patient completeness** — `patient_summary` row count == count of current
     `clinical_patients` == the NFR-4 baseline (`EXPECTED_PATIENT_COUNT`, e.g.
     5,767) and `COUNT(*) == COUNT(DISTINCT patient_id)` (DQ-FLD-106 /
     DQ-REC-010 grain).
   - **Allergy completeness** — the DQ-FLD-138 cross-field predicate
     (`has_allergy` ⇔ non-empty `allergies` array); count violations, require 0.
   - **Schema-name reconciliation** — use `unity.silver.*` / `unity.gold.*`;
     the DQS `unity.clinical` / `unity.analytics` names are stale (Phase 1).
   - Fail-closed: any failing check raises a `GoldReconciliationError` with a
     greppable `GOLD_RECON_FAILED_FOR_DS=<ds>` marker (LLD §5.5 — block
     consumer access; PagerDuty `p360-critical` + Clinical Ops Director for
     allergy failures).
2. **`{project_root}/airflow/jobs/run_gold_recon.py`** — the SparkSubmit entry
   shim. Unlike `run_gold_build.py` (which needs table-parameterised module
   selection and so uses its own snippet), `reconciliation_gold` targets ONE
   fixed runner module, so render this from
   `$PATTERNS_DIR/scripts/run_layer_entrypoint.py.j2` (the same template that
   produced `run_bronze_recon.py`): `task_type=gold_recon`,
   `runner_module={project}.gold.reconciliation`, `entry_function=main`,
   `argv_spec=[{--ds, required}, {--meta-dq-run-id, required}]`.
3. **DAG wiring** — add `reconciliation_gold` as a `SparkSubmitOperator`
   (LLD §4.2 — all Spark-touching tasks; NOT PythonOperator, same
   embedded-Spark classloader constraint as `reconciliation_bronze`), with
   `application=` resolving from a `GOLD_RECON_APP` env var falling back to the
   container path of `run_gold_recon.py` (same env-indirection as
   `GOLD_BUILD_APP`), `application_args=["--ds", "{{ ds }}", "--meta-dq-run-id",
   "{{ ts_nodash }}"]`, and the LLD §4.2 `reconciliation_gold` sizing (20 min
   timeout, 1 retry, 60s fixed backoff). Wire `gold_build >> reconciliation_gold`.
   Leave `emit_lineage` / `emit_metrics` (downstream per LLD §4.2) unwired —
   they are separate observability stories — and NOTE them.
4. **`{project_root}/tests/gold/test_reconciliation_unit.py`** — unit tests
   with a stubbed `spark` (no live session), covering positive reconciliation,
   a tolerance-breach fail, and completeness-fail (patient + allergy) cases,
   mirroring `tests/bronze/test_reconciliation_unit.py`.

## Phase 6 — Verify and Report

1. Run `/developer-plugin:validate-gold`. Fix any CRITICAL before finishing.
2. **Verification Compliance Self-Check (MANDATORY before reporting OK)** —
   the story's `## Verification` block is the contract:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_acs.py STORY-NN-NNN --json
   ```

   For each failing AC with a non-`manual` check, emit one
   `CRITICAL STORY-NN-NNN AC<N>: <spec> — <detail>` line and **stop** (do
   not mark the plan task done, do not print the OK trailer). `manual:`-only
   failures are INFO; missing Verification block is a WARNING. This is the
   only place this skill flips its result from OK to FAILED.
3. Report builders emitted, contracts emitted, tests emitted, the pattern
   docs consulted (e.g. `gold-aggregation-pattern.md`,
   `gold_builder.py.snippet` + LIBRARIES.md vintage), and any LLD §5.3 row
   that did not produce a module (with reason).

## Learnings & Corrections

Meta-rules: append corrections to
`{learnings_queue}`. LLD-bug corrections should be raised via a
`/technical-lead-plugin:update-lld` cycle so the LLD is corrected at source.

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017 — same runtime stack and same
constraints apply to Gold. Note especially IL-004 (2-part vs 3-part FQNs)
and IL-014 (DEV `max_active_tasks=1`) since Gold builders are typically the
heaviest tasks in the DAG.

### Active Learnings

(no skill-specific learnings yet)
