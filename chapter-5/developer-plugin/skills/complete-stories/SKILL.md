---
name: complete-stories
description: >
  Marks Scrum stories Done and rolls epic/backlog status up once every child
  is complete. BLOCKS completion if any story AC checkbox is unchecked, any
  dependency is not Done, any referenced deliverable is missing, or any
  epic-level AC is still open. Uses Edit (not Write) to flip only the Status
  cell and AC checkboxes, preserving every other line. If the gate blocks on
  ANY target, NOTHING is edited — the run is atomic from the user's view.
  Use when the user asks to:
  - Mark STORY-NN-NNN complete / close a story
  - Close out EPIC-NN / roll up epic status
  - "Are we done with sprint 3 yet?" (gate run without edits is acceptable)
argument-hint: "[STORY-NN-NNN | EPIC-NN | 'Sprint N' | comma-list]"
allowed-tools: Read, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Complete Scrum Stories

You are the hard gate between "code looks right" and "story is Done." You
edit story, epic, and backlog markdown files ONLY when every gate rule
passes. A single unchecked AC, missing dependency, absent deliverable, or
failing validator aborts the whole run — nothing is marked complete while
any task or story in the target epic is still open.

Plan-driven: when a story has a plan at
`{stories_dir}/v{N}/plans/STORY-NN-NNN.plan.json` (written by
implement-stories, annotated by validate-stories), this skill gates on the
plan. When no plan exists (legacy stories), it falls back to the original
AC-checkbox + deliverable-presence gate.

## Rollup rules

Three nested rollups, each atomic:

1. **Story → Done**: plan `status == "validated"` AND every AC
   `validation.status == "pass"` AND every dependency story is `Done` AND
   every deliverable path exists on disk. On success, tick the story's AC
   checkboxes, flip its Status cell to `Done`, set plan `status = "done"`
   and `completion.status = "done"`.
2. **Epic → Done**: every story in the epic file's `## Stories` table is
   `Done` AND every epic-level AC checkbox is ticked. On success, flip
   the epic's Status cell to `Done`.
3. **Backlog → Done**: every epic in the latest `BACKLOG-*.md` is `Done`.
   On success, flip the backlog's Status cell to `Done` and add a version
   history entry.

Each rollup runs after the preceding one succeeds. Rollup 2 only fires
after a story flips to Done (not on every `complete-stories` call).
Rollup 3 only fires after an epic flips to Done. So a reader running
`/developer-plugin:complete-stories STORY-02-004` gets the full cascade
automatically when that story is the last missing piece.

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

Same argument grammar as `implement-stories` and `validate-stories`
(story / epic / sprint / comma-list). Normalize to uppercase and zero-padded IDs.

### Phase 1: Hard Gate (atomic)

**Step 0 — Plan gate (new; runs before the legacy gate).**

For each target story, load its plan:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode load-plan --story STORY-NN-NNN
```

- **Plan exists** and `plan.status != "validated"` → BLOCK with
  `plan_not_validated`. Message: "run /developer-plugin:validate-stories
  STORY-NN-NNN first (plan is at `{plan_path}`)".
- **Plan exists** and any `acceptance_criteria[*].validation.status !=
  "pass"` → BLOCK with `ac_validation_fail`, citing failing ACs.
- **Plan exists** and any `tasks[*].status != "done"` → BLOCK with
  `task_not_done`.
- **Plan missing** → fall through to the legacy gate below (back-compat
  for stories implemented before the plan system landed).

**Step 1 — Run the legacy gate helper for every target.**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode gate --target STORY-NN-NNN
```

The helper auto-discovers the workspace by walking upward from CWD until it
finds a directory with both `outputs/stories/` and a cookiecutter-style
project (`pyproject.toml` + `src/<name>/`). It resolves `{project_root}`,
`{stories_dir}`, `{learnings_queue}`, and the backlog glob from that
anchor. No per-project flags are needed as long as CWD is at or under the
workspace root (or has it as an immediate subdirectory).

Exit code `0` = gate passes. Exit code `1` = blocked; JSON payload lists
every blocker.

Blocker codes the helper can emit:

| Code                      | Meaning                                                          |
|---------------------------|------------------------------------------------------------------|
| `ac_unchecked`            | A story AC is still `- [ ]`                                      |
| `dependency_not_done`     | A `Depends On:` story is not yet `Done`                          |
| `dependency_missing`      | A `Depends On:` story file is not found on disk                  |
| `missing_deliverable`     | An AC references a path that is not present on disk              |
| `invalid_status`          | Status cell is not one of To Do / In Progress / Done             |
| `epic_ac_unchecked`       | An epic-level AC is still `- [ ]`                                |
| `child:<code>`            | A child story's blocker (epic gates recurse)                     |
| `story_file_missing`      | Story file could not be resolved                                 |
| `epic_file_missing`       | Epic file could not be resolved                                  |
| `verifier_failure`        | `verify_acs.py` exited non-zero — at least one verifier FAILed   |
| `user_verification_missing` | Story has manual verifiers but no `User-Verified-By:` line     |
| `stack_unhealthy`         | Integration-test gate: Airflow `/health` or UC OSS API not 200   |
| `dag_trigger_failed`      | Integration-test gate: `airflow dags trigger <id>` returned non-zero |
| `dag_run_timeout`         | Integration-test gate: DAG did not reach `success` state in 10 min |

**Step 1.5 — Run automated verifiers via `verify_acs.py`.**

For each target story, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_acs.py STORY-NN-NNN
```

`verify_acs.py` is project-agnostic — it auto-detects the chapter-5 root
and reads each story's `## Verification` YAML to dispatch verifiers
(`pytest:`, `file_exists:`, `grep:`, `validator:`, `manual:`). Exit code
contract:

- `0` — every non-`manual:` verifier returned PASS (`manual:` are
  INDETERMINATE by design and require human sign-off — see Step 1.6).
- `1` — at least one verifier returned FAIL.
- `2` — runner error (malformed YAML, missing target, etc.).

A non-zero exit BLOCKS with code `verifier_failure`. Print the failing AC
and its verifier output. **The verifier is the gate** — without this step
"Done" means "checkbox is checked", not "the test actually passed". This
step is what makes the developer-plugin actually test+validate as part of
story completion.

**Step 1.6 — Require `User-Verified-By:` for stories with manual verifiers.**

Manual verifiers (`manual: <reason>`) are an explicit acknowledgment that
no machine can prove the AC. They MUST be signed off by a human before
Done. For each story whose `## Verification` block contains ≥1 `manual:`
spec, require a line like the following anywhere in the story (typically
at the bottom):

```
User-Verified-By: <name> <YYYY-MM-DD>
```

If the story has any `manual:` verifiers and the line is absent (or empty),
BLOCK with `user_verification_missing`. Message: "Story has N manual ACs
that need human sign-off. Add `User-Verified-By: <name> <date>` to the
story file once you have run the manual checks listed in `## How to Test
(User)`." Do NOT auto-add this line — it must come from the human.

**Step 1.7 — Integration-test stories: run the runtime gate.**

For each target story whose `Story Type` metadata is `integration-test`,
the gate additionally must prove the runtime is alive AND the named DAG
runs to success against UC OSS local. The skill operates entirely from
what the story declares — no project-specific names hardcoded.

1. **Stack health.** Read the story's `## How to Test (User)` Prerequisites
   to learn the expected ports (default `8081` for Airflow webserver,
   `8080` for UC OSS). Run:
   ```bash
   curl -fsS http://localhost:8081/health        # Airflow
   curl -fsS http://localhost:8080/api/2.1/unity-catalog/catalogs  # UC OSS
   ```
   If either fails, BLOCK with `stack_unhealthy`. Suggest the user run
   their `runtime-bootstrap` story's `## How to Test (User)` Steps first
   (typically `make dev-up`).
2. **DAG trigger.** Parse the DAG id from the story's `## Acceptance
   Criteria`. The validator's `STORIES-CLOSURE-003` rule already enforces
   "Airflow DAG" wording, so the AC text contains either a literal
   `airflow dags trigger <id>` or a backticked DAG id. Take the first
   match for `airflow\s+dags\s+trigger\s+(\S+)` or, failing that,
   ``\b([a-z0-9_]+_(?:hourly|daily|v\d+))\b`` from the AC body. Then run:
   ```bash
   airflow dags trigger "$DAG_ID"
   ```
   If trigger fails (non-zero exit), BLOCK with `dag_trigger_failed`.
3. **Wait for completion.** Poll up to 10 minutes:
   ```bash
   airflow dags list-runs -d "$DAG_ID" --state success
   ```
   If no success run appears within the timeout, BLOCK with
   `dag_run_timeout`. Print the most recent run's state.
4. **Re-run `verify_acs.py STORY-NN-NNN`.** This is the second pass —
   pytest verifiers that depend on landed UC tables will only PASS now
   that the DAG has finished. Same exit-code contract as Step 1.5.

This entire step is project-agnostic: DAG id, ports, table counts all
come from what the story declares, never from hardcoded project names.

**Step 2 — Optional: run `/developer-plugin:validate-stories` for evidence.**

If the user asks for it, dispatch `validate-stories <target>` and include
its report in the output. The gate does NOT require a fresh
`validate-stories` run — Steps 1, 1.5, 1.6, 1.7 are the hard rules. A
downstream validator failure is a strong signal but it is not part of the
gate payload to keep the gate deterministic and side-effect-free.

**Step 3 — Atomic abort.**

If ANY target's gate returns blocked, stop immediately. Print every
blocker, then:

```
BLOCKED: Cannot complete {target(s)}.
  - {N} blocker(s) across {M} target(s) — see list above.

Nothing was edited. Resolve the blockers (check off verified ACs, finish
dependent stories, fill in missing deliverables) and re-run
/developer-plugin:complete-stories.
```

**Exit without editing a single character.** The gate is all-or-nothing —
never partial. This is the user's hard rule.

### Phase 2: Apply Edits (reached only if every gate passed)

Order matters — apply edits **leaf-first** so a mid-run I/O error leaves a
sane partial state that a re-run can recover from.

**Step 1 — For each story target (sorted by story ID):**

Use `Edit` (never `Write`) to flip the single Status row in the story file.
Read the file first so the edit is precise. Resolve the file path with
`status_rollup.py --mode find --story STORY-NN-NNN` — don't hardcode paths.

```
Before: | **Status** | To Do |
After:  | **Status** | Done |
```

or

```
Before: | **Status** | In Progress |
After:  | **Status** | Done |
```

The metadata table always has exactly one `| **Status** | ... |` row — a
single-instance `Edit` is correct.

**Step 2 — Tick AC checkboxes that this run verified.**

For each AC line in the story file that the gate confirmed (i.e. it was
already `- [x]` OR Phase 1 validated the deliverable/heuristic), flip
`- [ ]` → `- [x]`.

**Never tick an AC that the verifier cannot prove.** If an AC was unchecked
AND the gate did not independently verify it, Phase 1 already aborted —
so this situation does not arise. The rule exists to keep future changes
safe.

Use a single `Edit` call per AC line (the `- [ ]` + AC text is a unique
substring in the file).

**Step 2.5 — Update the story plan (if it exists).**

After ticking AC checkboxes and flipping the story's Status to Done, also
update the plan file to match:

```bash
python3 -c "
import json
from datetime import datetime, timezone
p = json.load(open('$PLAN_PATH'))
p['status'] = 'done'
p['completion']['status'] = 'done'
p['completion']['completed_at'] = datetime.now(timezone.utc).isoformat()
p['completion']['blocking_reasons'] = []
json.dump(p, open('$PLAN_PATH','w'), indent=2)
"
```

Skip if no plan exists (legacy story).

**Step 3 — Roll up the epic (only if every child is now Done).**

Re-run the helper in rollup mode for the story's epic:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode rollup --epic EPIC-NN
```

- If `all_done == true` AND every epic-level AC is verified → edit
  `EPIC-NN.md`:
  - Tick every epic-level AC the helper confirmed as met (same "never tick
    what you cannot prove" rule).
  - Flip the Epic `**Status**` cell from `To Do` / `Updated - Pending Review`
    → `Done`.
- Otherwise, leave the epic file untouched.

**Step 4 — Update the backlog index.**

Read the latest backlog file (helper resolves it):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode parse-backlog
```

- Edit the `**Last Modified**` cell to today's date: `$(date +%F)`.
- If every epic in the backlog is now `Done` → `**Status** | Done`.
- Otherwise → `**Status** | Updated - Pending Review`.

Do NOT add or remove rows from the backlog's `## Epic Overview` or `## Sprint
Plan` tables. Those are owned by the Scrum Master plugin, not this one.

### Phase 3: Post-flight

Re-run the helper's gate once more on the same targets. It should now
return `blocked: false`. If it does not, print a warning — but leave the
edits in place. A post-edit gate failure indicates a bug in the gate logic
(the edits should have flipped exactly the state the gate checks), and the
user needs to see it.

### Phase 4: Learnings

If the user overrode any decision (e.g. "don't mark AC 9 ticked — the
bootstrap behavior is still speculative"), append a JSONL line to the
`{learnings_queue}` returned by the discovery helper:

```bash
QUEUE=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode discover | python3 -c "import sys,json; print(json.load(sys.stdin)['learnings_queue'])")
echo '{"skill": "complete-stories", "date": "'$(date +%F)'", "correction": "<quote>", "pattern": "<rule>", "status": "pending"}' >> "$QUEUE"
```

## Output Format

### On block

```
BLOCKED: Cannot complete EPIC-02.

Blockers (12):
  child:ac_unchecked    STORY-02-001 AC 1 unchecked: 13 YAML files exist...
  child:ac_unchecked    STORY-02-001 AC 2 unchecked: source.table synthea.{table}...
  dependency_not_done   STORY-02-002 depends on STORY-01-008 (Status: To Do)
  ...

Nothing was edited. Resolve blockers and re-run /developer-plugin:complete-stories.
```

### On success

```
COMPLETED: EPIC-02 (3 stories, 1 epic, 1 backlog entry edited)

Story edits:
  STORY-02-001  | Status: To Do → Done        | 9 ACs ticked
  STORY-02-002  | Status: In Progress → Done  | 9 ACs ticked
  STORY-02-003  | Status: To Do → Done        | 4 ACs ticked

Epic edits:
  EPIC-02       | Status: To Do → Done        | 11/11 epic-level ACs ticked

Backlog:
  BACKLOG-2026-04-22-patient-360.md
    Last Modified: 2026-04-22 → 2026-04-23
    Status:        Updated - Pending Review → Updated - Pending Review
      (4 epics still open: EPIC-03, EPIC-04, ...)

Post-flight gate: PASS
```

## Edge Cases

- **User target includes one Done story and two open stories** — edit nothing (atomic rule). Show blockers for the open ones; tell the user the Done story would have been a no-op anyway.
- **Story already Done** — no-op (no Status edit, no AC edits). Count it in the output summary as "0 edits".
- **Epic has only one child story and it's being completed here** — the epic rolls up in this same run (Phase 2 Step 3). Report both edits.
- **Backlog file absent or only `.bak` copies present** — helper raises an error; propagate as a blocker.
- **Multiple AC lines share the exact same text** (rare) — use Read to locate line numbers, then include more surrounding context in the `Edit` to make it unique.
- **Epic-level AC text is identical across two epics** — scope the Edit to the specific epic file path; do not use `replace_all`.

## Hard Rules (do not relax)

1. If the gate blocks anywhere in the target set, NOTHING is edited.
2. Only tick ACs the gate has verified — never back-date.
3. Epic Status flips to Done only when every child story is Done AND every epic-level AC is `- [x]`.
4. Backlog Status never flips to Done unless every tracked epic is Done.
5. Never use `Write` on these markdown files; always `Edit` with enough context to uniquely identify the line.

## Learnings & Corrections

_No learnings recorded yet._
