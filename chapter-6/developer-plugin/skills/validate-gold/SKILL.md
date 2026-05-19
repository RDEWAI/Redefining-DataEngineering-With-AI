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

```bash
WORKSPACE_ROOT="$(cd "$(dirname "${CLAUDE_PLUGIN_ROOT:-.}")" && pwd)"
PROJECT_ROOT="$WORKSPACE_ROOT/patient_360"
UPSTREAM_ROOT="$(cd "$WORKSPACE_ROOT/../chapter-4" && pwd)"
```

## Phase 0 — Pre-Conditions

Locate latest LLD / DMS / STM / DQS under `$UPSTREAM_ROOT/outputs/`. If
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
  DMS §4 (set equality + type match)
- **G7 [INFO]** Contract `tags` reflect DMS §4 owner/consumer group

## Phase 3 — SCD2 Read Pattern (Gold-specific)

For each builder, for every SCD2 dim input
(`clinical_patients`, `reference_organizations`, `reference_providers`,
`reference_payers`):

- **G8 [CRITICAL]** Read is filtered by `is_current = True` (current-state
  Gold pattern per LLD §5.2 SCD2 implications)
- **G9 [WARNING]** Pattern is `F.col("is_current") == True` rather than
  raw Python truthiness check (the latter is silently wrong against
  Spark Column types)
- **G10 [CRITICAL]** Builder does NOT import `apply_scd2` (Gold never
  performs SCD2 writes — LLD §5.3 implication)

## Phase 4 — DQ Gate (every Gold task)

- **G11 [CRITICAL]** `run_dq` is called inside the builder
- **G12 [CRITICAL]** `action_if_failed="fail"` is the table-level default
  (Gold tables are consumer-facing; per-rule overrides allowed but
  per-table default stays `fail`)
- **G13 [CRITICAL]** `run_dq` is called BEFORE the `write_gold_delta`
  step in source order
- **G14 [WARNING]** `dq_rules/<gold_table>.yml` matches
  `chapter-4/outputs/dqs/v*/se-rules/<gold_table>.yaml` byte-for-byte
- **G15 [CRITICAL]** SE `with_expectations(...)` wraps in a no-arg
  lambda (IL-007)

## Phase 5 — Join Correctness (vs STM Silver-to-Gold)

- **G16 [CRITICAL]** Every join in the builder maps to a row in the STM
  Silver-to-Gold sheet for that table
- **G17 [WARNING]** Builder reads every Silver input listed in LLD §5.3
  Inputs column — no missing reads, no extra reads

## Phase 6 — DAG Wiring

- **G18 [CRITICAL]** `gold_build` TaskGroup contains exactly the 3
  builders (LLD §5.3); no more, no fewer
- **G19 [CRITICAL]** Dependency edge:
  `reconciliation_silver >> gold_build >> reconciliation_gold`
- **G20 [CRITICAL]** Every Gold task uses `SparkSubmitOperator` (IL-011)

## Phase 7 — Traceability

- **G21 [WARNING]** Each builder's docstring cites LLD §5.3 row, STM row,
  DMS §4 subsection, DQS rule range
- **G22 [INFO]** Contract `ddl_path` and `dq_path` resolve to existing
  files

## Phase 8 — Report

Same format as `validate-silver` Phase 7. Exit `0` on no CRITICAL, `1`
otherwise. The Makefile `validate-gold` target wraps this skill's
`scripts/validate_gold.py`.

## Learnings & Corrections

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017. Note especially IL-016 —
when validate-gold is invoked under `implement-stories`, filter findings
to the current story's `.skill-paths` set; never halt on sibling-story
pre-existing failures.

### Active Learnings

(no chapter-6-specific learnings yet)
