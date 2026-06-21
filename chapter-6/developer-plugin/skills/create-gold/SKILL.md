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

The LLD + DMS + STM + DQS are the single source of truth. Every join,
column, and rule MUST already exist upstream — never invent.

## Workspace Discovery

```bash
WORKSPACE_ROOT="$(cd "$(dirname "${CLAUDE_PLUGIN_ROOT:-.}")" && pwd)"
PROJECT_ROOT="$WORKSPACE_ROOT/patient_360"
UPSTREAM_ROOT="$WORKSPACE_ROOT"
STORIES_ROOT="$WORKSPACE_ROOT"
LEARNINGS_QUEUE="$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl"
```

Writes:
- Builders → `$PROJECT_ROOT/src/patient_360/gold/build_<table>.py`
- Contracts → `$PROJECT_ROOT/contracts/<gold_table>.yml` (+ DQ pointer
  under `contracts/dq/`)
- DQ rules → `$PROJECT_ROOT/dq_rules/<gold_table>.yml`
- Unit tests → `$PROJECT_ROOT/tests/gold/test_build_<table>_unit.py`
- DAG edits → `$PROJECT_ROOT/airflow/dags/patient360_hourly_v1.py`

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
   `$WORKSPACE_ROOT/.auto-mode` exists → full-mode default (full Gold
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

Refuse to run unless **LLD, DMS, STM, DQS, and Stories** are all
`Approved`. The Silver layer is upstream of Gold: Silver tables must
already exist at `warehouse/{env}/silver/<domain>/<table>/` and the
Silver story must be `Done`. (Silver contracts carry no `Status` field,
so gate on the Silver story status + table presence, not a contract
"Approved" flag.)

If any upstream missing, stop with a `CRITICAL` message naming each
unapproved artifact or missing Silver table.

## Phase 0.5 — Path Scoping (optional, set by the orchestrator)

If `$WORKSPACE_ROOT/.skill-paths` exists, read it — each non-empty line is
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
   tables to read), Outputs (`warehouse/{env}/gold/<table>/`), Transform
   Ref (STM sheet), and DQ Check. As of the current LLD the rows are
   (illustrative only — re-read §5.3):
   - `build_patient_summary_gold` →
     `gold/build_patient_summary.py`, reads `clinical_patients` (current),
     `clinical_encounters`, `clinical_conditions`, `clinical_medications`,
     `clinical_allergies`
   - `build_clinical_history_gold` →
     `gold/build_patient_clinical_history.py`, reads `clinical_patients`
     (current) + the clinical fact tables, plus the reference dimensions
     the STM Silver-to-Gold rows actually join (e.g. `reference_providers`,
     `reference_organizations`, each filtered `is_current = True`)
   - `build_billing_summary_gold` →
     `gold/build_patient_billing_summary.py`, reads `clinical_patients`
     (current), `clinical_encounters`, `billing_claims`,
     `reference_payers` (current)
   Join keys are **per the STM Silver-to-Gold sheet** — dimensions join on
   their natural key (`patient_id`, `provider_id`, `organization_id`,
   `payer_id`); there is no surrogate FK. Never assume a fixed `patient_id`
   join for every row.
2. **DMS §4 (Gold Schemas)** — column list per Gold table; types per DMS.
   Gold schemas are expressed as fenced YAML (`table:` / `columns:`)
   blocks in DMS §4, not markdown pipe tables.
3. **STM Silver-to-Gold sheet** — per-Gold-table transformation rules
   (joins, aggregations, derived columns, code-system lookups)
4. **DQS Gold rules** — the `DQ-FLD-NNN` IDs that apply to each Gold
   table (e.g. DQ-FLD-105 to DQ-FLD-140 for patient_summary). Verify the
   per-table SE-rules YAML exists at
   `$UPSTREAM_ROOT/outputs/dqs/v*/se-rules/se-rules-<gold_table-hyphenated>.yaml`
   (the upstream file uses hyphens, e.g.
   `se-rules-patient-summary.yaml`). The local copy is
   `dq_rules/<gold_table>.yml` and carries only the `rules:` subtree plus
   the `dq_env` block. **`dq_env.<ENV>.table_name` MUST be the fully-qualified
   `unity.gold.<table>`** (catalog.schema.table), not the bare name — it is the
   SE rule-filter key (must equal the `target_table` passed to
   `with_expectations`) and the base for the managed `<target>_error`/`_stats`
   table FQNs. A bare name triggers the UC empty-namespace `fullTableNameForApi`
   AIOOBE on the error-table write.

## Phase 2 — Generate Per-Table Gold Builder Modules

For each Gold table declared in LLD §5.3, emit
`$PROJECT_ROOT/src/patient_360/gold/build_<table>.py`:

```python
"""Gold builder: <inputs> -> <gold_table>.

LLD: §5.3 row <NN>
STM: Silver-to-Gold row <NN>
DMS: §4.<NN> <gold_table> schema
DQS: <DQ-FLD-NNN> .. <DQ-FLD-MMM>
"""

from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

from patient_360.utils.se_runner import run_dq
from patient_360.utils.delta_helpers import read_silver_delta, write_gold_delta
from patient_360.utils.pipeline_config import load_pipeline_config

TABLE = "<gold_table>"


def build(spark: SparkSession, env: str, ds: str) -> DataFrame:
    cfg = load_pipeline_config(env)

    # 1. Read Silver inputs. SCD2 dims are filtered to current-state rows
    #    on the NATURAL key (patient_id, provider_id, organization_id,
    #    payer_id) — there is no surrogate FK. A point-in-time (historical)
    #    join, if any STM row calls for one, uses the effective_from /
    #    effective_to range:
    #        effective_from <= event_date
    #        AND (effective_to >= event_date OR effective_to = DATE '9999-12-31')
    #    (NOT effective_date / expiry_date — those are stale names.)
    patients = (
        read_silver_delta(spark, table="clinical_patients", env=env)
        .filter(F.col("is_current") == True)   # noqa: E712 — Spark Column compare
    )
    encounters = read_silver_delta(spark, table="clinical_encounters", env=env)
    # ... per LLD §5.3 Inputs column for this Gold table

    # 2. Apply STM Silver-to-Gold joins + aggregations. Preserve STM row order.
    gold_df = (
        patients
        .join(encounters, on="patient_id", how="left")
        # ... per STM rows
        .groupBy(...)
        .agg(...)
    )

    # 3. DQ gate BEFORE write — Gold-specific row_dq + agg_dq + query_dq.
    #    The per-rule / per-env action_if_failed comes from the loaded
    #    SE-rules YAML (DEV/QA=ignore, PROD=fail). run_dq maps env -> dq_env
    #    and resolves the action per rule; do not hardcode a flat "fail".
    validated_df, _ = run_dq(
        df=gold_df,
        table=TABLE,
        env=env,
        dq_rules_dir=Path(cfg["paths"]["dq_rules"]),
    )

    # 4. Write Gold table — FULL OVERWRITE, no partition (LLD §3.3:
    #    write=Full overwrite, partition=None). Insert into the Liquibase
    #    pre-created EXTERNAL Delta table via
    #    df.write.mode("overwrite").insertInto("unity.gold.<table>")
    #    (or df.writeTo("unity.gold.<table>").overwrite(...)). Gold tables
    #    are rebuilt every run, not SCD2; do NOT pass or partition by ds.
    write_gold_delta(validated_df, table=TABLE, env=env)

    return validated_df
```

**Hard rules**:
- **Insert into the pre-created table — never `.save(path)`.** Write each
  Gold table by inserting into the Liquibase-pre-created EXTERNAL Delta
  table: `df.write.mode("overwrite").insertInto("unity.gold.<table>")`
  (full overwrite, no partition; `df.writeTo("unity.gold.<table>").overwrite(...)`
  is the equivalent DataFrameWriterV2 form). NEVER `.save(path)`,
  `saveAsTable`, `CREATE TABLE`, `createOrReplace*`, or any catalog DDL at
  runtime — tables are pre-created as external Delta by Liquibase at
  deploy-time (LLD Decision 15). The builder inserts into an existing
  table; it never creates tables or touches the metastore.
- Gold has NO SCD2 (per LLD §5.3 — Gold tables are rebuilt each run, not
  versioned). Never import or call `apply_scd2` from a Gold builder.
- Every SCD2 dimension read MUST filter `is_current = True` for
  current-state Gold reports, joining on the dimension's NATURAL key
  (per LLD §5.2 SCD2 implications). A historical Gold report would use
  the `effective_from`/`effective_to` range overlap form instead.
- `action_if_failed` is resolved per-rule / per-env from the DQS
  SE-rules YAML (DEV/QA=ignore, PROD=fail). Do not hardcode a flat
  per-table `fail`; let `run_dq` resolve the env-mapped action.
- Joins follow STM Silver-to-Gold row order; never reorder for "performance"
  without an LLD §6 entry authorizing it.

## Phase 3 — Generate Contracts and DQ Pointers

Same pattern as `create-silver` Phase 4, with `layer: gold`. The contract
schema column list is from DMS §4 (the YAML `columns:` block). The DQ
thresholds are NOT invented here — read the actual values from the DQS
Gold SE-rules that apply to each table (the `row_dq` / `agg_dq` rule
families in `se-rules-<gold_table-hyphenated>.yaml`, e.g. completeness /
not-null / range rules). Copy the upstream thresholds verbatim; never
pin a placeholder like `completeness_min: 0.99`.

## Phase 4 — Generate Unit Tests

For each builder, emit
`$PROJECT_ROOT/tests/gold/test_build_<table>_unit.py` covering:

- Schema invariant: output columns match DMS §4
- Join correctness: one positive and one orphan case per STM join rule
- `is_current=True` filter is applied for every SCD2 dim read
- `run_dq` mocked + asserted (env-resolved action comes from the SE-rules
  YAML; under PROD it resolves to `fail`)
- Empty Silver input → task fails (LLD §5.3 `Fail task` empty-input
  behavior for the Gold tables)

## Phase 5 — Wire the DAG

Edit `$PROJECT_ROOT/airflow/dags/patient360_hourly_v1.py`:

1. Add a `gold_build` TaskGroup containing exactly the builder tasks
   declared in LLD §5.3.
2. Set the dependency edge:
   `reconciliation_silver >> gold_build >> reconciliation_gold`.
3. Each builder is a `SparkSubmitOperator` (IL-011) pointing at the per-table
   builder module.

The `silver_dimensions` / `silver_facts` task groups must already exist
(from `create-silver`); if missing, stop with a CRITICAL message asking
the operator to run `create-silver` first.

## Phase 6 — Verify and Report

Run `/developer-plugin:validate-gold`. Report builders emitted, contracts
emitted, tests emitted, and any LLD §5.3 row that did not produce a
module (with reason).

## Learnings & Corrections

Meta-rules: append corrections to
`$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl`. LLD-bug corrections
should be raised via a `/technical-lead-plugin:update-lld` cycle so the LLD
is corrected at source.

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017 — same runtime stack and same
constraints apply to Gold. Note especially IL-004 (2-part FQNs) and
IL-014 (DEV `max_active_tasks=1`) since Gold builders are typically the
heaviest tasks in the DAG.

### Active Learnings

(no skill-specific learnings yet)
