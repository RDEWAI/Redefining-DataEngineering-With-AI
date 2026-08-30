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

Run the shared discovery helper and substitute the returned tokens into
every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. Never hardcode
project or chapter names in edits.

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

Run the shared resolver (checks the four sources above in order):

```bash
CONV_ARG='<<EXACT_CONVERSATIONAL_TEXT_FROM_USER_OR_EMPTY_STRING>>'
read -r RESOLVED_ARG RESOLVED_SOURCE < <(
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_skill_arg.sh" "$CONV_ARG" | paste -sd' ' -
)
```

Echo a banner as the FIRST line of skill output:
`RESOLVED TARGET: <value> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__>)`.
Use `$RESOLVED_ARG` (NOT `$ARGUMENTS`) everywhere below as the story/epic
argument. If `$RESOLVED_SOURCE == EMPTY`, fall through to `AskUserQuestion`.

## Phase 0.5 — Path Scoping (optional, set by the orchestrator)

If `{workspace_root}/.skill-paths` exists, read it — each non-empty line is
a path in scope for THIS invocation. Process ONLY those paths; ignore other
paths the story AC names (they belong to other skills and the orchestrator
dispatches them separately). Delete `.skill-paths` after consuming it. When
the file is absent (direct human invocation), fall through to the standard
phases.

## Phase 1 — Upstream Approval Gate

Refuse to run unless the upstream artifacts LLD / DMS / STM / DQS /
Stories are all `Approved` (gate on each artifact's own `Status` field)
**and** the Silver layer is in place — Silver tables exist at
`warehouse/{env}/silver/<domain>/<table>/` and the Silver story is
`Done`. The Silver contracts under
`patient_360/contracts/<silver_table>.yml` carry no `Status` field, so do
NOT gate on a contract "Approved" flag. Gold cannot be updated against an
in-flight Silver change.

## Phase 2 — Compute the Diff

### Phase 2.0 — MANDATORY snippet read-routing audit (run FIRST, cannot be skipped)

Before the artifact-column/join/DQ diff below, you MUST audit every
in-scope builder's Silver reads against the CURRENT
`inputs/code/v*/scripts/gold_builder.py.snippet`. The snippet is the
canonical generator source; a builder that reads a Silver **FACT** through
a bare `spark.table("unity.silver.<fact>")` is out of sync with the snippet
and IS drift — even when every column/join/DQ rule still matches. Do NOT
conclude "NO DRIFT" until this audit passes.

Run, for each in-scope builder:

```bash
grep -nE 'spark\.table\("unity\.silver\.' src/patient_360/gold/<builder>.py
```

Classify each matched Silver table:
- **DIM** — SCD2, carries `is_current` (per DMS §3): `clinical_patients`,
  `reference_providers`, `reference_organizations`, `reference_payers`, and
  any other SCD2 dimension. DIMS are read via `_read_current`. A bare
  `spark.table(...)` on a DIM inside `build(...)` is also drift (should be
  `_read_current`), but in this pipeline dims already use `_read_current`.
- **FACT** — ds-partitioned append-only (per LLD §7), NO `is_current`:
  `clinical_encounters`, `clinical_conditions`, `clinical_procedures`,
  `clinical_medications`, `clinical_observations`, `clinical_immunizations`,
  `clinical_careplans`, `billing_claims`, and any other non-SCD2 Silver
  table. FACTS MUST be read via `_read_fact_current`.

The ONLY allowed `spark.table("unity.silver.` matches are the two inside
the `_read_current` and `_read_fact_current` helper bodies. If a match
appears anywhere inside `build(...)` for a FACT, that is confirmed drift →
apply the "Snippet read-routing change" step in Phase 4. Re-run the grep
after applying; it must show only the two helper-body matches.

### Phase 2.1 — Artifact diff

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
     projection drift (hypothetical example: a new
     `clinical_patients.<col>` added in Silver and consumed by
     `patient_summary` — use the actual changed column from the diff, not
     a placeholder name)
   - LLD §5.3 input list change → join graph drift
   - **Snippet read-routing drift** → the current
     `inputs/code/v*/scripts/gold_builder.py.snippet` is the canonical
     Silver-read pattern. Classify every Silver input the builder reads as
     a **DIM** (SCD2, carries `is_current` per DMS §3 → must be read via
     `_read_current`) or a **FACT** (ds-partitioned append-only per LLD §7,
     no `is_current` → must be read via `_read_fact_current`, latest-ds
     only). If a builder reads a FACT through a bare
     `spark.table("unity.silver.<fact>")` inside `build(...)` while the
     snippet routes facts through `_read_fact_current`, that is builder
     drift — the bare read double-counts across ds and breaks the Gold
     grain contract (DQS DQ-FLD-143). Also treat a missing
     `_read_fact_current` helper in a builder that reads any fact as drift.
4. **Report drift** before writing any change. Include a "Silver inputs
   affecting Gold" subsection that lists which Silver columns changed and
   which Gold tables consume them.

## Phase 3 — 3-Scenario Versioning

Same as `update-silver` (A: new upstream version, B: same version new
date, C: same-day re-run). Detect from upstream LLD version + date
against the last-mod stamp on the Gold modules.

## Phase 4 — Apply the Drift

- **DMS §4 column change**: update the projection, the `contracts/<gold_table>.yml`
  schema, the contract test
- **STM rule change**: re-emit the join/aggregation block from
  `inputs/code/v*/scripts/gold_builder.py.snippet` (per
  `gold-aggregation-pattern.md`); preserve boilerplate
- **Snippet read-routing change**: re-emit ONLY the Silver-read block from
  the snippet. Ensure the `_read_fact_current` helper (verbatim from the
  snippet, placed right after `_read_current`) is defined in the module.
  For each drifted FACT, replace the bare
  `spark.table("unity.silver.<fact>")` with
  `_read_fact_current(spark, "<fact>")`, preserving any trailing
  `.alias(...)` unchanged. DIM reads stay on `_read_current`. Touch nothing
  else — joins, projections, `OUTPUT_COLUMNS`, the empty-input guard, the
  `run_dq` gate, and the `insertInto` write are all unchanged. `del ds` may
  remain (the helper keys off max(ds), so the passed `ds` stays unused).
- **DQ rule change**: re-copy the `rules:` subtree (plus the `dq_env`
  block) from
  `outputs/dqs/v*/se-rules/se-rules-<gold_table-hyphenated>.yaml` →
  `dq_rules/<gold_table>.yml`. The upstream filename is hyphenated
  (e.g. `se-rules-patient-summary.yaml`); compare and copy only the
  rules subtree semantically, not the whole file byte-for-byte.
  **`dq_env.<ENV>.table_name` MUST be the fully-qualified `unity.gold.<table>`**
  (3-part), never bare — it is the SE rule-filter key (must equal the
  `target_table` `se_runner` passes to `with_expectations`) and the base for the
  managed `<target>_error`/`_stats` FQNs; a bare name triggers the UC
  empty-namespace `fullTableNameForApi` AIOOBE on the error-table write.
- **Silver input change**: update the builder's `read_silver_delta` call
  if the table list changed; update the projection if a Silver column was
  renamed; if a Silver column was removed and Gold consumed it, **stop
  with CRITICAL** — operator must choose between updating Gold's
  semantics or reverting the Silver change
- **`action_if_failed` change**: the action is resolved per-rule /
  per-env from the SE-rules `dq_env` block (DEV/QA=ignore, PROD=fail);
  an upstream change to the PROD-env action requires explicit
  confirmation via `AskUserQuestion`

## Phase 5 — DAG Wiring Patch

If LLD §5.3 added or removed a Gold table, patch the `gold_build`
TaskGroup to contain exactly the builders listed in LLD §5.3. Otherwise
the DAG edge is unchanged.

## Phase 6 — Tests

Regenerate the unit test for any builder whose schema, joins, or DQ args
changed. `is_current=True` assertion for SCD2 dim reads stays in every
test.

## Phase 7 — Verify and Report

Run `/developer-plugin:validate-gold`. Show drift summary, files touched,
files preserved, and any "Silver column removed but Gold still reads it"
blockers.

## Learnings & Corrections

### Inherited Learnings

See `create-silver/SKILL.md` IL-001..IL-017.

### Active Learnings

(no skill-specific learnings yet)
