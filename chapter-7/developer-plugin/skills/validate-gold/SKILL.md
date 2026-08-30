---
name: validate-gold
description: >
  Validates an existing Gold layer implementation against the latest
  approved LLD §5.3, DMS §4, STM Silver-to-Gold sheet, and DQS §2-3 Gold
  rules. Produces a severity-ranked report covering builder presence,
  schema alignment, SCD2 `is_current` filtering, DQ-before-write order,
  contract/DQ coverage, DAG wiring, and traceability.
  Use when the user asks to:
  - Validate, check, review, or audit the Gold layer
  - Run quality checks on Gold builders before promotion
  - Find drift between Gold code and Silver / DMS / STM / DQS
argument-hint: ""
allowed-tools: Read, Grep, Glob, Bash, Skill
context: fork
---

# Validate Gold Layer

You are a senior Data Engineer running a Gold-layer audit. Detect drift,
report it; never auto-fix.

## Workspace Discovery

Run the shared discovery helper and substitute the returned tokens into
every path this skill reads:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`.

## Phase 0 — Pre-Conditions

Locate latest LLD / DMS / STM / DQS under `{workspace_root}/outputs/`. If
any is not `Approved`, downgrade all findings by one severity.

## Phase 1 — Builder Presence

For each Gold task row in LLD §5.3:

- **G1 [CRITICAL]** `src/patient_360/gold/build_<table>.py` exists
- **G2 [CRITICAL]** `contracts/<gold_table>.yml` exists
- **G3 [CRITICAL]** `contracts/dq/<gold_table>.yml` exists
- **G4 [CRITICAL]** `dq_rules/<gold_table>.yml` exists
- **G5 [CRITICAL]** `tests/gold/test_build_<table>_unit.py` exists

Builders present but not in LLD §5.3 → **WARNING (orphan)**.

## Phase 2 — Schema Alignment

- **G6 [CRITICAL]** `contracts/<gold_table>.yml` schema columns match
  DMS §4 (set equality). DMS §4 Gold schemas are fenced YAML
  (`table:` / `columns:`) blocks, not markdown pipe tables — parse the
  YAML `columns:` block
- **G7 [INFO]** Contract `tags` reflect DMS §4 owner/consumer group

## Phase 3 — SCD2 Read Pattern (Gold-specific)

For each builder, for every SCD2 dim it actually reads — derive the
per-builder SCD2 input set from LLD §5.3 (Inputs column) intersected with
the SCD2 dimensions declared in DMS §6 (`clinical_patients`,
`reference_organizations`, `reference_providers`, `reference_payers`), not
a pinned global set. Note that `patient_clinical_history` reads
`reference_providers` / `reference_organizations` in addition to
`clinical_patients`:

- **G8 [CRITICAL]** Read is filtered by `is_current = True` (current-state
  Gold pattern per LLD §5.2 SCD2 implications), associated with that
  specific dim read
- **G9 [WARNING]** Pattern is `F.col("is_current") == True` rather than
  raw Python truthiness check (the latter is silently wrong against
  Spark Column types)
- **G10 [CRITICAL]** Builder does NOT import `apply_scd2` (Gold never
  performs SCD2 writes — LLD §5.3 implication)
- **G23 [CRITICAL]** UC insertInto write only. The builder contains NO
  `saveAsTable`, `createOrReplace*`, `createTable`, or `CREATE TABLE` /
  catalog DDL (the table is pre-created EXTERNAL Delta by Liquibase — LLD
  v1.13 UC write pattern). The write goes via
  `insertInto("unity.gold.<table>")` (this is the required path and is NOT
  banned); the validator asserts an `insertInto` call targets the expected
  `unity.gold.<table>` FQN. Full overwrite, no `ds` partition (LLD §3.3).

## Phase 4 — DQ Gate (every Gold task)

- **G11 [CRITICAL]** `run_dq` is called inside the builder
- **G12 [CRITICAL]** The target-env action for the table resolves to
  `fail` for PROD — validate against the env-resolved `action_if_failed`
  from the loaded SE-rules `dq_env` block (DEV/QA=ignore, PROD=fail), not
  a literal `action_if_failed="fail"` kwarg default
- **G13 [CRITICAL]** `run_dq` is called BEFORE the `write_gold_delta`
  step in source order
- **G14 [WARNING]** `dq_rules/<gold_table>.yml` matches the `rules:`
  subtree of
  `outputs/dqs/v*/se-rules/se-rules-<gold_table-hyphenated>.yaml`
  (semantic compare of the rules, not a whole-file byte compare)
- **G15 [CRITICAL]** SE `with_expectations(...)` wraps in a no-arg
  lambda (IL-007)

## Phase 5 — Join Correctness (vs STM Silver-to-Gold)

- **G16 [WARNING]** Best-effort join check: the builder declares at least
  one `.join()` for each multi-input table. Full join-to-STM-row mapping
  requires parsing the STM Silver-to-Gold xlsx sheet; until that is wired
  in, this is a presence check, not an exact row-by-row match
- **G17 [WARNING]** Builder reads every Silver input listed in LLD §5.3
  Inputs column — no missing reads, no extra reads

## Phase 6 — DAG Wiring

- **G18 [CRITICAL]** `gold_build` TaskGroup contains exactly the builders
  listed in LLD §5.3 (derived at runtime); no more, no fewer
- **G19 [CRITICAL]** Dependency edge:
  `reconciliation_silver >> gold_build >> reconciliation_gold`
- **G20 [CRITICAL]** Every Gold `gold_build` builder task uses
  `SparkSubmitOperator` (IL-011). Scoped to the builder tasks only —
  `reconciliation_gold` may legitimately be a `PythonOperator`.

## Phase 7 — Traceability

- **G21 [WARNING]** Each builder's docstring cites LLD §5.3 row, STM row,
  DMS §4 subsection, DQS rule range
- **G22 [INFO]** Contract `ddl_path` and `dq_path` resolve to existing
  files

## Phase 8 — Report

Same format as `validate-silver` Phase 7. Exit `0` on no CRITICAL, `1`
otherwise. The Makefile `validate-gold` target wraps this skill's
`scripts/validate_gold.py`. Cite the pattern references the audit was run
against (e.g. `Checked against inputs/code/v*/gold-aggregation-pattern.md`
and `scripts/gold_builder.py.snippet`) so drift findings are traceable to
the current builder pattern.

## Learnings & Corrections

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017. Note especially IL-016 —
when validate-gold is invoked under `implement-stories`, filter findings
to the current story's `.skill-paths` set; never halt on sibling-story
pre-existing failures.

### Active Learnings

(no skill-specific learnings yet)
