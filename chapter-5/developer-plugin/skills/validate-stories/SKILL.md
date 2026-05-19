---
name: validate-stories
description: >
  Verifies that the code implementation satisfies every acceptance criterion
  of one or more Scrum stories (and every epic-level AC for an epic target).
  Combines a static-heuristic AC scan (keyword/path checks derived from the
  create-*/update-* skills' Story → Deliverable Map) with the matching
  downstream validate-* skill (validate-ingestion / validate-dag /
  validate-pipeline). Read-only — never flips Status or AC checkboxes.
  Use when the user asks to:
  - Validate STORY-NN-NNN / EPIC-NN against its acceptance criteria
  - Check AC compliance before marking a story Done
  - Confirm an implementation is ready to close out
argument-hint: "[STORY-NN-NNN | EPIC-NN | 'Sprint N' | comma-list]"
allowed-tools: Read, Grep, Glob, Bash, Skill
context: fork
---

# Validate Scrum Stories

You are a plan-driven verifier. For each target story, you load its
**execution plan** (written by `implement-stories`), run the per-task
validator declared in the plan, annotate the plan with per-AC pass/fail
and evidence, and produce an advisory report. You never modify story
markdown files. You DO update the plan JSON.

## Plan-first workflow

Every action this skill takes is sourced from
`{stories_dir}/v{N}/plans/STORY-NN-NNN.plan.json`:

```bash
PLAN=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
         --mode load-plan --story STORY-NN-NNN)
```

- **No plan on disk** → the story was never implemented via the new
  orchestrator. Fall back to the legacy path: build an in-memory plan
  (`--mode build-plan`, no `--save`) and validate off that. Warn in the
  output trailer so the user knows the plan was ephemeral.
- **Plan exists** → read `tasks[]` and `acceptance_criteria[]`.

For each task in the plan:

1. Run the task's `validator` (e.g. `validate-ingestion`, `validate-dag`,
   `validate-scaffold`, `validate-pipeline`) against the task's
   `paths` / `artifacts` only. Use the `Skill` tool.
2. Parse the validator output. Set `tasks[i].validator_status` to
   `pass` / `fail` / `indeterminate`.

For each AC in `acceptance_criteria[]`:

1. Read its `task_ids`. The AC is covered if EVERY task it references
   reports `validator_status == "pass"` AND a structural/grep check of
   the AC text against the generated code succeeds. Set
   `ac.validation.status` accordingly and fill `ac.validation.evidence`
   with a short citation (file:line or validator output excerpt).
2. For behavioural ACs with no paths, pass if ANY task covers them
   (OR-logic).

Overall plan status after this phase:
- all ACs `pass` + all tasks `pass` → plan `status = "validated"`.
- any AC `fail` or task `fail` → plan `status = "failed"`.

Persist the plan after updating.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`.

## Coding Patterns Handbook

Load the pattern doc this skill checks against (read-only; no freshness prompt):

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "WARNING: inputs/code/v*/ not found — test-pattern conformance will be INDETERMINATE."
fi
```

**Pattern docs consulted:**

- `$PATTERNS_DIR/test-pattern.md` — expected pytest layout + integration marker

### References trailer (in output)

Cite each pattern doc consulted, e.g. `Checked against inputs/code/v1/test-pattern.md §layout`.

## Validator Dispatch (content-based classification — no config)

Per-story validator is resolved from the story's acceptance-criteria content
(same classifier the orchestrator uses):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode classify --story STORY-NN-NNN
```

Map `skill_kind` to the validator by literal convention:

| `skill_kind` | validator skill       |
|--------------|-----------------------|
| `scaffold`   | `validate-scaffold`   |
| `dag`        | `validate-dag`        |
| `ingestion`  | `validate-ingestion`  |
| `pipeline`   | `validate-pipeline`   |
| `unknown`    | — (see below)         |

If `skill_kind == "unknown"` OR `confidence == "low"`, emit a WARNING
(`"classifier returned '<kind>' with low confidence for STORY-NN-NNN — AC
verdicts based on heuristics only; reasons: <list>"`) and skip Phase 3.

## Phase 0.a — Argument Resolution (mandatory, runs first)

The Skill-tool argument frequently fails to reach forked subagents. Resolve
the target via the shared resolver, which checks four sources in order:
`$SKILL_ARG` → `{workspace_root}/.skill-arg` → conversational arg → auto-mode.

```bash
# Step 1: capture the user's conversational input. Substitute the
# bracketed text below with the EXACT message the user supplied after
# the skill name; if no message was supplied, leave it as an empty
# string. This is the ONLY substitution this skill requires.
CONV_ARG='<<EXACT_CONVERSATIONAL_TEXT_FROM_USER_OR_EMPTY_STRING>>'

# Step 2: run the shared resolver. It auto-discovers the workspace
# from $PWD, so no {workspace_root} substitution is required. Output is
# two lines on stdout: the resolved value, then the source token.
read -r RESOLVED_ARG RESOLVED_SOURCE < <(
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_skill_arg.sh" "$CONV_ARG" \
    | paste -sd' ' -
)
```

Print this banner as the **first line** of skill output:

```
RESOLVED TARGET: <value> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__>)
```

If `$RESOLVED_SOURCE == EMPTY`, fall through to the skill's existing
clarification step (typically `AskUserQuestion`). DO NOT ask the user before
running this resolver.

## Workflow

### Phase 0: Resolve Target Set

Same argument grammar as `implement-stories` (story/epic/sprint/comma-list).
Normalize to uppercase and zero-padded IDs. For `EPIC-NN` / `Sprint N`, expand
using the helper:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode parse-epic --epic EPIC-02
```

### Phase 1: Parse Each Story

For each target story, call:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode parse-story --story STORY-NN-NNN
```

Capture from the JSON: `status`, `epic_id`, `depends_on`, and `ac_lines[]`
(each line has `index`, `checked`, `text`, `line`).

### Phase 2: AC Verification — verifier block preferred, heuristics fallback

**Preferred path — explicit `## Verification` block.** If the story file
contains a `## Verification` YAML block (declared by the author, the
scrum-master skill, or a retrofit pass), run the mechanical verifier:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/../scripts/verify_acs.py STORY-NN-NNN --json
```

(The script lives at `developer-plugin/scripts/verify_acs.py`; its module
docstring is the authoritative schema spec.) The JSON output gives per-AC
`status: PASS|FAIL|INDETERMINATE` plus each check's detail. Use those
verdicts verbatim — do NOT re-run the heuristics below for that story.

Verifier types: `file_exists`, `file_count`, `grep`, `grep_count`, `pytest`,
`validator`, `manual` (explicit INDETERMINATE for runtime-only ACs).

**Fallback path — heuristic AC verification.** Only when no Verification
block is present, run one or more of these static checks — no code
execution. Every AC must receive exactly one verdict: **PASS**, **FAIL**, or
**INDETERMINATE**.

**Rules are derived from the story's AC text itself — not from hardcoded
per-epic tables.** This is what makes the skill project-agnostic.

For each AC:

1. **Path tokens.** Pull every backtick-quoted path token from the AC text
   (e.g. `` `src/foo/bar.py` `` or `` `airflow/configs/patients.yml` ``).
   Resolve each against `{project_root}` (from the discovery helper) and
   then against `{workspace_root}`.
   - If the token contains a `{placeholder}` → INDETERMINATE (pattern, not a file).
   - Else, file exists → PASS. Absent → FAIL with the resolved path.
2. **Identifier tokens.** Backtick-quoted tokens without a file extension
   (e.g. `` `load_table_config` ``, `` `EmptyInputError` ``) are symbols.
   If the same AC also mentions a file token, `Grep` for the symbol inside
   that file; ≥1 match → PASS, 0 → FAIL.
3. **YAML key:value pairs.** If the AC text contains `key: value` in a code
   fence or inline code (e.g. `` `empty_input_behavior: fail` ``) and an AC
   path token resolves to a `.yml`/`.yaml` file, verify the pair is present.
4. **Counts.** Text like "13 YAML files" or "all 18 tables" → count the AC's
   resolved directory contents and compare.
5. If none of the above apply → **INDETERMINATE**. Do not guess.

Deterministic and file-local only: no execution, no network, no Spark session.

### Phase 3: Downstream Validator

Run the classifier, then dispatch the matching `validate-{kind}` skill via
the `Skill` tool. Capture its final `Result: PASS / FAIL` line and the
`CRITICAL` count. Surface every CRITICAL finding whose message mentions a
file that the target story's ACs reference — those are AC-attributable
failures.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode classify --story STORY-NN-NNN
```

If `skill_kind == "unknown"` or `confidence == "low"`, skip this phase and
emit the WARNING described in the Validator Dispatch section above.

### Phase 4: Epic-Level ACs (epic target only)

If the target is `EPIC-NN`, also run the helper against the epic file:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode parse-epic --epic EPIC-NN
```

Apply the same Phase 2 heuristics to each item in `epic_ac_lines[]`.

### Phase 5: Drift Check

For every target story, if `status == "Done"` but any AC in its body is
`- [ ]` → emit a CRITICAL finding:

```
DRIFT: STORY-NN-NNN Status cell says Done, but AC 3, AC 5 are still unchecked.
Run /developer-plugin:complete-stories (it reads AC truth, not Status) to
resolve, or edit the story file to reflect reality.
```

## Output Format

Report per target in this exact shape. Keep the width under 100 characters so
the skill output renders cleanly in most terminals.

```
Story STORY-02-002 — Implement Generic Ingestion Runner | Status: To Do

Acceptance Criteria:
  AC 1: Runner reads per-table YAML config ..................... PASS
  AC 2: Source data read from DuckDB synthea.{table} ............ PASS
  AC 3: Metadata columns ds, _ingested_at, _source_batch_id .... PASS
  AC 4: StructType schema enforced (no inference) .............. PASS
  AC 5: Inline SE validation via se_runner.py .................. PASS
  AC 6: action_if_failed: fail | drop | ignore ................. PASS
  AC 7: Delta replaceWhere ds = '{ds}' ......................... PASS
  AC 8: empty_input_behavior (fail | write_empty) .............. PASS
  AC 9: Bootstrap soft-import fallback ......................... INDETERMINATE

  Summary: 8/9 PASS, 0 FAIL, 1 INDETERMINATE

Downstream: /developer-plugin:validate-ingestion → Result: PASS
  (0 CRITICAL, 2 WARNING, 5 INFO)

Drift check: none

Overall: PASS (with 1 INDETERMINATE AC — manual review required before closing)
```

For an epic target, append an **Epic-Level** block:

```
Epic EPIC-02 — Acceptance Criteria (Epic-Level):
  AC 1: All 13 source tables land in Bronze Delta .............. INDETERMINATE
  ...
  Summary: 2/11 PASS, 0 FAIL, 9 INDETERMINATE

Rollup:  11 stories  |  Done: 0  |  In Progress: 0  |  To Do: 11
         Implied epic status: To Do
```

Final line for the whole run:

```
Overall: <PASS | FAIL | PASS-WITH-INDETERMINATE>
```

**This skill writes nothing.** It does not flip Status cells and does not
tick checkboxes. Completion edits belong to `complete-stories`.

## Edge Cases

- **INDETERMINATE overload** — if more than half of a story's ACs are INDETERMINATE, flag it in the final summary: "heuristics missing for this story; add patterns to validate-stories or accept manual review."
- **Story file missing** — helper returns an error; propagate as FAIL.
- **Downstream validator itself errors** (non-zero exit, no Result line) — treat as FAIL and surface the error text.
- **Epic with children in mixed Done/not-Done states** — still valid; the rollup section tells the user which ones block epic closure.

## Learnings & Corrections

_No learnings recorded yet._
