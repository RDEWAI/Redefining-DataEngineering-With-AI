---
name: update-gold
description: >
  Updates an existing Gold layer implementation in response to changes in
  the upstream LLD §5.3, DMS §4, STM Silver-to-Gold sheet, DQS §2-3, or in
  the Silver layer that Gold reads from. Preserves unchanged builders,
  increments versioning per the 3-scenario rule, and warns when Silver
  inputs have changed in a way that requires a Gold rebuild.

  Modes:
  - Story mode: STORY-NN-NNN — apply only story-authorized changes
  - Diff mode (default): compare current Gold against the latest upstream
    + Silver contracts and update any drifted builder
  - Full mode: regenerate every Gold builder

  Use when the user asks to:
  - Update or revise Gold layer code after a Silver / DMS / STM / DQS change
  - Reconcile Gold builders with re-approved upstream artifacts
  - Apply ripple changes from `update-silver` to Gold
argument-hint: "[STORY-NN-NNN | 'diff' | 'full']"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Update Gold Layer

The Gold layer already exists; bring it back into alignment with the
current approved upstream + Silver contracts without rewriting unchanged
code.

## Workspace Discovery

```bash
WORKSPACE_ROOT="$(cd "$(dirname "${CLAUDE_PLUGIN_ROOT:-.}")" && pwd)"
PROJECT_ROOT="$WORKSPACE_ROOT/patient_360"
UPSTREAM_ROOT="$(cd "$WORKSPACE_ROOT/../chapter-4" && pwd)"
```

## Phase 0 — Upstream Approval Gate

Refuse to run unless LLD / DMS / STM / DQS / Stories AND the Silver
contracts under `patient_360/contracts/<silver_table>.yml` are all
`Approved`. Gold cannot be updated against an in-flight Silver change.

## Phase 1 — Compute the Diff

1. **Read current Gold builders** under `gold/build_*.py` — extract the
   LLD §5.3 row, STM row, DMS section, DQ rule range each was generated
   against.
2. **Read the latest upstream** (LLD §5.3, DMS §4, STM Silver-to-Gold,
   DQS §2-3 Gold rules) + the current Silver contracts.
3. **Diff per Gold table**:
   - DMS §4 column add/remove/rename → contract + builder projection drift
   - STM Silver-to-Gold rule change → join/aggregation drift
   - DQS Gold rule change → DQ rule file drift
   - **Silver contract change for a column that Gold reads** → builder
     projection drift (e.g. `clinical_patients.race_code` added in Silver
     and consumed by `patient_summary`)
   - LLD §5.3 input list change → join graph drift
4. **Report drift** before writing any change. Include a "Silver inputs
   affecting Gold" subsection that lists which Silver columns changed and
   which Gold tables consume them.

## Phase 2 — 3-Scenario Versioning

Same as `update-silver` (A: new upstream version, B: same version new
date, C: same-day re-run). Detect from upstream LLD version + date
against the last-mod stamp on the Gold modules.

## Phase 3 — Apply the Drift

- **DMS §4 column change**: update the projection, the `contracts/<gold_table>.yml`
  schema, the contract test
- **STM rule change**: re-emit the join/aggregation block; preserve
  boilerplate
- **DQ rule change**: re-copy
  `chapter-4/outputs/dqs/v*/se-rules/<gold_table>.yaml` →
  `dq_rules/<gold_table>.yml`
- **Silver input change**: update the builder's `read_silver_delta` call
  if the table list changed; update the projection if a Silver column was
  renamed; if a Silver column was removed and Gold consumed it, **stop
  with CRITICAL** — operator must choose between updating Gold's
  semantics or reverting the Silver change
- **`action_if_failed` change**: Gold defaults to `fail`; an upstream
  change relaxing this requires explicit confirmation via `AskUserQuestion`

## Phase 4 — DAG Wiring Patch

If LLD §5.3 added or removed a Gold table (rare — Phase 2 may grow this
to 5 tables), patch the `gold_build` TaskGroup. Otherwise the DAG
edge is unchanged.

## Phase 5 — Tests

Regenerate the unit test for any builder whose schema, joins, or DQ args
changed. `is_current=True` assertion for SCD2 dim reads stays in every
test.

## Phase 6 — Verify and Report

Run `/developer-plugin:validate-gold`. Show drift summary, files touched,
files preserved, and any "Silver column removed but Gold still reads it"
blockers.

## Learnings & Corrections

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017.

### Active Learnings

(no chapter-6-specific learnings yet)
