---
name: update-silver
description: >
  Updates an existing Silver layer implementation in response to changes in
  the upstream LLD §5.2, DMS §3, STM Bronze-to-Silver sheet, or DQS §2.
  Preserves unchanged modules, increments versioning per the 3-scenario rule
  (chapter-4 CLAUDE.md), and surfaces ripple effects to the Gold layer.

  Modes:
  - Story mode: STORY-NN-NNN — apply only the changes the story authorizes
  - Diff mode (default): compare current Silver implementation against the
    latest approved LLD/DMS/STM/DQS and update any drifted module
  - Full mode: regenerate every Silver module against the latest upstream

  Use when the user asks to:
  - Update or revise Silver layer code after a DMS / STM / DQS change
  - Apply LLD edits to existing Silver transforms
  - Reconcile Silver code with a re-approved upstream artifact set
argument-hint: "[STORY-NN-NNN | 'diff' | 'full']"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Update Silver Layer

You are a senior Data Engineer. The Silver layer already exists; your job is
to bring it back into alignment with the current approved LLD / DMS / STM /
DQS without rewriting unchanged code.

## Workspace Discovery

```bash
WORKSPACE_ROOT="$(cd "$(dirname "${CLAUDE_PLUGIN_ROOT:-.}")" && pwd)"
PROJECT_ROOT="$WORKSPACE_ROOT/patient_360"
UPSTREAM_ROOT="$(cd "$WORKSPACE_ROOT/../chapter-4" && pwd)"
LEARNINGS_QUEUE="$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl"
```

## Phase 0 — Upstream Approval Gate

Same as `create-silver`: refuse to run unless LLD / DMS / STM / DQS /
Stories are all `Approved` per the metadata block / Summary sheet.

## Phase 1 — Compute the Diff

1. **Read current Silver modules** under
   `$PROJECT_ROOT/src/patient_360/silver/transform_*.py`. Extract from each
   module's docstring the LLD §5.2 row, STM row, DMS section it was
   generated against.
2. **Read the latest upstream** (LLD §5.2, DMS §3, STM Bronze-to-Silver,
   DQS §2). Build the up-to-date specification.
3. **Diff per table**:
   - Column add/remove/rename in DMS §3 → contract + module signature drift
   - STM Bronze-to-Silver rule change → transformation logic drift
   - DQS DQ-FLD-NNN change → DQ rule file drift
   - LLD §5.2 `empty_input_behavior` or `se_action_if_failed` change → config drift
   - SCD2 hash column change in DMS §6 → `apply_scd2` call drift
4. **Report drift** before writing any change:
   ```
   Drift detected:
     clinical_patients: 1 column added (race_code), 2 STM rules changed
     billing_claims:    se_action_if_failed flipped fail → drop
     reference_payers:  hash column list added (is_active)
   No drift in 10 other Silver tables.
   ```

## Phase 2 — Apply the 3-Scenario Versioning Rule

Per chapter-4 CLAUDE.md update-versioning rules:

| Scenario | Trigger | Action |
|---|---|---|
| A | New LLD/DMS/STM/DQS major version exists upstream | Tag changed modules with comment `# Updated for LLD v{N+1}` |
| B | Same upstream version, today ≠ source-of-truth date | Bump module-level docstring date; `.bak` the prior file |
| C | Same upstream version, same day re-run | Edit in place; no `.bak` |

Detect the scenario by reading the upstream LLD version + date against the
last-mod stamp on the silver modules.

## Phase 3 — Apply the Drift

For each drifted Silver module:

- **Column add/remove in DMS §3**: update the projection list, update
  `contracts/<silver_table>.yml`, regenerate the contract test
- **STM rule change**: re-emit the transformation block; preserve the
  surrounding boilerplate (imports, return, DQ call); cite the new STM row
- **DQ rule change**: re-copy `chapter-4/outputs/dqs/v*/se-rules/<table>.yaml`
  → `patient_360/dq_rules/<table>.yml`
- **`se_action_if_failed` / `empty_input_behavior` flip**: update the
  `run_dq` keyword arg and the per-table YAML config in
  `airflow/configs/silver/<table>.yml`
- **SCD2 hash column change**: update the `apply_scd2` `hash_columns` list;
  re-run a smoke test against synthetic data; flag a record_hash
  recomputation pass — every existing row in the target Delta table is
  now invalidated unless you also run the helper's hash backfill

## Phase 4 — Ripple to Gold

If the changed Silver column is consumed by a Gold builder
(`gold/build_patient_summary.py`, `build_patient_clinical_history.py`,
`build_patient_billing_summary.py`), surface a recommended `update-gold`
invocation:

```
Recommended downstream: /developer-plugin:update-gold "<EPIC-NN>"
  Reason: clinical_patients.race_code is read by patient_summary.race join.
```

Do NOT auto-invoke update-gold — the user decides.

## Phase 5 — Tests + DAG

- Regenerate or patch `tests/silver/test_transform_<table>_unit.py` for the
  changed schema / DQ args.
- If `silver_dimensions` / `silver_facts` task groups gained or lost a task
  (rare — table additions/removals only), patch
  `airflow/dags/patient360_hourly_v1.py`.

## Phase 6 — Verify and Report

Run `/developer-plugin:validate-silver`. Show drift summary, files touched,
files preserved, and any ripple recommendations to the user.

## Learnings & Corrections

Meta-rules: append corrections to
`chapter-6/memory/developer/learnings-queue.jsonl`. If a correction implies
the LLD itself is wrong, add the row to `developer-plugin/LLD-DEVIATIONS.md`
and recommend a `/technical-lead-plugin:update-lld` cycle.

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017 — every rule applies here too
(same runtime, same DQ stack, same Airflow constraints).

### Active Learnings

(no chapter-6-specific learnings yet)
