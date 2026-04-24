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

**Step 1 — Parse the argument into an ordered story list.**

Argument grammar (shared with validate-stories and complete-stories):

| Form                     | Example                            | Meaning                                             |
|--------------------------|------------------------------------|-----------------------------------------------------|
| `STORY-NN-NNN`           | `STORY-02-002`                     | single story                                        |
| comma-list               | `STORY-02-001,STORY-02-002`        | ordered list — respect declared `Depends On`        |
| `EPIC-NN`                | `EPIC-02`                          | every child story, topo-sorted                      |
| `Sprint N`               | `Sprint 3`                         | every story whose `Sprint` cell is `Sprint N`       |
| (no arg)                 | —                                  | ask via `AskUserQuestion`                           |

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

### Phase 2: Dispatch

**Step 1 — Pick create-* vs update-* per story.**

For each story in the resolved list:

1. Run `--mode classify --story STORY-NN-NNN` to resolve `skill_kind`.
2. Map `skill_kind` to the `create-{kind}` / `update-{kind}` / `validate-{kind}` triplet using the table above.
3. Decide mode:
   - **Story Status `To Do`** AND the deliverables listed in its ACs do NOT yet exist on disk → dispatch the **create** skill.
   - **Story Status `In Progress`**, OR any AC-referenced deliverable already exists → dispatch the **update** skill.
   - Both viable (e.g. 50% of deliverables present) → ask via `AskUserQuestion`, listing the present vs absent deliverables so the user can decide overwrite vs incremental.

Deliverable paths are the backtick-quoted tokens in the story's AC text;
check them against `{project_root}` first, then `{workspace_root}`.

**Step 2 — Forward the story ID when the generator supports story mode.**

Some generators accept a `STORY-NN-NNN` argument and scope their work to that
one story; others generate everything the LLD describes. You can't tell from
the config. Try the story-ID form first; if the generator errors because it
requires a different argument, fall back to invoking it with no argument and
tell the user: "This generator runs full mode — only the deliverables covered
by STORY-NN-NNN will be reviewed from this run."

```
Skill("<resolved-create-skill>", "STORY-NN-NNN")
```

**Step 3 — Unclassifiable stories.**

If `skill_kind == "unknown"` OR `confidence == "low"` for any story, stop
the batch before any dispatch:

```
Cannot classify STORY-NN-NNN from its acceptance criteria.
  Reasons (0): (no rule matched any AC)

Resolve by one of:
  1. Tightening the AC text to reference a concrete path under the
     cookiecutter layout (e.g. `airflow/configs/foo.yml`,
     `src/{project_name}/bronze/...`, `_infra/ci/...`).
  2. Overriding the classification: tell me "treat STORY-NN-NNN as
     {scaffold|dag|ingestion|pipeline}" and re-run — I'll record that as
     a learning.
```

If the user overrides, record the correction in the learnings queue
(Phase 5) so a future `apply-learnings` run can propose a classifier rule.

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

Print the final table. End with the exact next-step line:

```
Next: /developer-plugin:validate-stories <same-argument>
```

Do NOT run validate-stories yourself — the user chooses when to validate
(they may want to inspect the generated diff first).

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
