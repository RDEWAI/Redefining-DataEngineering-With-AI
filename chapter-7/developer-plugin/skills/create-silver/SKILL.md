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

Before any file operation, resolve the chapter workspace and the upstream
artifact roots (in the consolidated layout every upstream artifact and the
stories live under the workspace's own `outputs/`):

```bash
WORKSPACE_ROOT="$(cd "$(dirname "${CLAUDE_PLUGIN_ROOT:-.}")" && pwd)"
# WORKSPACE_ROOT now points at the chapter workspace directory.
PROJECT_ROOT="$WORKSPACE_ROOT/patient_360"
UPSTREAM_ROOT="$WORKSPACE_ROOT"
STORIES_ROOT="$WORKSPACE_ROOT"
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

## Phase 0 — Resolve the Effective Argument

**FIRST — resolve the effective argument. Do this before any other Phase 0 step.**

The conversational argument is NOT the only source of truth — a parent
orchestrator (e.g. `implement-stories`) dispatches this skill via the
`Skill` tool and, because this skill runs with `context: fork`, the
forwarded `$ARGUMENTS` does NOT reach this fork. Check these sources in
order; stop at the first non-empty hit:

1. `$SKILL_ARG` environment variable.
2. `$WORKSPACE_ROOT/.skill-arg` file — read its contents, then delete the
   file so it is consumed at most once.
3. The conversational argument supplied to the skill.
4. **Auto-mode default** — if `$CLAUDE_AUTO_MODE=1` OR
   `$WORKSPACE_ROOT/.auto-mode` exists → full-mode default (full Silver
   generation, no story ID).
5. Only if ALL four above are empty, ask the user via `AskUserQuestion`.

Mechanical resolver (copy-paste; `$USER_ARG` is the conversational arg):

```bash
resolve_skill_arg() {
  if [ -n "$SKILL_ARG" ]; then echo "$SKILL_ARG"; return; fi
  if [ -f "$WORKSPACE_ROOT/.skill-arg" ]; then
    cat "$WORKSPACE_ROOT/.skill-arg"; rm -f "$WORKSPACE_ROOT/.skill-arg"; return
  fi
  if [ -n "$1" ]; then echo "$1"; return; fi
  if [ "$CLAUDE_AUTO_MODE" = "1" ] || [ -f "$WORKSPACE_ROOT/.auto-mode" ]; then
    echo "__AUTO__"; return
  fi
  echo ""
}
RESOLVED_ARG=$(resolve_skill_arg "$USER_ARG")
```

Echo a banner as the FIRST line of skill output: `RESOLVED TARGET: <RESOLVED_ARG>`.
Use `$RESOLVED_ARG` (NOT `$ARGUMENTS`) everywhere below as the story/epic
argument. If `$RESOLVED_ARG` is `__AUTO__` or empty/an `.md` path, treat it
as **full mode**.

## Phase 0.4 — Upstream Approval Gate

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

## Phase 0.5 — Path Scoping (optional, set by the orchestrator)

If `$WORKSPACE_ROOT/.skill-paths` exists, read it — each non-empty line is
a path in scope for THIS invocation. Process ONLY those paths; ignore other
paths the story AC names (they belong to other skills and the orchestrator
dispatches them separately). Delete `.skill-paths` after consuming it. When
the file is absent (direct human invocation), fall through to the standard
phases that scan every candidate deliverable against the Silver Domain of
Ownership.

## Phase 1 — Read Upstream Artifacts

1. **LLD §5.2 (Silver Tasks)** — extract every Silver task row (the count
   is read from the table, not hardcoded; in the current run it is 13). For
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
   `src/patient_360/utils/scd2.py::apply_scd2(df, target_table, natural_keys,
   hash_columns, effective_date)` (the `target_table` parameter is a named UC
   table FQN `unity.silver.<dim>`; see Phase 2).

3. **DMS §3 (Silver Schemas)** — for each Silver table, extract the column
   list and types (the DMS, NOT the source, owns Silver column contracts).
   Read the SCD2-dimension designation from the LLD §5.2 "SCD Type 2 processing
   notes" / DMS §6 (do NOT hardcode) — in the current run the SCD Type 2 dims
   are `clinical_patients`, `reference_organizations`, `reference_providers`,
   `reference_payers` (illustrative; always re-read from the artifacts). For
   each SCD2 table also extract the **hash (Type-2 tracked) column list** from
   the DMS §6 "Dimension Attribute SCD Types" table (the columns marked SCD
   Type 2 for that dimension).

4. **STM Bronze-to-Silver sheet** — for each Silver table, extract the
   transformation rules: column renames, casts, derived fields, code-system
   lookups, null-handling. Cite the row number in generated transform
   modules.

5. **DQS §2 (field-level Silver rules)** — locate the `DQ-FLD-NNN` IDs
   that apply to each Silver table. Confirm the per-table YAML files
   already exist upstream. The se-rules files use the
   `se-rules-<silver_table-with-hyphens>.yaml` convention (underscores →
   hyphens), e.g. `clinical_patients` →
   `$UPSTREAM_ROOT/outputs/dqs/v*/se-rules/se-rules-clinical-patients.yaml`
   (emitted by `dq-engineer-plugin:generate-se-rules`). Resolve with
   `silver_table.replace('_','-')` or glob
   `se-rules/se-rules-*.yaml`; if the matching file is missing, stop with:

   ```
   CRITICAL: upstream se-rules-<silver_table-hyphenated>.yaml missing for table <table>.
   Run /dq-engineer-plugin:generate-se-rules first.
   ```

   When emitting `dq_rules/<silver_table>.yml`, **`dq_env.<ENV>.table_name` MUST
   be the fully-qualified `unity.silver.<table>`** (catalog.schema.table), not
   the bare name — it is the SE rule-filter key (must equal the `target_table`
   `se_runner` passes to `with_expectations`) and the base for the managed
   `<target>_error`/`_stats` table FQNs. A bare name triggers the UC
   empty-namespace `fullTableNameForApi` AIOOBE on the error-table write.

6. **Stories / Story arg** — if `$RESOLVED_ARG` is `STORY-NN-NNN` or `EPIC-NN`,
   read that file from `$STORIES_ROOT/outputs/stories/v*/EPIC-NN-.../`,
   extract Acceptance Criteria backtick-quoted deliverables, and intersect
   with the Silver scope. Skip deliverables outside Silver and emit a
   ROUTE-OUT note for each.

## Phase 2 — Emit Shared SCD2 Helper (idempotent)

If `$PROJECT_ROOT/src/patient_360/utils/scd2.py` does not already exist,
emit it using the LLD §2.3 contract extended with a `target_table`
parameter — the LLD's published signature omits it, and without it the
function cannot locate the pre-created named UC table to merge into
(LLD §13 Decision 15: Silver/Gold tables are pre-created as EXTERNAL Delta
by Liquibase at deploy-time and addressed at runtime by their named UC FQN
`unity.silver.<table>`). Use the signature:

```python
def apply_scd2(
    df: DataFrame,
    target_table: str,
    natural_keys: list[str],
    hash_columns: list[str],
    effective_date,
) -> dict[str, int]:
    """Generic named-table SCD Type 2 merge.

    target_table is a NAMED Unity Catalog table FQN (unity.silver.<dim>)
    that has been PRE-CREATED as EXTERNAL Delta by Liquibase at deploy-time.
    The helper MERGEs into the existing table via
    DeltaTable.forName(spark, target_table) and NEVER creates the table /
    issues saveAsTable at runtime.

    Caller is responsible for running DQ checks BEFORE invoking this
    function — the SCD2 helper trusts every row it receives.

    Returns: {"rows_inserted": int, "rows_closed": int, "rows_unchanged": int}
    """
```

Implementation requirements (GROUND TRUTH — DMS §3 + DMS §6 + LLD §5.2 notes):

- `spark = df.sparkSession` (derived internally; NOT a parameter).
- `target_table` is a **named UC table FQN** `unity.silver.<table>`, resolved
  via `DeltaTable.forName(spark, target_table)` — NEVER `DeltaTable.forPath`
  and NEVER a filesystem path. The table is **pre-created** by Liquibase
  (deploy-time); the helper MERGEs into the existing (possibly empty) table and
  NEVER `saveAsTable`, `CREATE TABLE`, or any catalog DDL at runtime
  (table creation is deploy-time, LLD §13 Decision 15).
- **SCD2 metadata columns are EXACTLY four** (DMS §3): `effective_from` (DATE),
  `effective_to` (DATE), `is_current` (BOOLEAN), `_record_hash` (VARCHAR(64)).
  There is **NO** `surrogate_key`. PK = `[natural_key, effective_from]`. NEVER
  emit `surrogate_key`, `expiry_date`, `record_hash` (no underscore),
  `dw_created_at`, or `dw_updated_at` — those are stale chapter-3 columns.
- Compute `_record_hash` on the source side before the merge as
  `sha2(concat_ws("|", *[F.coalesce(F.trim(F.col(c).cast("string")), F.lit("")) for c in hash_columns]), 256)`
  — single-pipe delimiter, COALESCE/TRIM-normalized, so it matches the STM
  `SHA256(CONCAT_WS('|', COALESCE(TRIM(...),''), ...))` expressions exactly.
- Resolve the target with `DeltaTable.forName(spark, target_table)` and run a
  Delta MERGE against the named UC table `unity.silver.<table>` keyed on the
  natural key(s) with:
  - `WHEN MATCHED AND target.is_current = TRUE AND target._record_hash <> source._record_hash`
    → set `target.is_current = FALSE`,
    `target.effective_to = (new effective_from) - 1 day` (the close date is one
    day before the incoming `effective_from`), then insert the new version.
  - `WHEN NOT MATCHED` → insert with `effective_from = <effective_date param>`,
    `effective_to = DATE '9999-12-31'` (open-end sentinel, NOT NULL),
    `is_current = TRUE`, `_record_hash = <computed>`.
- **First run** (the pre-created `unity.silver.<table>` is empty): the same
  MERGE runs against the empty table — every source row falls through the
  `WHEN NOT MATCHED` branch and is inserted (all rows
  `effective_from = effective_date`, `effective_to = DATE '9999-12-31'`,
  `is_current = TRUE`). Do NOT create the table and do NOT
  `.save(...)`/`saveAsTable` — Liquibase already created it at deploy-time.
- No surrogate-key generation at all (no key to generate). NEVER use
  `monotonically_increasing_id()` (non-deterministic) — kept as a determinism
  guard, see IL-006.
- Return `{"rows_inserted": int, "rows_closed": int, "rows_unchanged": int}`
  (e.g. by reading `DESCRIBE HISTORY` for the last operation); the caller emits
  these via OpenTelemetry per LLD §5.4.

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
from patient_360.utils.delta_helpers import read_bronze_delta
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

    # Inline SE BEFORE write — row_dq + agg_dq from dq_rules/<silver_table>.yml.
    # action_if_failed is the SE failure response, NOT the empty-input policy
    # (those are two distinct gates — SE failure response vs empty-input
    # policy; do not conflate them). The effective
    # action is per-env, resolved by se_runner from the DQS se-rules `dq_env`
    # block (DEV/QA=ignore, PROD=fail) — do NOT hardcode a per-table severity.
    # se_runner.run_dq returns a SINGLE validated DataFrame (keyword-only
    # args; action_if_failed resolved per-env internally). NOT a tuple.
    validated_df = run_dq(
        df=silver_df,
        table=TABLE,
        env=env,
        dq_rules_dir=Path(cfg["paths"]["dq_rules"]),
    )

    # Named UC table FQN: target is the pre-created (Liquibase) external Delta
    # table addressed by its catalog name, never a filesystem path.
    target_table = f"unity.silver.{TABLE}"

    # SCD2 dims: MERGE into the named unity.silver.<table> via the shared helper.
    # Helper trusts validated rows and resolves the pre-created table with
    # DeltaTable.forName — the first run merges into an empty table.
    if <is_scd2>:
        metrics = apply_scd2(
            df=validated_df,
            target_table=target_table,
            natural_keys=[<natural_keys>],
            hash_columns=[<hash_columns_from_dms_section_6>],
            effective_date=ds,
        )
        # metrics: {"rows_inserted": int, "rows_closed": int, "rows_unchanged": int}
        # caller emits via OpenTelemetry per LLD §5.4 step 8

    # Cleansed facts: insertInto the pre-created named UC table (no path/save/
    # saveAsTable). The ONLY idempotent fact write is DYNAMIC PARTITION
    # OVERWRITE (LLD §13 Decision 15, empirically verified): the Spark session
    # sets spark.sql.sources.partitionOverwriteMode=dynamic (owned by
    # build_spark_session), and the write is
    # mode("overwrite").insertInto(...) with NO .option("replaceWhere", ...).
    # This replaces ONLY the ds partition(s) present in validated_df and
    # preserves all other partitions, so re-runs are idempotent.
    #
    # NEVER add .option("replaceWhere", ...) here: insertInto SILENTLY IGNORES
    # replaceWhere (it only applies to .save()/.saveAsTable()), so a re-run
    # APPENDS and DOUBLES the data (empirically confirmed). replaceWhere also
    # cannot coexist with partitionOverwriteMode=dynamic
    # (DELTA_REPLACE_WHERE_WITH_DYNAMIC_PARTITION_OVERWRITE). Plain append uses
    # mode("append").insertInto(...).
    else:
        # spark.sql.sources.partitionOverwriteMode=dynamic is already set on the
        # session by build_spark_session; the overwrite below is per-ds-partition.
        validated_df.write.mode("overwrite").insertInto(target_table)

    return validated_df
```

**Hard rules**:
- Never reorder STM steps — preserve the source row order so traceability holds.
- Never invent columns. Every column in the output must come from DMS §3 for
  this table. SCD2 dims carry EXACTLY the four metadata columns
  `effective_from`, `effective_to`, `is_current`, `_record_hash` — never
  `surrogate_key`, `expiry_date`, `record_hash`, or `dw_*`.
- The `action_if_failed` value is NOT set by this module and NOT a per-table
  severity table. It is resolved per-env by `se_runner` from the DQS se-rules
  `dq_env` block (DEV/QA=`ignore`, PROD=`fail`). Keep this strictly separate
  from the empty-input policy (`empty_input_behavior: write_empty|fail` from
  LLD §5.2), which is its own gate.
- For SCD2 dims, `apply_scd2` (named-table MERGE via `DeltaTable.forName`) is
  the ONLY write path — never use the cleansed-fact `insertInto` path for SCD2
  tables.
- For cleansed-fact (non-SCD2) tables, the ONLY idempotent write is DYNAMIC
  PARTITION OVERWRITE: `validated_df.write.mode("overwrite").insertInto("unity.silver.<table>")`
  with the session set to `spark.sql.sources.partitionOverwriteMode=dynamic`
  (owned by `build_spark_session`). This replaces only the ds partition(s)
  present in the DataFrame and preserves all others — re-runs are idempotent.
- NEVER add `.option("replaceWhere", ...)` to a fact write: `insertInto`
  SILENTLY IGNORES `replaceWhere` (it applies only to `.save()`/`.saveAsTable()`),
  so a re-run APPENDS and DOUBLES the data (empirically confirmed). `replaceWhere`
  also cannot coexist with `partitionOverwriteMode=dynamic`
  (`DELTA_REPLACE_WHERE_WITH_DYNAMIC_PARTITION_OVERWRITE`). Dynamic partition
  overwrite is THE fact write — there is no replaceWhere alternative.
- All writes target the pre-created named UC table (`unity.silver.<table>`)
  via MERGE (`DeltaTable.forName`) or `insertInto`; never `.save(path)`,
  never `saveAsTable`, never runtime catalog DDL (tables are pre-created by
  Liquibase at deploy-time).
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
   ddl_path: ddl/migrations/<YYYYMMDD>_2<NN>_<silver_table>.sql
   dq_path: dq_rules/<silver_table>.yml
   ```

2. `$PROJECT_ROOT/contracts/dq/<silver_table>.yml` (thresholds pointer):

   ```yaml
   table: <silver_table>
   layer: silver
   dq_rules_ref: dq_rules/<silver_table>.yml
   thresholds:
     # Operator-set contract keys. If DQS supplies values, cite the real
     # section: statistical thresholds, freshness SLA, or reconciliation
     # tolerances (DQS §3/§4) — NOT a generic "DQS §1". Otherwise mark these
     # as operator-set defaults agreed with data-ops.
     completeness_min: <operator-set | DQS statistical>
     validity_min:     <operator-set | DQS statistical>
     freshness_max_hours: <operator-set | DQS freshness SLA>
   ```

3. `$PROJECT_ROOT/dq_rules/<silver_table>.yml` — copy the `rules:` subtree
   from the upstream se-rules file
   `$UPSTREAM_ROOT/outputs/dqs/v*/se-rules/se-rules-<silver_table-with-hyphens>.yaml`
   (e.g. `se-rules-clinical-patients.yaml`). Copy the rules verbatim; the
   `dq_env` / `table_name` headers are environment-specific and may differ
   from the upstream template.

4. `$PROJECT_ROOT/ddl/migrations/<YYYYMMDD>_2<NN>_<silver_table>.sql` — the
   **pre-create DDL** as a PLAIN DATED SQL migration. Liquibase was REMOVED
   (developer-plugin L-015): it cannot work on UC OSS + Spark Thrift. This skill
   OWNS the Silver per-table migration (the layer skill that knows DMS §3 + the
   SCD2 set). The runtime NEVER creates these tables — `make ddl-apply` globs
   `ddl/migrations/*.sql`, sorts lexically, env-substitutes
   `${PATIENT360_WAREHOUSE_ROOT}`, and applies each via `beeline -f` before the
   pipeline writes. NAMING: `<YYYYMMDD>` = creation date; `2<NN>` = layer digit
   `2` (silver) + 2-digit intra-layer alpha sequence (bronze=1xx, silver=2xx,
   gold=3xx, so a lexical sort yields bronze→silver→gold). One CREATE per file;
   the first lines are `--` comment headers (beeline ignores them):

   - Table FQN is the 3-part `unity.silver.<silver_table>` (UC named side
     catalog), with an explicit
     `LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/<silver_table>'`
     (env-substituted by `ddl-apply.sh`).
   - Columns: the full business column list from **DMS §3** for this table,
     typed per DMS, plus metadata.
   - **SCD2 dimensions** (`clinical_patients`, `reference_organizations`,
     `reference_providers`, `reference_payers`) additionally get the SCD2
     metadata columns — `effective_from DATE`, `effective_to DATE`,
     `is_current BOOLEAN`, `_record_hash STRING` (VARCHAR(64)),
     `_ingested_at TIMESTAMP`, `_source_batch_id STRING` — and **NO
     `PARTITIONED BY`** (DMS §3: SCD2 dims are MERGE-upserted, never
     `ds`-partitioned; the natural key + `effective_from` is the PK). NO
     `surrogate_key`.
   - **Cleansed facts** get `ds DATE NOT NULL`, `_ingested_at TIMESTAMP`,
     `_source_batch_id STRING`, and **`PARTITIONED BY (ds)`** (insertInto
     dynamic partition overwrite target).
   - The rollback is a `-- rollback: DROP TABLE IF EXISTS unity.silver.<table>`
     comment line (the plain-SQL replacement for Liquibase `<rollback>`).

   ```sql
   -- migration: <YYYYMMDD>_2<NN>_<silver_table>
   -- layer: silver  table: unity.silver.<silver_table>
   -- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
   -- rollback: DROP TABLE IF EXISTS unity.silver.<silver_table>

   CREATE TABLE IF NOT EXISTS unity.silver.<silver_table> (
       <col> <DMS-TYPE>,            -- one row per DMS §3 business column
       -- SCD2 dims only:  effective_from DATE, effective_to DATE,
       --                  is_current BOOLEAN, _record_hash STRING
       -- facts only:      ds DATE NOT NULL
       _ingested_at TIMESTAMP,
       _source_batch_id STRING
   ) USING DELTA
   LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/<silver_table>'
   -- facts only:  PARTITIONED BY (ds)   (omit entirely for SCD2 dims)
   ```

## Phase 5 — Generate Unit Tests

For each transform emit
`$PROJECT_ROOT/tests/silver/test_transform_<table>_unit.py` covering:

- Schema invariant: output columns equal the DMS §3 column list
- Row-level transformations: at least one positive and one negative case
  per STM transformation rule
- SCD2 dims only: tested separately in `test_scd2_unit.py`; the per-table
  test must still verify that `apply_scd2` is called with the documented
  natural-key / hash-column tuple
- DQ gate: mock `run_dq` and assert it is invoked before the write; the
  effective `action_if_failed` is resolved per-env inside `se_runner` from the
  DQS se-rules, so assert on the run_dq invocation, not a hardcoded action
- Empty input: covers the LLD §5.2 declared behavior (`fail` raises,
  `write_empty` returns an empty DataFrame with the right schema)

## Phase 6 — Wire the DAG Task Groups

Edit `$PROJECT_ROOT/airflow/dags/patient360_hourly_v1.py` (DAG filename read
from the LLD §4.2 / existing DAG, not hardcoded):

1. Add a `silver_dimensions` TaskGroup containing the SCD2 dim tasks (read the
   SCD2-dim set from LLD §5.2 notes / DMS §6 — in the current run:
   `transform_patients_silver`, `transform_organizations_silver`,
   `transform_providers_silver`, `transform_payers_silver`).
2. Add a `silver_facts` TaskGroup containing the remaining cleansed-fact tasks.
3. Wire the **real per-task dependency edges from LLD §4.2 Task Inventory** —
   do NOT collapse them into a flat `[silver_dimensions, silver_facts]`
   fan-out. From LLD §4.2 (re-read at runtime):
   - the SCD2 dims (`patients`, `organizations`, `providers`, `payers`) depend
     on `reconciliation_bronze`
   - `transform_encounters_silver` depends on `transform_patients_silver`,
     `transform_organizations_silver`, `transform_providers_silver`
   - `transform_allergies_silver` depends on `transform_patients_silver`
   - the remaining facts (`conditions`, `medications`, `observations`,
     `immunizations`, `procedures`, `claims`, `careplans`) depend on
     `transform_encounters_silver`
   - `reconciliation_silver` depends on ALL silver tasks
   Express these as explicit task-to-task edges; the TaskGroups are for visual
   grouping only and must not flatten the dependency graph above.
4. Each Silver transform task is a `SparkSubmitOperator` pointing at the
   per-table transform module (use the same wrapper as Bronze).
   `reconciliation_silver` is SQL-only and may be a `PythonOperator` /
   `SQLExecuteQueryOperator` per LLD §4.2.

Do not duplicate Bronze ingestion or `reconciliation_bronze` — they
already exist from `developer-plugin:create-ingestion` /
`create-dag`. The edit is additive only.

## Phase 7 — Verify and Report

Run the in-plugin validator:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-silver/scripts/validate_silver.py \
  --project-root "$PROJECT_ROOT"
# The validator auto-discovers the latest LLD/DMS by walking up from
# $PROJECT_ROOT to the workspace `outputs/` (find_upstream_root).
```

Report:
- ✅ N modules emitted, M contracts emitted, K tests emitted
- ❌ Any LLD §5.2 row that did not produce a module (with reason)
- 🛣  ROUTE-OUT items: deliverables in the story that belong to other layers

## Learnings & Corrections

Meta-rules for adding learnings to this skill:

- Append every user correction during a session to
  `$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl` as a JSON line:
  `{"skill": "create-silver", "date": "YYYY-MM-DD", "correction": "...", "pattern": "...", "status": "pending"}`
- At session end, if pending entries exist, run
  `/developer-plugin:apply-learnings` before finishing.

### Inherited Learnings (from the Bronze build)

These rules were learned the hard way while building the Bronze
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
- **IL-002** NEVER bind `spark.sql.catalog.spark_catalog` to
  `UCSingleCatalog` — `spark_catalog` stays `DeltaCatalog`. Unity Catalog is
  ALWAYS a **named side catalog** (`spark.sql.catalog.unity =
  io.unitycatalog.spark.UCSingleCatalog`, `spark.sql.defaultCatalog=unity`),
  and that `unity` catalog **IS used at runtime** for Silver reads and writes:
  SCD2 dims MERGE into `unity.silver.<dim>` via `DeltaTable.forName`; cleansed
  facts `insertInto("unity.silver.<table>")`. UC tables are **pre-created** as
  EXTERNAL Delta by Liquibase at deploy-time, never created at runtime (LLD §13
  Decisions 12 + 15).
- **IL-003** NEVER issue runtime catalog DDL that CREATES objects — no
  `saveAsTable`-create, no `CREATE TABLE`, no `CREATE SCHEMA` (tables are
  pre-created by Liquibase at deploy-time). Runtime DOES `insertInto` / MERGE
  into the existing `unity.silver.*` tables. Anchor any relative config paths
  against `PATIENT360_PROJECT_ROOT` (see IL-005) so they resolve identically
  across `spark-submit` boots.
- **IL-004** ALWAYS address Silver Delta tables by their **named UC FQN**
  (`unity.silver.<table>` — read via `spark.read.table(...)`, write via
  `DeltaTable.forName(...)` MERGE or `insertInto(...)`), never by filesystem
  path / `delta.\`...\`` and never by a UC-bound `spark_catalog`. Because UC is
  a single-part-namespace catalog, keep table references two-part under the
  `unity` catalog (`silver.<table>`) to avoid `REQUIRES_SINGLE_PART_NAMESPACE`.
- **IL-005** ALWAYS anchor relative YAML paths (contracts_dir,
  dq_rules_dir, source.path) against the `PATIENT360_PROJECT_ROOT` env
  var. The Airflow worker CWD is `/opt/airflow`, not the project root —
  every relative path that resolves against CWD will break in container.
- **IL-006** The DMS §3 SCD2 schema has **NO surrogate key** — the natural
  key is the merge key, so there is no surrogate to generate. NEVER use
  `monotonically_increasing_id()` (non-deterministic per executor and per
  run); the ban stands as a determinism guard even though no surrogate-key
  generation is required.

**Spark Expectations (Silver inline DQ)**

- **IL-007** ALWAYS wrap the input DataFrame in a no-arg lambda for SE's
  decorator API: `decorated = se.with_expectations(...)(lambda: df);
  validated = decorated()`. Calling `se.with_expectations(...)(df)` returns
  a function (not a DataFrame) and silently breaks `.write`.
- **IL-008** spark-expectations ALWAYS writes a stats table — there is no
  disable flag. Configure the SE stats and error writers as **path-based**
  Delta via `.option("path", ...)` (outside Unity Catalog) — do NOT rely on a
  `saveAsTable` into the `unity` catalog. The SE stats/error tables live on the
  filesystem; only the Silver data tables are named UC tables (see IL-002).
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

**DDL migration (Silver DDL ownership)**

- **IL-018** This skill OWNS the Silver per-table DDL migration
  (`ddl/migrations/<YYYYMMDD>_2<NN>_<silver_table>.sql`, plain SQL — Liquibase
  removed, L-015) — there is no separate "future silver skill"; it is this one
  (mirrors `update-ingestion` owning the Bronze migrations). ALWAYS emit each
  Silver migration with: the 3-part FQN `unity.silver.<table>`, an explicit
  `LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/<table>'`, the full
  DMS §3 business columns, and a `<rollback>` DROP. **SCD2 dims** add the
  SCD2 metadata set (`effective_from`, `effective_to`, `is_current`,
  `_record_hash`, `_ingested_at`, `_source_batch_id`; NO `surrogate_key`)
  and carry **NO `PARTITIONED BY`** (MERGE-upserted, never `ds`-partitioned
  per DMS §3). **Facts** add `ds DATE NOT NULL` + `_ingested_at` +
  `_source_batch_id` and `PARTITIONED BY (ds)`. NEVER emit a bare `silver.`
  schema (must be `unity.silver.`), NEVER omit `LOCATION` (the table is
  EXTERNAL), and NEVER `PARTITIONED BY (ds)` on an SCD2 dim. These
  changelogs are applied by the beeline `ddl-apply` one-shot (create-scaffold
  L-012), NOT the runtime.

### Active Learnings

<!-- New L-NNN entries get appended below by apply-learnings. Keep absolute
     directives ("MUST" / "NEVER") so they survive context-window pressure.
     Inherited entries (IL-NNN) live in their own block above and are
     never renumbered. -->

- **L-001** (2026-06-21): Emitted Silver Python MUST pass `make lint` (ruff `select=[E,F,I,UP]`, line-length 100). This skill had no lint gate and shipped UP037 (quoted `-> "F.Column"` annotations — write `-> F.Column` unquoted, `F` is imported at module top) and E501 (>100-char `F.expr("…long SQL…")` strings — split the SQL across implicitly-concatenated string literals), silently red-lining `make lint`. As the FINAL step of this skill ALWAYS run `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/` and confirm `make lint` exits 0 before reporting done (`ruff format` auto-resolves UP037/I001 and explodes long signatures).
