---
name: implement-stories
description: >
  Drives the implementation of one or more Scrum stories by dispatching to the
  correct downstream create-/update- skill per epic. Accepts a story ID, a
  comma-separated list, an epic ID (topo-sorted by Depends On), or a Sprint
  label (e.g. "Sprint 3"). Never edits story markdown itself — it only
  orchestrates the generators and surfaces their results.
  Use when the user asks to:
  - Implement STORY-NN-NNN or a list of stories
  - "Implement EPIC-02" / "Implement all of Sprint 3"
  - Build the next story in the backlog
  - Drive story-mode generation across several stories in one turn
argument-hint: "[STORY-NN-NNN | EPIC-NN | 'Sprint N' | comma-list]"
allowed-tools: Read, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Implement Scrum Stories

You are the orchestrator for the existing `create-*` / `update-*` skills.
Your job is to walk one or more stories through their generator in the correct
order, stop on the first CRITICAL failure, and hand off to
`/developer-plugin:validate-stories` when the batch finishes.

You do NOT edit story markdown files. You do NOT flip Status fields. You do
NOT tick acceptance-criteria checkboxes. Those mutations belong to
`/developer-plugin:complete-stories` after validation passes.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Coding Patterns & Libraries Handbook (orchestrator-level)

Before dispatching to any sub-skill, the orchestrator runs the freshness
check ONCE so every downstream generator inherits an up-to-date library
cache without re-prompting:

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, call **AskUserQuestion** *once* with options `Refresh now` / `Proceed with cached versions` / `Cancel`:

- `Refresh now` — invoke `/developer-plugin:refresh-libraries`, wait for completion, then continue dispatching.
- `Proceed with cached versions` — dispatch sub-skills with the cached versions; prepend a single stale-cache warning to the batch's final References trailer.
- `Cancel` — abort the batch; no stories run.

**Do not** let each sub-skill re-prompt — the orchestrator answers once for the whole batch. Downstream create-*/update-* skills skip their own freshness check when invoked from this skill (detect via an env var such as `DEVPLUGIN_FRESHNESS_OK=1`).

Read `$PATTERNS_DIR/LIBRARIES.md` in full so versions are available to any sub-skill that asks.

## Dispatch (content-based classification — no config)

There is NO dispatch yaml. Story and epic numbers are not stable across
projects — `EPIC-02` may be ingestion in one project and something else in
another. Each story is classified by its acceptance-criteria content:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode classify --story STORY-NN-NNN
```

The JSON output includes `skill_kind` — one of `scaffold`, `dag`,
`ingestion`, `pipeline`, or `unknown` — plus `confidence` (`high` / `low`)
and a `reasons[]` list citing the AC matches that produced the verdict.

Map `skill_kind` to the generator by literal convention (no lookup):

| `skill_kind` | create skill        | update skill        | validate skill        |
|--------------|---------------------|---------------------|-----------------------|
| `scaffold`   | `create-scaffold`   | `update-scaffold`   | `validate-scaffold`   |
| `dag`        | `create-dag`        | `update-dag`        | `validate-dag`        |
| `ingestion`  | `create-ingestion`  | `update-ingestion`  | `validate-ingestion`  |
| `pipeline`   | `create-pipeline`   | `update-pipeline`   | `validate-pipeline`   |
| `unknown`    | — (see Phase 2 Step 3) | —                | —                     |

If `skill_kind == "unknown"` OR `confidence == "low"`, stop the batch and
ask the user via `AskUserQuestion`, showing the `reasons[]` so they can
override. Record any override as a learning (Phase 5).

A downstream generator MAY accept a `STORY-NN-NNN` argument directly (story
mode) — forward the story ID verbatim when it does. Otherwise forward the LLD
path (full mode) and tell the user only the covered story's deliverables will
be reviewed from that run. Classification does not distinguish the two modes;
detection is the invoked skill's responsibility.

## Workflow

### Phase 0: Resolve Target Set

**FIRST — resolve the effective argument. Do this before any other Phase 0 step.**

The argument passed via the `Skill` tool may not reach this forked subagent.
Check these sources in order; stop at the first non-empty hit:

1. `$SKILL_ARG` environment variable.
2. `{workspace_root}/.skill-arg` file — read its contents, then delete
   the file so it is consumed at most once.
3. The conversational argument supplied to the skill.
4. **Auto-mode default** — if `$CLAUDE_AUTO_MODE=1` OR
   `{workspace_root}/.auto-mode` exists → **resolve the latest backlog and
   implement the first un-Done epic** (as returned by
   `status_rollup.py` in backlog order). Epic numbers are not assumed to
   be meaningful across projects; the ordering is the one the backlog
   itself declares. This is the skill's full-mode default and never
   requires user input.
5. Only if ALL four above are empty, ask the user via `AskUserQuestion`.

You MUST NOT ask the user until sources 1–4 have been checked. Auto-mode
detection is a hard override — if the marker exists, proceed with the
default target and do not ask.

Mechanical resolver (copy-paste; `$USER_ARG` is the conversational arg):

```bash
resolve_skill_arg() {
  if [ -n "$SKILL_ARG" ]; then echo "$SKILL_ARG"; return; fi
  if [ -f "{workspace_root}/.skill-arg" ]; then
    cat "{workspace_root}/.skill-arg"; rm -f "{workspace_root}/.skill-arg"; return
  fi
  # caller supplies conversational arg as $1
  if [ -n "$1" ]; then echo "$1"; return; fi
  if [ "$CLAUDE_AUTO_MODE" = "1" ] || [ -f "{workspace_root}/.auto-mode" ]; then
    echo "__AUTO__"; return
  fi
  echo ""
}
RESOLVED_ARG=$(resolve_skill_arg "$USER_ARG")
```

If `$RESOLVED_ARG` is `__AUTO__`, expand it into the first un-Done epic
in the backlog and proceed without asking.

**Loud-banner rule (anti-flake guard).** Whenever the resolver lands in
the `__AUTO__` branch (sources 1–3 all empty), emit this banner as the
*first line* of skill output before any other work — so the user
immediately notices if their explicit arg was lost in transit:

```
⚠ AUTO-MODE FALLBACK: no explicit target found in $SKILL_ARG, .skill-arg,
  or conversational arg. Resolved to <EPIC-NN> (first un-Done epic).
  If you intended a different target, abort with Ctrl-C and re-invoke
  AFTER writing the target to {workspace_root}/.skill-arg, e.g.:
      echo "EPIC-02" > {workspace_root}/.skill-arg
```

**Caller contract.** The Skill-tool argument frequently fails to reach
forked subagents. Any caller (slash command, parent agent, hook) that
invokes `/developer-plugin:implement-stories <arg>` programmatically
MUST also `echo "<arg>" > {workspace_root}/.skill-arg` immediately
before the Skill invocation. The skill consumes the file (deletes after
read), so it is a one-shot. Without this, auto-mode silently picks the
first un-Done epic — the banner above is the safety net, not a contract.

#### Version lockfile (pinned upstream v{N})

Before any dispatch, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --write
```

This creates `{workspace_root}/outputs/dev-lock.yaml` pinning the exact v{N}
folder for each upstream (`lld`, `stm`, `dqs`, `stories`) for the duration
of this batch. Every downstream create-*/update-* skill sources the same
file — they never re-resolve `ls -d outputs/*/v* | tail -1` on their own
once the lockfile is present. Delete the lockfile to re-pin on the next
batch.

#### Bootstrap gate (chicken-and-egg)

Check the discovery result:

```bash
DISCOVERY=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover)
NEEDS_BOOTSTRAP=$(echo "$DISCOVERY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('needs_bootstrap', False))")
```

If `needs_bootstrap == True`, classify every story in the target set (via
`status_rollup.py --mode classify`). If at least one classifies to
`scaffold`, dispatch `/developer-plugin:create-scaffold` FIRST (passing
the original target via `$SKILL_ARG`), wait for completion, then re-run
discovery before continuing. `create-scaffold` handles the cookiecutter
bootstrap as its first step.

If `needs_bootstrap == True` but NO story in the target set classifies to
`scaffold`, stop with CRITICAL: `project not bootstrapped — run /developer-plugin:create-scaffold first, or include a foundation story in the target set`.
This keeps the bootstrap gate tied to **kind** (`scaffold`), not to a
specific epic number — any project's foundation epic, numbered however
the reader's scrum-master emitted it, triggers the gate.

**Step 1 — Parse the argument into an ordered story list.**

Argument grammar (shared with validate-stories and complete-stories):

| Form                     | Example                            | Meaning                                             |
|--------------------------|------------------------------------|-----------------------------------------------------|
| `STORY-NN-NNN`           | `STORY-02-002`                     | single story                                        |
| comma-list               | `STORY-02-001,STORY-02-002`        | ordered list — respect declared `Depends On`        |
| `EPIC-NN`                | `EPIC-02`                          | every child story, topo-sorted                      |
| `Sprint N`               | `Sprint 3`                         | every story whose `Sprint` cell is `Sprint N`       |
| `__AUTO__` / (no arg)    | —                                  | auto-mode: next un-Done epic from `EPIC-01`; else ask via `AskUserQuestion` |

Normalize the argument exactly as `create-ingestion` Phase 0 does:
uppercase, zero-padded (`"story 2 of epic 2"` → `STORY-02-002`). Reject
ranges (`STORY-02-001..003`) explicitly — they are not supported.

**Step 2 — For `EPIC-NN` / `Sprint N`, expand to stories and topo-sort.**

Use the helper:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode parse-epic --epic EPIC-02
```

Read the `child_stories` array. Build a DAG from each story's `depends_on`
field and emit the stories in topological order. If a cycle is detected,
stop with a CRITICAL: `cycle detected: A → B → A`.

For `Sprint N`, parse every story file under the latest
`{stories_dir}/v*/` (from discovery) and filter by `sprint == "Sprint N"`,
then topo-sort the same way.

**Step 3 — Show the resolved list and confirm.**

Use `AskUserQuestion`:

```
About to implement 3 stories in this order:
  1. STORY-02-001 — Per-Table YAML Ingestion Configs   (create-ingestion)
  2. STORY-02-002 — Generic Ingestion Runner           (create-ingestion)
  3. STORY-02-003 — SparkSubmitOperator Wrapper        (update-ingestion — file exists)

Proceed? (Yes / No / Edit order)
```

If the user picks Edit, ask which stories to keep or reorder, then re-confirm.

### Phase 1: Pre-flight

For each target story, call:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode parse-story --story STORY-NN-NNN
```

From the JSON:

- If `status == "Done"` → **skip** (single-line log: `STORY-NN-NNN already Done — skipped`). Never re-dispatch.
- If `epic_id`'s epic file has `status == "Done"` but this story is not Done → stale backlog. Stop and tell the user to resolve the drift before continuing.
- If the story file is not found → stop with the error from the helper.

### Phase 1.5: Build and Persist the Story Plan

Every story gets a **persistent execution plan** — the single ledger that
`implement-stories`, `validate-stories`, and `complete-stories` all read
and enrich. One plan per story, located at
`{stories_dir}/v{N}/plans/STORY-NN-NNN.plan.json`.

Before dispatching any sub-skill, build (or refresh) the plan:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode build-plan --story STORY-NN-NNN --save
```

The plan captures:
- `tasks[]` — one per (skill, paths) group from `extract-deliverables`,
  in `dispatch_order`, with a `depends_on` chain so later tasks wait for
  earlier ones.
- `acceptance_criteria[]` — every AC line linked to the task(s) whose
  deliverable paths cover its backtick-quoted tokens. Behavioural ACs
  (no tokens) link to every task so any validator can attempt coverage.
- `status: planned` initially; walks `planned → in_progress → implemented
  → validated → done` over the three phases; or `failed` at any step.

If the scrum-master re-runs and an AC or deliverable changes, re-running
`build-plan --save` overwrites the plan and increments `plan_version`.
Prior task outcomes are NOT preserved across re-builds — callers that
care should compare `plan_version`.

### Phase 2: Dispatch (multi-skill, path-based, plan-driven)

This phase is path-based, not kind-based. A single story whose ACs name
deliverables under two skills' domains (e.g. an ingestion module AND the
DAG task that wires it in) dispatches to BOTH skills in sequence, each
scoped to the paths it owns. No skill ever sees paths outside its domain.

The routing registry is
`{workspace_root}/inputs/code/v*/DELIVERABLE-OWNERS.yaml` — a reader's
extension point for re-routing path classes (e.g. swapping Airflow for
Dagster).

**Step 1 — Extract deliverables for each story.**

For each story in the resolved list:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode extract-deliverables --story STORY-NN-NNN
```

The JSON output contains:
- `paths` — every backtick-quoted path from the AC (placeholders stripped).
- `by_skill` — paths grouped by owning skill from the registry.
- `dispatch_order` — the order to invoke those skills (from the
  registry's `dispatch_order`: typically scaffold → ingestion → dag →
  pipeline).
- `unmatched` — paths no glob matched (added to `fallback_kind`'s group
  via the classifier).
- `fallback_kind` — the classifier's kind, used when `paths` is empty
  (purely behavioural ACs) or for unmatched paths.

**Step 2 — Fall-back for behavioural stories.**

If `by_skill` is empty, the story's ACs have no path tokens (behavioural
story). Dispatch the single skill named by `fallback_kind` (from the
classifier) with `STORY-NN-NNN` and no `.skill-paths` file — the sub-
skill will read the story's AC and handle it in its historical
single-skill mode.

If `fallback_kind` is also missing / `unknown`, stop the batch:

```
Cannot route STORY-NN-NNN. No deliverable paths in its AC and the
classifier returned `unknown`. Tighten the AC text to reference concrete
paths (e.g. `airflow/configs/foo.yml`, `src/<project>/bronze/...`) or
override with "treat STORY-NN-NNN as {scaffold|dag|ingestion|pipeline}".
```

Record any user override in the learnings queue (Phase 5).

**Step 3 — Per-group dispatch (plan-driven).**

Read the plan's `tasks[]` (built in Phase 1.5). For each task in order:

Before dispatching a task, update the plan:
- set `tasks[i].status = "in_progress"` and stamp `started_at`
- if this is the first task, bump plan `status = "in_progress"`

Persist the plan after every status change so a mid-batch interruption
leaves a truthful ledger. Use a simple Python one-liner:

```bash
python3 -c "
import json, sys
from datetime import datetime, timezone
p = json.load(open('$PLAN_PATH'))
for t in p['tasks']:
    if t['id'] == '$TID':
        t['status'] = '$NEW_STATUS'
        if '$NEW_STATUS' == 'in_progress' and not t['started_at']:
            t['started_at'] = datetime.now(timezone.utc).isoformat()
        if '$NEW_STATUS' in ('done','failed'):
            t['finished_at'] = datetime.now(timezone.utc).isoformat()
json.dump(p, open('$PLAN_PATH','w'), indent=2)
"
```

Then dispatch:

1. **Write the scoping files**:

   ```bash
   echo "STORY-NN-NNN"            > {workspace_root}/.skill-arg
   printf '%s\n' "${paths[@]}"    > {workspace_root}/.skill-paths
   ```

   The sub-skill reads both and treats `.skill-paths` as the ONLY paths
   in scope for this invocation. Both files are consumed (deleted) by the
   sub-skill after reading.

2. **Pick create-* vs update-*** using the same rule as before, but
   scoped to THIS group's paths:
   - `status == "To Do"` AND **none** of this group's paths exist on
     disk → `create-<skill>`.
   - `status == "In Progress"`, OR **any** of this group's paths
     already exist → `update-<skill>`.
   - Split (some present, some absent) → `AskUserQuestion` with the
     present/absent lists.

3. **Invoke** via the `Skill` tool and capture output.

4. **CRITICAL handling (intra-story)**: if this dispatch reports
   CRITICAL, **stop this story** (do not dispatch the subsequent groups
   for the same story — they likely depend on this one). Continue with
   the next story in the batch unless `--stop-on-critical-batch` is
   passed.

5. Append one row to the implementation log per dispatch:

   ```
   STORY-02-004 | create-ingestion | 2 files created     | OK
   STORY-02-004 | update-dag       | 1 file patched      | OK
   STORY-02-006 | create-ingestion | 1 file created      | OK
   ```

After the sub-skill returns, parse its output to populate
`tasks[i].files_created`, `files_updated`, `artifacts`, and any
`critical_findings`. Then set `tasks[i].status = "done"` (or `"failed"`
if CRITICAL) and save.

When every task has `status == "done"`, set plan `status = "implemented"`.
If any task `status == "failed"`, set plan `status = "failed"`.

**Step 3.5 — Post-dispatch AC verification (tight loop).**

After each sub-skill returns and the plan is saved, run the AC verifier
for this story before dispatching the next task in the same story:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/../scripts/verify_acs.py STORY-NN-NNN --json
```

Parse the JSON output (shape: a list of one story object with
`has_verification`, `overall`, and `acs[]`):

- **`has_verification: false`** — add one trailer line for the run
  summary: `STORY-NN-NNN: no Verification block — inline validation skipped.`
  Then continue as normal.
- **For each AC object with `status == "FAIL"`** (any non-`manual` check
  that failed):
    1. Determine which task to attribute the failure to:
       - If the AC has non-empty `task_ids` in `acceptance_criteria[]`
         and they include the just-completed task → that task fails.
       - If `task_ids` is empty OR doesn't reference any task in this
         story → attribute to the most recently completed task in this
         story (`tasks[-1]` whose `status == "done"`). Empty `task_ids`
         is a heuristic-population artifact, NOT a permission to ignore
         the FAIL.
    2. Append the first `check.detail` of the first failing check to
       `tasks[i].critical_findings`.
    3. Set `tasks[i].validator_status = "fail"` AND
       `tasks[i].status = "failed"` (overrides the prior `done`).
    4. Treat as CRITICAL for halt semantics: set plan
       `status = "failed"`, **stop this story**, continue the batch.
       Log the row: `STORY-NN-NNN | <skill> | AC<N> inline-FAIL | STOPPED`.
- **For `status == "PASS"`** → set `tasks[i].validator_status = "pass"`.
- **`status == "INDETERMINATE"`** never halts and never sets
  `validator_status` — leave the field as `"pending"`.

Persist the plan JSON after updates. This tight loop surfaces gaps at
the moment they appear rather than deferring them to an end-of-batch
`validate-stories` run.

**Step 4 — Verify no ROUTE-TO escapes.**

A sub-skill invoked WITH a `.skill-paths` file should never emit
`ROUTE-TO:` (every path it received was already vetted as owned). If the
output contains `ROUTE-TO:`, record a learning — the registry has a gap
for that path pattern, and a future `apply-learnings` run should propose
adding the glob.

### Phase 3: Execute

For each story in order:

1. Invoke the chosen skill via the `Skill` tool. Capture its final
   `Output Summary` text.
2. If the skill reports any CRITICAL failure (visible in its output), **stop
   the batch**. Do not continue to subsequent stories — later stories in a
   topo-sorted list typically depend on the one that just failed.
3. Append one row to your running implementation log:

   ```
   STORY-02-002 | create-ingestion | 1 file created | OK
   STORY-02-003 | update-ingestion | 0 CRITICAL, 1 WARNING | OK
   STORY-02-004 | create-ingestion | 2 CRITICAL        | STOPPED
   ```

### Phase 4: Hand-off

Print the final table. Immediately above the next-step line, emit one
**inline-validation summary** line tallying the Step 3.5 verdicts across
all stories in the batch:

```
Inline validation: <N> PASS, <M> FAIL (<first-failing-story AC#>, ...), <K> SKIPPED (no verification block)
```

Then end with the exact next-step line:

```
Next: /developer-plugin:validate-stories <same-argument>
```

Do NOT run validate-stories yourself — the user chooses when to validate
(they may want to inspect the generated diff first). The inline summary
above is a heads-up, not a replacement.

### Phase 5: Learnings

If the user corrected your classification (e.g. "no, STORY-02-010 is an
ingestion test, not scaffold") or your topo-sort ordering, append a JSONL
line to the `{learnings_queue}` returned by the discovery helper:

```bash
QUEUE=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py \
  --mode discover | python3 -c "import sys,json; print(json.load(sys.stdin)['learnings_queue'])")
echo '{"skill": "implement-stories", "date": "'$(date +%F)'", "correction": "<quoted user correction>", "pattern": "<generalized rule>", "status": "pending"}' >> "$QUEUE"
```

The existing PostToolUse `check-learnings-queue.py` hook will remind you to
run `/developer-plugin:apply-learnings` at session end.

## Output Summary

End every run with this table (one row per target story):

```
Target: EPIC-02  |  Resolved: 3 stories  |  Dispatched: 3  |  Stopped: 0

Order | Story         | Skill              | Result
    1 | STORY-02-001  | create-ingestion   | 13 configs created, validate-ingestion PASS
    2 | STORY-02-002  | create-ingestion   | 1 module created,  validate-ingestion PASS
    3 | STORY-02-003  | update-ingestion   | 1 module edited,   validate-ingestion PASS

Next: /developer-plugin:validate-stories EPIC-02
```

## Edge Cases (must handle)

- **Lowercase arg** (`story-02-002`) → normalize to uppercase silently.
- **Circular `Depends On`** → detect during topo-sort, stop with CRITICAL.
- **Story already Done** → single-line skip log; never re-dispatch.
- **Multiple backlog files** → helper picks the lexicographically latest non-`.bak`.
- **`AskUserQuestion` unavailable** → default to the conservative choice
  (`update-*` when deliverable exists, else `create-*`) and log the decision.
- **Generator fails mid-batch** → stop, print log so far, tell the user which
  story to fix before re-invoking.

## Learnings & Corrections

_No learnings recorded yet._
