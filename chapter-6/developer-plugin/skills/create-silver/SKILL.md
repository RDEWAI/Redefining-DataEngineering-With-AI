---
name: create-silver
description: >
  Generates the Silver layer of the Patient 360 Medallion pipeline from the
  approved LLD, DMS, STM, DQS, and a given story or epic. Emits per-table
  PySpark transformation modules (SCD2 dimensions + cleansed facts), the
  shared SCD2 helper, per-table contracts, per-table Spark Expectations DQ
  rule files, unit tests, and the DAG wiring for the `silver_dimensions`
  and `silver_facts` task groups.

  Modes:
  - Story mode: read a STORY-NN-NNN, extract backtick-quoted deliverables
    from its Acceptance Criteria, generate only those that fall under the
    Silver layer (modules under `src/patient_360/silver/`, contracts/dq
    files for silver-prefixed tables, tests under `tests/silver/`).
    ROUTE-OUT any deliverable that lives in another layer.
  - Full mode: process every un-Done story classified as `silver`,
    topo-sorted by Depends On, until the Silver layer is complete.

  Project-agnostic: the table list, SCD2 dimension designation, hash
  column list, per-table DQ rule filenames, and module names are ALL read
  from the current run's LLD §5.2, DMS §3, STM Bronze-to-Silver sheet,
  and DQS §2 at runtime. No project identifiers or story IDs are hardcoded.

  Use when the user asks to:
  - Generate or update Silver layer code for a story or epic
  - Build the SCD2 helper and per-table Silver transform modules
  - Wire the silver_dimensions / silver_facts task groups into the DAG
argument-hint: "[STORY-NN-NNN | EPIC-NN | 'full']"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create Silver Layer

You are a senior Data Engineer building the Silver layer of a Medallion
pipeline. Your job is to translate LLD §2.3 (Module Interface Contracts),
§5.2 (Silver Tasks), DMS §3 (Silver Schemas), STM Bronze-to-Silver mapping,
and DQS §2 (field-level rules) into production-ready Silver code.

The LLD + DMS + STM + DQS are the single source of truth. Never invent
paths, tables, columns, hash columns, or rule IDs — every name must already
exist in those upstream artifacts. The output must be config- and
metadata-driven, not hard-coded.

## Workspace Discovery

Before any file operation, resolve the chapter-6 workspace and the
upstream chapter-4 artifact roots:

```bash
WORKSPACE_ROOT="$(cd "$(dirname "${CLAUDE_PLUGIN_ROOT:-.}")" && pwd)"
# WORKSPACE_ROOT now points at the chapter-6 directory.
PROJECT_ROOT="$WORKSPACE_ROOT/patient_360"
UPSTREAM_ROOT="$(cd "$WORKSPACE_ROOT/../chapter-4" && pwd)"
STORIES_ROOT="$(cd "$WORKSPACE_ROOT/../chapter-5" && pwd)"
LEARNINGS_QUEUE="$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl"
```

The Silver plugin reads:
- **LLD / DMS / STM / DQS** from `$UPSTREAM_ROOT/outputs/{lld,dms,stm,dqs}/v*/`
- **Stories** from `$STORIES_ROOT/outputs/stories/v*/`

The Silver plugin writes:
- Transform modules → `$PROJECT_ROOT/src/patient_360/silver/transform_{table}.py`
- Shared SCD2 helper → `$PROJECT_ROOT/src/patient_360/utils/scd2.py`
- Contracts → `$PROJECT_ROOT/contracts/{silver_table}.yml`
- DQ rules → `$PROJECT_ROOT/dq_rules/{silver_table}.yml` (only if not already
  emitted by `dq-engineer-plugin:generate-se-rules`)
- Unit tests → `$PROJECT_ROOT/tests/silver/test_transform_{table}_unit.py`
- DAG wiring → edits to `$PROJECT_ROOT/airflow/dags/patient360_hourly_v1.py`

## Phase 0 — Upstream Approval Gate

The skill MUST refuse to run unless every required upstream artifact is
`Approved`:

| Upstream | Required status | Source |
|---|---|---|
| LLD | Approved | `$UPSTREAM_ROOT/outputs/lld/v*/LLD-*.md` |
| DMS | Approved | `$UPSTREAM_ROOT/outputs/dms/v*/DMS-*.md` |
| STM | Approved | `$UPSTREAM_ROOT/outputs/stm/v*/STM-*.xlsx` (Summary sheet) |
| DQS | Approved | `$UPSTREAM_ROOT/outputs/dqs/v*/DQS-*.md` |
| Stories | Approved | `$STORIES_ROOT/outputs/stories/v*/BACKLOG-*.md` |

For each upstream, locate the latest version folder via
`ls -d $UPSTREAM_ROOT/outputs/{art}/v* | sort -V | tail -1`, read the most
recent non-`.bak` file, and check the `Status` field in the metadata
block (or, for the STM, the `Status` cell in the Summary sheet).

If any upstream is not `Approved`, stop and report:

```
CRITICAL: Cannot run create-silver — upstream not approved.
  LLD: <status>
  DMS: <status>
  ...
Approve the missing upstream(s) via the corresponding `/approve-*` skill
and re-run.
```

## Phase 1 — Read Upstream Artifacts

1. **LLD §5.2 (Silver Tasks)** — extract the table of 13 Silver tasks. For
   each row capture:
   - Task ID (`transform_<table>_silver`)
   - Module Path (`src/patient_360/silver/transform_<table>.py`)
   - Contract file (`contracts/<silver_table>.yml`)
   - DQ Rules file (`dq_rules/<silver_table>.yml`)
   - Input Bronze path (`warehouse/{env}/bronze/<bronze_table>/`)
   - Output Silver path (`warehouse/{env}/silver/<domain>/<silver_table>/`)
   - Empty-input behavior (`Fail task` vs `Write empty`)
   - DQ rule range (e.g., DQ-FLD-046 to DQ-FLD-059)

2. **LLD §2.3 — SCD2 utility contract** — confirm the signature for
   `src/patient_360/utils/scd2.py::apply_scd2(df, natural_keys, hash_columns,
   effective_date)`.

3. **DMS §3 (Silver Schemas)** — for each Silver table, extract the column
   list and types (the DMS, NOT the source, owns Silver column contracts).
   Identify which 4 tables are SCD Type 2 (per LLD §5.2 notes):
   `clinical_patients`, `reference_organizations`, `reference_providers`,
   `reference_payers`. For each SCD2 table also extract the **hash column
   list** from DMS §6.

4. **STM Bronze-to-Silver sheet** — for each Silver table, extract the
   transformation rules: column renames, casts, derived fields, code-system
   lookups, null-handling. Cite the row number in generated transform
   modules.

5. **DQS §2 (field-level Silver rules)** — locate the `DQ-FLD-NNN` IDs
   that apply to each Silver table. Confirm the per-table YAML files
   already exist at `$UPSTREAM_ROOT/outputs/dqs/v*/se-rules/<silver_table>.yaml`
   (emitted by `dq-engineer-plugin:generate-se-rules`); if any are missing,
   stop with:

   ```
   CRITICAL: dq_rules/<silver_table>.yml missing for table <table>.
   Run /dq-engineer-plugin:generate-se-rules first.
   ```

6. **Stories / Story arg** — if `$ARGUMENTS` is `STORY-NN-NNN` or `EPIC-NN`,
   read that file from `$STORIES_ROOT/outputs/stories/v*/EPIC-NN-.../`,
   extract Acceptance Criteria backtick-quoted deliverables, and intersect
   with the Silver scope. Skip deliverables outside Silver and emit a
   ROUTE-OUT note for each.

## Phase 2 — Emit Shared SCD2 Helper (idempotent)

If `$PROJECT_ROOT/src/patient_360/utils/scd2.py` does not already exist,
emit it using the LLD §2.3 contract with the deviation noted in
`chapter-6/silver-gold-plugin/LLD-DEVIATIONS.md` — the LLD's published
signature is missing a `target_path` parameter, without which the function
cannot locate the Delta table to merge into. Use the adjusted signature:

```python
def apply_scd2(
    df: DataFrame,
    target_path: str,
    natural_keys: list[str],
    hash_columns: list[str],
    effective_date,
) -> dict[str, int]:
    """Generic SCD Type 2 merge.

    Caller is responsible for running DQ checks BEFORE invoking this
    function — the SCD2 helper trusts every row it receives.

    Returns: {"rows_inserted": int, "rows_closed": int, "rows_unchanged": int}
    """
```

Implementation requirements:

- `spark = df.sparkSession` (derived internally; not a parameter)
- Compute `record_hash` as `sha2(concat_ws("|", *hash_columns), 256)` on the
  source side before the merge
- Use Delta `MERGE INTO` against `target_path` with:
  - `WHEN MATCHED AND target.is_current = TRUE AND target.record_hash <> source.record_hash`
    → set `target.is_current = FALSE`, `target.expiry_date = effective_date - 1`
  - `WHEN NOT MATCHED` → insert with a new `surrogate_key`,
    `effective_date = <param>`, `expiry_date = NULL`, `is_current = TRUE`,
    `record_hash = <computed>`, `dw_created_at = current_timestamp()`,
    `dw_updated_at = current_timestamp()`
- Surrogate-key generation MUST be deterministic across runs — use
  `xxhash64(natural_key, effective_date)` or read the current max from the
  target and increment; do NOT use `monotonically_increasing_id()` (not
  stable across re-runs)
- Return a metrics dict by reading `DESCRIBE HISTORY` for the last
  operation; the caller emits these via OpenTelemetry per LLD §5.4

Emit a unit test stub at `tests/silver/test_scd2_unit.py` covering:
- New record (no match) → insert path
- Changed record (match + hash differs) → close + insert path
- Unchanged record (match + hash equal) → no-op path
- DQ contract: the helper MUST NOT call `run_dq` — assert that the test's
  mock for `run_dq` is never invoked from within `apply_scd2`

## Phase 3 — Generate Per-Table Silver Transform Modules

For each Silver table in LLD §5.2 (13 modules), emit
`$PROJECT_ROOT/src/patient_360/silver/transform_<table>.py` following this
structure:

```python
"""Silver transform: <bronze_table> -> <silver_table>.

LLD: §5.2 row <NN>
STM: Bronze-to-Silver row <NN>
DMS: §3.<NN> <silver_table> schema
DQS: <DQ-FLD-NNN> .. <DQ-FLD-MMM>
"""

from pathlib import Path

import yaml
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

from patient_360.utils.se_runner import run_dq
from patient_360.utils.delta_helpers import read_bronze_delta, write_silver_delta
from patient_360.utils.pipeline_config import load_pipeline_config
# SCD2-only import; omit for cleansed-fact transforms
from patient_360.utils.scd2 import apply_scd2  # noqa: F401  (SCD2 only)

TABLE = "<silver_table>"
DOMAIN = "<clinical|billing|reference>"


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    cfg = load_pipeline_config(env)
    bronze_df = read_bronze_delta(spark, table="<bronze_table>", ds=ds, env=env)

    # STM Bronze-to-Silver transformations (rename, cast, derive, lookup, null-handle)
    silver_df = (
        bronze_df
        # ... per STM row N
    )

    # Inline SE BEFORE write — row_dq + agg_dq from dq_rules/<silver_table>.yml
    # action_if_failed is the SE failure response, NOT the empty-input policy
    # (those are two distinct gates — see LLD-DEVIATIONS.md #2).
    validated_df, _quarantine = run_dq(
        df=silver_df,
        table=TABLE,
        env=env,
        action_if_failed="<fail|drop|ignore>",   # from DQS §1 per-rule severity
        dq_rules_dir=Path(cfg["paths"]["dq_rules"]),
    )

    target_path = f"{cfg['paths']['silver']}/{DOMAIN}/{TABLE}"

    # SCD2 dims: MERGE INTO via the shared helper. Helper trusts validated rows.
    if <is_scd2>:
        metrics = apply_scd2(
            df=validated_df,
            target_path=target_path,
            natural_keys=[<natural_keys>],
            hash_columns=[<hash_columns_from_dms_section_6>],
            effective_date=ds,
        )
        # metrics: {"rows_inserted": int, "rows_closed": int, "rows_unchanged": int}
        # caller emits via OpenTelemetry per LLD §5.4 step 8

    # Cleansed facts: overwrite the ds partition (append + replaceWhere)
    else:
        write_silver_delta(validated_df, table=TABLE, domain=DOMAIN, ds=ds, env=env)

    return validated_df
```

**Hard rules**:
- Never reorder STM steps — preserve the source row order so traceability holds.
- Never invent columns. Every column in the output must come from DMS §3 for
  this table.
- The `action_if_failed` value is determined by LLD §5.2 column “DQ Check”:
  `fail` for patients, encounters, allergies, FK dimensions; `drop` for
  non-critical clinical tables; `ignore` for warnings only.
- For SCD2 dims, `apply_scd2` is the ONLY write path — never call
  `write_silver_delta` for SCD2 tables.
- Each module ends with a `return validated_df` so unit tests can assert on
  the row count and schema independently of the write.

## Phase 4 — Generate Per-Table Contracts and DQ Pointers

For each Silver table emit:

1. `$PROJECT_ROOT/contracts/<silver_table>.yml`:

   ```yaml
   table: <silver_table>
   layer: silver
   domain: <clinical|billing|reference>
   owner: <team-from-DMS>
   tags: [<from-DMS-section-3>]
   schema:
     - {name: <col>, type: <dms-type>, nullable: <true|false>, description: <dms-desc>}
     # one row per column from DMS §3
   ddl_path: ddl/liquibase/changelogs/<silver_table>.xml
   dq_path: dq_rules/<silver_table>.yml
   ```

2. `$PROJECT_ROOT/contracts/dq/<silver_table>.yml` (thresholds pointer):

   ```yaml
   table: <silver_table>
   layer: silver
   dq_rules_ref: dq_rules/<silver_table>.yml
   thresholds:
     completeness_min: <from-DQS-section-1>
     validity_min:     <from-DQS-section-1>
     freshness_max_hours: <from-DQS-section-1>
   ```

3. `$PROJECT_ROOT/dq_rules/<silver_table>.yml` — copy from
   `$UPSTREAM_ROOT/outputs/dqs/v*/se-rules/<silver_table>.yaml` verbatim.

## Phase 5 — Generate Unit Tests

For each transform emit
`$PROJECT_ROOT/tests/silver/test_transform_<table>_unit.py` covering:

- Schema invariant: output columns equal the DMS §3 column list
- Row-level transformations: at least one positive and one negative case
  per STM transformation rule
- SCD2 dims only: tested separately in `test_scd2_unit.py`; the per-table
  test must still verify that `apply_scd2` is called with the documented
  natural-key / hash-column tuple
- DQ gate: mock `run_dq` and assert it is invoked with the table-specific
  `action_if_failed`
- Empty input: covers the LLD §5.2 declared behavior (`fail` raises,
  `write_empty` returns an empty DataFrame with the right schema)

## Phase 6 — Wire the DAG Task Groups

Edit `$PROJECT_ROOT/airflow/dags/patient360_hourly_v1.py`:

1. Add a `silver_dimensions` TaskGroup containing the 4 SCD2 dim tasks
   (`clinical_patients`, `reference_organizations`, `reference_providers`,
   `reference_payers`).
2. Add a `silver_facts` TaskGroup containing the 9 cleansed-fact tasks.
3. Set the dependency edge:
   `bronze_ingestion >> reconciliation_bronze >> [silver_dimensions, silver_facts] >> reconciliation_silver`.
4. Each Silver task is a `SparkSubmitOperator` pointing at the per-table
   transform module (use the same wrapper as Bronze).

Do not duplicate Bronze ingestion or `reconciliation_bronze` — they
already exist from chapter-5 `developer-plugin:create-ingestion` /
`create-dag`. The edit is additive only.

## Phase 7 — Verify and Report

Run the in-plugin validator:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-silver/scripts/validate_silver.py \
  --project-root "$PROJECT_ROOT" \
  --lld "$(ls -t "$UPSTREAM_ROOT"/outputs/lld/v*/LLD-*.md | grep -v '\.bak$' | head -1)" \
  --dms "$(ls -t "$UPSTREAM_ROOT"/outputs/dms/v*/DMS-*.md | grep -v '\.bak$' | head -1)"
```

Report:
- ✅ N modules emitted, M contracts emitted, K tests emitted
- ❌ Any LLD §5.2 row that did not produce a module (with reason)
- 🛣  ROUTE-OUT items: deliverables in the story that belong to other layers

## Learnings & Corrections

Meta-rules for adding learnings to this skill:

- Append every user correction during a session to
  `chapter-6/memory/developer/learnings-queue.jsonl` as a JSON line:
  `{"skill": "create-silver", "date": "YYYY-MM-DD", "correction": "...", "pattern": "...", "status": "pending"}`
- At session end, if pending entries exist, run
  `/silver-gold-plugin:apply-learnings` before finishing.

### Inherited Learnings (from chapter-5/memory/developer/learnings-queue.jsonl)

These rules were learned the hard way while building the chapter-5 Bronze
layer. They apply unchanged to Silver transforms because the runtime stack
(PySpark + Delta + Spark Expectations + Airflow 3.x + UC OSS UI-only) is
identical. NEVER violate them in emitted Silver code without an explicit
LLD waiver.

**Spark / Delta runtime**

- **IL-001** NEVER pin `pyspark==4.0.0` — that exact release has a
  `_start_update_server` arity regression that breaks every SparkSession
  boot. Pin `pyspark>=4.0.2,<4.1` (last 4.0 patch) or `==4.1.1` if the LLD
  permits the 4.1 line. Verify with a one-line throwaway `SparkSession.builder…getOrCreate().stop()`
  before emitting the pin.
- **IL-002** NEVER wire `spark.sql.catalog.spark_catalog` to
  `UCSingleCatalog` for local-FS dev. Use `DeltaCatalog`
  (`org.apache.spark.sql.delta.catalog.DeltaCatalog`) plus Spark's built-in
  Hive metastore. UC OSS may run for UI/lineage only — never as the Spark
  catalog. (See LLD §13 Decisions 12 + 15, both Revoked 2026-05-12.)
- **IL-003** ALWAYS set `spark.sql.catalogImplementation=hive` AND
  `spark.hadoop.javax.jdo.option.ConnectionURL='jdbc:derby:;databaseName=<stable-path>;create=true'`
  so the Derby metastore survives across `spark-submit` boots. Each task
  otherwise boots a fresh in-memory catalog and `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`
  fires on the second run.
- **IL-004** ALWAYS use 2-part FQNs (`<schema>.<table>`) in writer and
  query code; `spark_catalog` is the default catalog and 3-part FQNs raise
  `REQUIRES_SINGLE_PART_NAMESPACE` once UC is dropped.
- **IL-005** ALWAYS anchor relative YAML paths (contracts_dir,
  dq_rules_dir, source.path) against the `PATIENT360_PROJECT_ROOT` env
  var. The Airflow worker CWD is `/opt/airflow`, not the project root —
  every relative path that resolves against CWD will break in container.
- **IL-006** NEVER use `monotonically_increasing_id()` for SCD2 surrogate
  keys — it is non-deterministic per executor and per run. Use
  `xxhash64(natural_key, effective_date)` OR read `max(surrogate_key)`
  from the target and increment with `row_number()`.

**Spark Expectations (Silver inline DQ)**

- **IL-007** ALWAYS wrap the input DataFrame in a no-arg lambda for SE's
  decorator API: `decorated = se.with_expectations(...)(lambda: df);
  validated = decorated()`. Calling `se.with_expectations(...)(df)` returns
  a function (not a DataFrame) and silently breaks `.write`.
- **IL-008** spark-expectations ALWAYS writes a stats table — there is no
  disable flag. Make sure the metastore accepts `saveAsTable` from SE
  (Hive/Derby works; UCSingleCatalog does not — see IL-002).
- **IL-009** Reconciliation queries MUST filter on `meta_dq_run_date = ds`,
  NOT `meta_dq_run_id`. SE generates `meta_dq_run_id` internally and does
  not accept an external override. The contract is "DQ ran for today's
  data", not "DQ ran for this exact Airflow run".
- **IL-010** ALWAYS wrap `from patient_360.utils import se_runner` in a
  diagnostic `try/except ImportError` that re-raises after logging. This
  pattern is REQUIRED by LLD §8.6 + §13 Decision 14 — NEVER swallow the
  ImportError; NEVER omit the wrapper once `se_runner.py` ships.

**Airflow 3.x (DAG wiring for `silver_dimensions` / `silver_facts`)**

- **IL-011** Every task that touches Spark MUST be a `SparkSubmitOperator`
  (separate JVM). NEVER use `PythonOperator` with `build_spark_session`
  inside the callable — Airflow 3.x task-SDK collides with py4j subprocess
  management and produces `_start_update_server() missing 1 required
  positional argument: 'is_unix_domain_sock'`.
- **IL-012** Airflow 3.x's `SparkSubmitOperator` dropped the `driver_cores`
  kwarg. Forward the value via `spark.driver.cores` in the `conf` dict
  instead.
- **IL-013** TaskGroup factories MUST resolve the active DAG via
  `airflow.sdk.definitions._internal.contextmanager.DagContext.get_current()`
  and pass `dag=` explicitly. The pre-3.x pattern of passing `dag=None` and
  relying on TaskGroup contextual binding fails eagerly under 3.x.
- **IL-014** Dev DAG defaults: `max_active_tasks=1`, `catchup=False`.
  Concurrent tasks race on the shared `bronze_se_stats` CREATE; backfill
  avalanche piles up scheduled runs and orphan Delta files. Production
  raises these only after the SE stats table is seeded.
- **IL-015** DEV compute defaults: 1g driver / 1g executor / shuffle
  partitions = 4 / broadcast threshold = 10m. Larger Silver inputs (e.g.
  observations) may need overrides — document the trade-off in the
  per-table YAML, not at the cluster level.

**Story-driven orchestration (when invoked via implement-stories)**

- **IL-016** Validator findings MUST be intersected with the current
  task's `.skill-paths` set before halting. NEVER halt the current story
  on a CRITICAL that names a path owned by a sibling story or a project-
  wide pre-existing failure.
- **IL-017** When a story AC glob conflicts with the LLD / project
  convention (e.g. `dq_rules/synthea_*.yml` vs `dq_rules/{table}.yml`),
  HALT the story and recommend `scrum-master:update-stories` — NEVER
  project-wide rename to match the AC.

### Active Learnings

<!-- New L-NNN entries get appended below by apply-learnings. Keep absolute
     directives ("MUST" / "NEVER") so they survive context-window pressure.
     Inherited entries (IL-NNN) live in their own block above and are
     never renumbered. -->

(no chapter-6-specific learnings yet)
