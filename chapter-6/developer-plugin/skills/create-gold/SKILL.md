---
name: create-gold
description: >
  Generates the Gold layer of the Patient 360 Medallion pipeline from the
  approved LLD §2.3 / §5.3, DMS §4, STM Silver-to-Gold sheet, DQS §2-3
  (Gold rules), and a given story. Emits PySpark builder modules for the
  3 Gold consumer tables (`patient_summary`, `patient_clinical_history`,
  `patient_billing_summary`), per-table contracts, per-table Spark
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
  - Build the 3 Gold consumer tables (patient_summary, etc.)
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
UPSTREAM_ROOT="$(cd "$WORKSPACE_ROOT/../chapter-4" && pwd)"
STORIES_ROOT="$(cd "$WORKSPACE_ROOT/../chapter-5" && pwd)"
LEARNINGS_QUEUE="$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl"
```

Writes:
- Builders → `$PROJECT_ROOT/src/patient_360/gold/build_<table>.py`
- Contracts → `$PROJECT_ROOT/contracts/<gold_table>.yml` (+ DQ pointer
  under `contracts/dq/`)
- DQ rules → `$PROJECT_ROOT/dq_rules/<gold_table>.yml`
- Unit tests → `$PROJECT_ROOT/tests/gold/test_build_<table>_unit.py`
- DAG edits → `$PROJECT_ROOT/airflow/dags/patient360_hourly_v1.py`

## Phase 0 — Upstream Approval Gate

Refuse to run unless **LLD, DMS, STM, DQS, Stories, AND the Silver layer
contract trio** are all `Approved`. The Silver layer is upstream of Gold:
silver tables must exist at `warehouse/{env}/silver/<domain>/<table>/`
and their contracts must be marked Approved.

If any upstream missing, stop with a `CRITICAL` message naming each
unapproved artifact.

## Phase 1 — Read Upstream Artifacts

1. **LLD §5.3 (Gold Tasks)** — extract the 3 Gold task rows:
   - `build_patient_summary_gold` →
     `gold/build_patient_summary.py`, reads `clinical_patients` (is_current),
     `clinical_encounters`, `clinical_conditions`, `clinical_medications`,
     `clinical_allergies`
   - `build_clinical_history_gold` →
     `gold/build_patient_clinical_history.py`, reads `clinical_patients` (is_current)
     + every clinical fact table
   - `build_billing_summary_gold` →
     `gold/build_patient_billing_summary.py`, reads `clinical_patients` (is_current),
     `clinical_encounters`, `billing_claims`, `reference_payers` (is_current)
2. **DMS §4 (Gold Schemas)** — column list per Gold table; types per DMS
3. **STM Silver-to-Gold sheet** — per-Gold-table transformation rules
   (joins, aggregations, derived columns, code-system lookups)
4. **DQS §2-3 Gold rules** — the `DQ-FLD-NNN` IDs that apply to each Gold
   table (e.g. DQ-FLD-105 to DQ-FLD-140 for patient_summary). Verify the
   per-table YAML exists at
   `$UPSTREAM_ROOT/outputs/dqs/v*/se-rules/<gold_table>.yaml`.

## Phase 2 — Generate Per-Table Gold Builder Modules

For each of the 3 Gold tables, emit
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

    # 1. Read Silver inputs. SCD2 dims are filtered to current-state rows;
    #    point-in-time joins use the effective_date / expiry_date range
    #    (see LLD §5.2 SCD2 processing notes).
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
    validated_df, _ = run_dq(
        df=gold_df,
        table=TABLE,
        env=env,
        action_if_failed="fail",   # Gold tables are consumer-facing; fail-closed
        dq_rules_dir=Path(cfg["paths"]["dq_rules"]),
    )

    # 4. Write Gold partition (full table replace per ds; Gold tables are
    #    rebuilt every run, not SCD2).
    write_gold_delta(validated_df, table=TABLE, ds=ds, env=env)

    return validated_df
```

**Hard rules**:
- Gold has NO SCD2 (per LLD §5.3 — Gold tables are rebuilt per ds, not
  versioned). Never import or call `apply_scd2` from a Gold builder.
- Every dimension read MUST filter `is_current = True` for current-state
  Gold reports, per LLD §5.2 SCD2 implications. Historical Gold reports
  (none in Phase 1) would use the date-range overlap form.
- `action_if_failed="fail"` is the Gold default — consumer tables MUST NOT
  ship with partial data. Per-rule overrides may relax this but the
  per-table fail-closed default stays `fail`.
- Joins follow STM Silver-to-Gold row order; never reorder for "performance"
  without an LLD §6 entry authorizing it.

## Phase 3 — Generate Contracts and DQ Pointers

Same pattern as `create-silver` Phase 4, with `layer: gold`. The contract
schema column list is from DMS §4; the DQ pointer thresholds (completeness,
validity, freshness) come from DQS §1 — Gold tables usually have stricter
thresholds (e.g. `completeness_min: 0.99`).

## Phase 4 — Generate Unit Tests

For each builder, emit
`$PROJECT_ROOT/tests/gold/test_build_<table>_unit.py` covering:

- Schema invariant: output columns match DMS §4
- Join correctness: one positive and one orphan case per STM join rule
- `is_current=True` filter is applied for every SCD2 dim read
- `run_dq` mocked + asserted with `action_if_failed="fail"`
- Empty Silver input → task fails (LLD §5.3 last column `Fail task` for
  all three Gold tables)

## Phase 5 — Wire the DAG

Edit `$PROJECT_ROOT/airflow/dags/patient360_hourly_v1.py`:

1. Add a `gold_build` TaskGroup containing the 3 builder tasks.
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
`chapter-6/memory/developer/learnings-queue.jsonl`. LLD-bug corrections
also go in `developer-plugin/LLD-DEVIATIONS.md`.

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017 — same runtime stack and same
constraints apply to Gold. Note especially IL-004 (2-part FQNs) and
IL-014 (DEV `max_active_tasks=1`) since Gold builders are typically the
heaviest tasks in the DAG.

### Active Learnings

(no chapter-6-specific learnings yet)
