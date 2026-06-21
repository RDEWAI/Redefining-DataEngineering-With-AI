---
name: update-silver
description: >
  Updates an existing Silver layer implementation in response to changes in
  the upstream LLD §5.2, DMS §3, STM Bronze-to-Silver sheet, or DQS §2.
  Preserves unchanged modules, increments versioning per the 3-scenario rule
  (defined in this skill's Phase 2 table), and surfaces ripple effects to the
  Gold layer.

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
UPSTREAM_ROOT="$WORKSPACE_ROOT"
LEARNINGS_QUEUE="$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl"
```

## Phase 0 — Resolve the Effective Argument

**FIRST — resolve the effective argument. Do this before any other step.**

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
   `$WORKSPACE_ROOT/.auto-mode` exists → full-mode default.
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
argument.

## Phase 0.5 — Path Scoping (optional, set by the orchestrator)

If `$WORKSPACE_ROOT/.skill-paths` exists, read it — each non-empty line is
a path in scope for THIS invocation. Process ONLY those paths; ignore other
paths the story AC names (they belong to other skills and the orchestrator
dispatches them separately). Delete `.skill-paths` after consuming it. When
the file is absent (direct human invocation), fall through to the standard
phases.

## Phase 0.6 — Upstream Approval Gate

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
   - **Write-target / catalog drift** → the module (or the shared
     `utils/scd2.py`) writes to a **filesystem path** (`target_path`,
     `DeltaTable.forPath`, `.save(<path>)`, ``delta.`<path>` ``) while LLD
     §5.2 specifies the **named UC FQN `unity.silver.<table>`**. This is a
     migration drift: rewrite SCD2 dims to `target_table="unity.silver.<dim>"`
     + `DeltaTable.forName`, facts to `insertInto("unity.silver.<table>")`
     (dynamic partition overwrite), and re-emit the per-table changelog DDL
     (Phase 3 "Write-target / catalog migration" bullet). Detect it by
     comparing each module's actual write call against the LLD §5.2 Output
     FQN — a `forPath`/`target_path`/`.save(`/`delta.\`` against a
     `unity.silver.*` LLD target IS drift, even when DMS columns are
     unchanged.
4. **Report drift** before writing any change:
   ```
   Drift detected:
     clinical_patients: 1 column added (race_code), 2 STM rules changed
     billing_claims:    se_action_if_failed flipped fail → drop
     reference_payers:  hash column list added (is_active)
   No drift in 10 other Silver tables.
   ```

## Phase 2 — Apply the 3-Scenario Versioning Rule

Apply the update-versioning rules below (this table is the source of truth for
the rule; the project `patient_360/CLAUDE.md` does not define it):

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
  `contracts/<silver_table>.yml`, regenerate the contract test, AND
  re-emit the per-table migration `ddl/migrations/<YYYYMMDD>_2<NN>_<silver_table>.sql`
  so its DDL columns match (see create-silver Phase 4 step 4 + IL-018) —
  this skill owns the Silver changelog DDL.
- **Write-target / catalog migration** (e.g. path-based `forPath` →
  `unity.silver.<table>` `forName` MERGE, or a stubbed changelog → hydrated
  DDL): rewrite the transform's `target_table` to the 3-part
  `unity.silver.<table>` FQN and (re)emit the hydrated changelog per
  create-silver Phase 4 step 4 + IL-018 (FQN + `LOCATION`, SCD2 dims
  unpartitioned / facts `PARTITIONED BY (ds)`, `<rollback>`). NEVER leave a
  bare `silver.` schema, a missing `LOCATION`, or `PARTITIONED BY (ds)` on
  an SCD2 dim.
- **STM rule change**: re-emit the transformation block; preserve the
  surrounding boilerplate (imports, return, DQ call); cite the new STM row
- **DQ rule change**: re-copy the `rules:` subtree from
  `outputs/dqs/v*/se-rules/se-rules-<table-with-hyphens>.yaml`
  (e.g. `se-rules-clinical-patients.yaml`) → `patient_360/dq_rules/<table>.yml`.
  Copy only the `rules:` subtree; the `dq_env` / `table_name` headers are
  environment-specific and stay local. **`dq_env.<ENV>.table_name` MUST be the
  FULLY-QUALIFIED `unity.silver.<table>`** (catalog.schema.table) — NOT the bare
  name. `se_runner` reads it as both the SE rule-filter key (it must equal the
  `target_table` passed to `with_expectations`) and the base for the managed
  error/stats table FQNs. A bare name reproduces the UC empty-namespace
  `fullTableNameForApi` AIOOBE on the error-table write.
- **`se_action_if_failed` / `empty_input_behavior` flip**: update the
  `run_dq` keyword arg and the per-table YAML config in
  `airflow/configs/silver/<table>.yml`
- **SCD2 hash column change**: update the `apply_scd2` `hash_columns` list;
  re-run a smoke test against synthetic data; flag a `_record_hash`
  recomputation pass — every existing row in the target Delta table is
  now invalidated unless you also run the helper's hash backfill

## Phase 4 — Ripple to Gold

If the changed Silver column is consumed by a Gold builder (read the Gold
builder module paths from LLD §5.3 Gold Tasks — in the current run
`gold/build_patient_summary.py`, `build_patient_clinical_history.py`,
`build_patient_billing_summary.py`; always re-read, do not hardcode), surface
a recommended `update-gold` invocation:

```
Recommended downstream: /developer-plugin:update-gold "<EPIC-NN>"
  Reason: clinical_patients.race_code is read by patient_summary.race join.
```

Do NOT auto-invoke update-gold — the user decides.

## Phase 5 — Tests + DAG

- Regenerate or patch `tests/silver/test_transform_<table>_unit.py` for the
  changed schema / DQ args.
- If `silver_dimensions` / `silver_facts` task groups gained or lost a task
  (rare — table additions/removals only), patch the project DAG file (read its
  path from LLD §4.2 / the existing `airflow/dags/*.py`; in the current run
  `airflow/dags/patient360_hourly_v1.py`). When patching edges, preserve the
  real LLD §4.2 per-task dependencies — never collapse to a flat fan-out.

## Phase 6 — Verify and Report

Run `/developer-plugin:validate-silver`. Show drift summary, files touched,
files preserved, and any ripple recommendations to the user.

## Learnings & Corrections

Meta-rules: append corrections to
`$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl`. If a correction implies
the LLD itself is wrong, recommend a `/technical-lead-plugin:update-lld`
cycle so the LLD is corrected at source.

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017 — every rule applies here too
(same runtime, same DQ stack, same Airflow constraints).

### Active Learnings

- **L-001** (2026-06-20): NEVER leave a Silver/Gold `dq_rules/<table>.yml` `dq_env.<ENV>.table_name` bare. `se_runner`'s bare-name target fallback qualifies to the **bronze** schema (`unity.bronze.<table>`), so a bare Silver name (a) routes the managed SE `_error`/`_stats` audit tables into the wrong schema AND (b) — because SE filters rules on `table_name == target_table` — matches ZERO rules, silently disabling DQ. ALWAYS emit the explicit 3-part FQN `unity.silver.<table>` (identical across DEV/QA/PROD).
- **L-002** (2026-06-21): Regenerated Silver Python MUST pass `make lint` (ruff `select=[E,F,I,UP]`, line-length 100). Regen had no lint gate and left UP037 (quoted `-> "F.Column"` — write `-> F.Column` unquoted) and E501 (>100-char `F.expr("…long SQL…")` strings — split across implicitly-concatenated string literals) debt that silently red-lined `make lint`. As the FINAL step ALWAYS run `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/` and confirm `make lint` exits 0 before reporting done.
