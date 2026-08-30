---
name: validate-silver
description: >
  Validates an existing Silver layer implementation against the latest
  approved LLD §5.2, DMS §3, STM Bronze-to-Silver sheet, and DQS §2.
  Produces a severity-ranked report (CRITICAL / WARNING / INFO) covering
  module presence, schema alignment, SCD2 wiring, DQ-before-write order,
  contract/DQ coverage, and traceability.
  Use when the user asks to:
  - Validate, check, review, or audit the Silver layer
  - Run quality checks on Silver code before promotion
  - Find drift between Silver code and upstream artifacts
argument-hint: ""
allowed-tools: Read, Grep, Glob, Bash, Skill
context: fork
---

# Validate Silver Layer

You are a senior Data Engineer running an audit. The Silver layer code may
have drifted from the approved upstream artifacts. Your job is to detect
every drift class and report it; never auto-fix — the operator decides
whether to run `update-silver`.

## Workspace Discovery

```bash
WORKSPACE_ROOT="$(cd "$(dirname "${CLAUDE_PLUGIN_ROOT:-.}")" && pwd)"
PROJECT_ROOT="$WORKSPACE_ROOT/patient_360"
UPSTREAM_ROOT="$WORKSPACE_ROOT"
```

## Phase 0 — Pre-Conditions (INFO-only)

Locate the latest LLD / DMS / STM / DQS under `$UPSTREAM_ROOT/outputs/`.
If none of the four is `Approved`, downgrade every finding by one severity
(CRITICAL → WARNING, WARNING → INFO) — Silver validation against unapproved
upstream is advisory only.

## Phase 1 — Module Presence

For every Silver task row in LLD §5.2:

- **R1 [CRITICAL]** `src/patient_360/silver/transform_<table>.py` exists
- **R2 [CRITICAL]** `contracts/<silver_table>.yml` exists
- **R3 [CRITICAL]** `contracts/dq/<silver_table>.yml` exists
- **R4 [CRITICAL]** `dq_rules/<silver_table>.yml` exists
- **R5 [CRITICAL]** `tests/silver/test_transform_<table>_unit.py` exists

Modules present but not in the LLD §5.2 list → **WARNING (orphan)**.

## Phase 2 — Schema Alignment

For each present Silver table:

- **R6 [CRITICAL]** `contracts/<silver_table>.yml` schema columns match
  DMS §3 column list for that table (set equality, type match per the
  DMS-stated types)
- **R7 [WARNING]** SCD2 dimension contracts include the four DMS §3 SCD2
  metadata columns: `effective_from` (DATE), `effective_to` (DATE),
  `is_current` (BOOLEAN), `_record_hash` (VARCHAR(64)). This is a subset of
  the DMS §3 column set already checked by R6 — there is NO `surrogate_key`,
  `expiry_date`, `record_hash` (no underscore), or `dw_*` column (those are
  stale chapter-3 names). The natural key is an ordinary business column
  covered by R6; PK is `[natural_key, effective_from]`.
- **R8 [INFO]** Contract `tags` reflect DMS §3 owner/domain

## Phase 3 — SCD2 Wiring (dimensions only)

For each of the 4 SCD2 dim tables
(`clinical_patients`, `reference_organizations`, `reference_providers`,
`reference_payers`):

- **R9 [CRITICAL]** Module imports `apply_scd2` from
  `patient_360.utils.scd2`
- **R10 [CRITICAL]** `apply_scd2(...)` invocation passes `target_table`,
  `natural_keys`, `hash_columns`, `effective_date` in that order (positional
  or keyword). `target_table` is a NAMED Unity Catalog table FQN
  (`unity.silver.<dim>`, merged via `DeltaTable.forName("unity.silver.<dim>")`)
  — NOT a filesystem path. The dim table is pre-created EXTERNAL Delta by
  Liquibase; the helper MERGEs into the named UC table. `saveAsTable` is
  forbidden (UCSingleCatalog-unsupported staged create) — LLD v1.13 UC write
  pattern.
- **R11 [CRITICAL]** `hash_columns` list matches DMS §6 for that table
- **R12 [CRITICAL]** Module does NOT call `write_silver_delta` for SCD2
  tables — that path is mutually exclusive with `apply_scd2`
- **R13 [CRITICAL]** `apply_scd2` is invoked AFTER `run_dq` in source order
  (DQ-before-write contract)
- **R14 [WARNING]** Module never calls `monotonically_increasing_id()`. The
  DMS §3 SCD2 schema has NO surrogate key — the natural key is the merge key,
  so no surrogate generation is needed at all. The ban is a determinism guard:
  `monotonically_increasing_id()` is non-deterministic per executor and per run
  (per inherited learning IL-006).

## Phase 4 — DQ Gate (every Silver task)

- **R15 [CRITICAL]** `run_dq(...)` is called inside the module
- **R16 [CRITICAL]** `run_dq` passes an `action_if_failed` argument. The
  effective value is per-env, read by `se_runner` from the DQS se-rules
  `dq_env` block (DEV/QA = `ignore`, PROD = `fail`) — NOT a hardcoded
  per-table severity table and NOT a flat `fail`. The empty-input policy
  (`empty_input_behavior`, LLD §5.2) is a separate gate and is not checked here.
- **R17 [CRITICAL]** `run_dq` is called BEFORE the write step (SCD2 merge
  or `write_silver_delta`) in source order
- **R18 [WARNING]** `dq_rules/<silver_table>.yml` `rules:` subtree matches
  the upstream DQS file `outputs/dqs/v*/se-rules/se-rules-<silver_table-with-hyphens>.yaml`
  (e.g. `se-rules-clinical-patients.yaml`). Compare only the `rules:` subtree
  semantically — the `dq_env` / `table_name` headers legitimately differ
  between the upstream template and the local copy, so a byte-for-byte
  comparison would false-positive.
- **R19 [CRITICAL]** SE `with_expectations(...)` wraps its argument in a
  no-arg lambda (per inherited learning IL-007). Pattern:
  `decorated = se.with_expectations(...)(lambda: df); validated = decorated()`.
  Direct `se.with_expectations(...)(df)` → CRITICAL.

## Phase 5 — DAG Wiring

Read `airflow/dags/patient360_hourly_v1.py`:

- **R20 [CRITICAL]** `silver_dimensions` TaskGroup contains exactly the 4
  SCD2 dim tasks; no more, no fewer
- **R21 [CRITICAL]** `silver_facts` TaskGroup contains exactly the 9
  cleansed-fact tasks
- **R22 [CRITICAL]** Dependency edge:
  `bronze_ingestion >> reconciliation_bronze >> [silver_dimensions, silver_facts] >> reconciliation_silver`
- **R23 [CRITICAL]** Every Spark-touching Silver transform task
  (`transform_<table>_silver`) uses `SparkSubmitOperator` — a PythonOperator
  is flagged only when its `task_id` is a Spark transform task (per IL-011).
  SQL-only reconciliation tasks (`reconciliation_silver`) may legitimately be
  `PythonOperator` / `SQLExecuteQueryOperator` per LLD §4.2.
- **R24 [WARNING]** Each `SparkSubmitOperator` invokes the per-table module
  by path (`src/patient_360/silver/transform_<table>.py`)

## Phase 6 — Traceability

- **R25 [WARNING]** Every Silver module's docstring cites LLD §5.2 row,
  STM Bronze-to-Silver row, DMS §3 subsection, DQS DQ-FLD-NNN range
- **R26 [INFO]** `contracts/<silver_table>.yml` `ddl_path` resolves to an
  existing plain-`.sql` migration under `ddl/migrations/`
- **R27 [INFO]** `contracts/<silver_table>.yml` `dq_path` resolves to the
  existing per-table `dq_rules/<silver_table>.yml`

## Phase 7 — Report

Emit a structured report (text or JSON via `--format json`):

```
Silver Validation Report
========================
File: <project_root>/src/patient_360/silver/

  CRITICAL (N):
    [R10] clinical_patients: apply_scd2 call missing target_path argument
    [R17] clinical_encounters: run_dq invoked AFTER write_silver_delta

  WARNING (M):
    [R7]  reference_organizations: contract missing _record_hash column

  INFO (K):
    [R26] billing_claims: ddl_path -> ddl/migrations/20260620_201_billing_claims.sql

  Summary: N critical, M warnings, K info
  Result: FAILED (critical issues)
```

Exit code: `0` if no CRITICAL findings, `1` otherwise. The Makefile
`validate-silver` target wraps this skill's script.

## Implementation Note

The actual rule evaluator lives at
`scripts/validate_silver.py` and is invoked by both this skill (for the
interactive report) and the Makefile `validate-silver` target (CI).

## Learnings & Corrections

Meta-rules: append corrections to
`$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl`. Validator-rule mistakes
go in this skill's Active Learnings; LLD interpretation mistakes should be
raised via a `/technical-lead-plugin:update-lld` cycle.

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017. Note especially IL-016
(filter findings to story scope when invoked under `implement-stories`).

### Active Learnings

(no skill-specific learnings yet)
