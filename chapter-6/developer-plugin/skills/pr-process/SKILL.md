---
name: pr-process
description: >
  Drives the full pull-request lifecycle for a story branch produced by the
  developer-plugin: runs a readiness gate, opens the PR with a story-derived
  body and labels, polls reviews and check rollups, and on approval invokes a
  pluggable sandbox-teardown driver so the developer environment used to build
  the story is destroyed.

  Teaching frame for chapter-6 readers: in real projects, once data-engineering
  work is done the team opens a PR, reviewers approve, and the dev sandbox
  (local docker-compose OR a sandboxed cloud env) is destroyed so cost and
  orphaned state don't accumulate. This skill demonstrates that lifecycle with
  the local-docker driver, and the driver contract is documented so a
  cloud-databricks or cloud-eks driver can be swapped in later without
  rewriting the skill.

  Modes:
  - Story mode (default): pass STORY-NN-NNN. The skill discovers the branch,
    runs readiness, opens the PR, drives review, tears down on approval.
  - Attach mode: pass a numeric pull-request number. The skill skips readiness
    + open and joins the lifecycle at the review phase.

  Project-agnostic: branch names, project root, docker-compose file, named
  volumes, and the driver list are all read from workspace discovery + the
  active teardown-pattern.md at runtime. No project / chapter / table names
  are hardcoded in this skill.

  Use when the user asks to:
  - Open a PR for a story, drive the review, and tear down the sandbox
  - Run a PR readiness check before pushing
  - Destroy the local docker-compose sandbox after a PR is approved
argument-hint: "[STORY-NN-NNN | <pull_number>]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Pull Request Process

You are a senior Data / Platform Engineer responsible for the **post-DE-work
lifecycle**: turn a finished story branch into a reviewed, approved PR, then
destroy the development sandbox so the team doesn't bleed cost or carry
orphaned state into the next story.

The skill has **four phases**. Phase 1 is a gate (no PR opens without a clean
readiness report). Phase 4 is the user's hard requirement (teardown MUST run
on approval). Phases 2 and 3 are the lifecycle in between.

The teardown step is **pluggable**. Chapter-6 ships a `local-docker` driver
that tears down the patient_360 docker-compose stack. The driver contract is
documented in `inputs/code/v1/teardown-pattern.md` so readers can add a
`cloud-databricks` / `cloud-eks` driver later without touching this skill.

## Workspace Discovery

Before any file operation, run the shared discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project, chapter, table, DAG, catalog, or
schema names.

## Coding Patterns & Libraries Handbook

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required pattern docs for this skill:**

- `$PATTERNS_DIR/teardown-pattern.md` — driver contract (`--dry-run`,
  `--check`, `--destroy`, JSON summary), driver-selection rules, worked
  examples for local-docker and cloud-databricks.
- `$PATTERNS_DIR/ci-cd-pattern.md` — references the `sandbox-cleanup.yml`
  workflow that pairs with this skill on the CI side.
- `$PATTERNS_DIR/docker-compose-conventions.md` — named-volume conventions
  the local-docker driver removes.
- `$PATTERNS_DIR/LIBRARIES.md` — pinned `gh` version + docker compose version.

### Library freshness check

```bash
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, pause and call **AskUserQuestion** with options
`Refresh now` / `Proceed with cached versions` / `Cancel`. On Refresh,
invoke `/developer-plugin:refresh-libraries` then resume.

### References trailer (in output)

Emit a `### References` section citing consumed pattern docs + LIBRARIES.md
vintage. Add a stale-cache warning if the user proceeded with cached versions.

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

If `$RESOLVED_SOURCE == EMPTY`, fall through to `AskUserQuestion` asking the
user for a `STORY-NN-NNN` ID or a PR number. DO NOT proceed without one.

### Mode dispatch

After resolution, classify `$RESOLVED_ARG`:

- Matches `^STORY-[0-9]+-[0-9]+$` → **Story mode** (run all 4 phases).
- Matches `^[0-9]+$` (1–6 digits) → **Attach mode** (skip Phase 1 + 2,
  start at Phase 3 against that PR number).
- Anything else → CRITICAL, stop.

## Workflow

### Phase 1 — Readiness Gate (Story mode only)

Before opening a PR, this skill MUST confirm the branch is shippable. Any
failure here stops the skill — the PR does not open.

Resolve the branch + project root, then run the readiness aggregator:

```bash
BRANCH="$(git -C {project_root} rev-parse --abbrev-ref HEAD)"
STORY_ID="$RESOLVED_ARG"

python3 ${CLAUDE_PLUGIN_ROOT}/skills/pr-process/scripts/check_pr_readiness.py \
  --story "$STORY_ID" \
  --workspace-root "{workspace_root}" \
  --project-root "{project_root}" \
  --branch "$BRANCH" \
  --json
```

`check_pr_readiness.py` runs the following gates and returns a single JSON
report with an aggregate `result` of `PASS | WARN | FAIL`:

| # | Gate | Exit signal |
|---|---|---|
| 1 | `git status --porcelain` is empty (no uncommitted changes) | FAIL on dirty tree |
| 2 | Current branch is **not** `main` and is ahead of `origin/main` by ≥ 1 commit | FAIL otherwise |
| 3 | Story file exists at `{stories_dir}/EPIC-NN-*/STORY-NN-NNN-*.md` with `Status: Done` or `Approved` | FAIL if missing / not Approved |
| 4 | `make lint` exits 0 (ruff clean) | FAIL on non-zero |
| 5 | `make test` exits 0 (pytest green) | FAIL on non-zero |
| 6 | `verify_acs.py $STORY_ID --json` reports no FAIL ACs | FAIL on any AC failure |
| 7 | `/developer-plugin:validate-stories $STORY_ID` reports PASS | FAIL on its CRITICAL |

If `result == FAIL`: print every failing gate as one CRITICAL line and
**stop**. Do not open a PR. Append a learnings entry only if the failure
was an unexpected runtime error (not an expected red gate).

If `result == WARN`: surface the warnings, ask the user via
`AskUserQuestion` whether to proceed (`Open as draft` / `Open ready for
review` / `Abort`). Default to `Open as draft` for safety.

If `result == PASS`: continue to Phase 2.

### Phase 2 — Open the PR (Story mode only)

Render the PR body from the template and invoke `gh`:

```bash
TEMPLATE="${CLAUDE_PLUGIN_ROOT}/skills/pr-process/pr_body.md.j2"
RENDERED_BODY="$(python3 - <<PY
import json, pathlib, subprocess, sys
from jinja2 import Template

story = "$STORY_ID"
ctx = json.loads(pathlib.Path("/tmp/pr-readiness-${STORY_ID}.json").read_text())
tpl = Template(pathlib.Path("$TEMPLATE").read_text())
print(tpl.render(story=story, ctx=ctx))
PY
)"
```

The template (`pr_body.md.j2`) renders the PR body with:

- `## Story` — link to the story file (relative path from repo root).
- `## Acceptance Criteria` — copy the `## Verification` block from the
  story verbatim, with each AC as a markdown checkbox (`- [x]` for PASS,
  `- [ ]` for INDETERMINATE / manual, `- [!]` for WARN).
- `## Files Changed` — categorise by layer (bronze / silver / gold / dag /
  pipeline / contracts / dq_rules / tests / infra) using the file-path
  prefixes from `git diff --name-only origin/main...HEAD`.
- `## Validator Summary` — table of validator name → result → notes,
  populated from the readiness report.
- `## Sandbox Teardown on Approval` — footer announcing which driver will
  run on approval and the resources it plans to destroy (driver `--check`
  output).

Open the PR:

```bash
TITLE="$STORY_ID: $(awk '/^# /{print substr($0,3); exit}' "{stories_dir}"/EPIC-*/$STORY_ID-*.md)"
LABELS="$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/pr-process/scripts/check_pr_readiness.py \
  --story "$STORY_ID" --workspace-root "{workspace_root}" --project-root "{project_root}" \
  --branch "$BRANCH" --emit labels)"
DRAFT_FLAG=""
[ "$READINESS_RESULT" = "WARN" ] && DRAFT_FLAG="--draft"

PR_URL="$(gh pr create \
  --base main \
  --head "$BRANCH" \
  --title "$TITLE" \
  --body "$RENDERED_BODY" \
  --label "$LABELS" \
  $DRAFT_FLAG)"

echo "$PR_URL" > "{workspace_root}/outputs/pr-process/$STORY_ID.url"
```

Labels are resolved from:

- `epic-NN-<slug>` — derived from the story's parent epic folder name.
- `layer:<bronze|silver|gold|infra>` — derived from the dominant file-path
  prefix in `git diff --name-only`.
- `requires-sandbox-teardown` — always present (so CI can route the
  `sandbox-cleanup.yml` workflow).

**Hard rule:** the PR body must include the literal token
`<!-- pr-process: managed -->` on the last line. Phase 3 uses this as a
self-identifier when polling — without it, the skill refuses to update
the PR body.

### Phase 3 — Drive Review

The skill polls the PR until it reaches a terminal state. The poll loop
calls `gh pr view --json reviews,statusCheckRollup,mergeStateStatus`.

```bash
PR_NUMBER="${RESOLVED_ARG#https://*/pull/}"  # attach mode: numeric arg
# or, story mode: PR_URL captured in Phase 2
```

States and actions:

| `mergeStateStatus` + reviews | Action |
|---|---|
| `BLOCKED`, no reviews yet | Print "Awaiting review" status line, sleep, re-poll (or hand back to user with current state). |
| `CHANGES_REQUESTED` | Read each unresolved review thread via `gh api repos/{owner}/{repo}/pulls/{pr}/comments`. Classify each comment by the file path it targets, then route fixes through the matching skill: `src/.../bronze/` → `/developer-plugin:update-ingestion`; `src/.../silver/` → `/developer-plugin:update-silver`; `src/.../gold/` → `/developer-plugin:update-gold`; `airflow/dags/` → `/developer-plugin:update-dag`; `_infra/ci/`, `.github/workflows/` → `/developer-plugin:update-pipeline`. **NEVER edit the story markdown directly.** |
| `APPROVED` + `statusCheckRollup` all green | Proceed to Phase 4. |
| `APPROVED` + `statusCheckRollup` has FAILING checks | Call `AskUserQuestion` with options `Retry failing checks (gh run rerun)` / `Wait for next push` / `Abort teardown`. Default `Wait`. |
| `MERGED` (PR was merged externally) | Proceed to Phase 4 immediately. |
| `CLOSED` without merge | Stop. Do not run teardown — the user closed the PR for a reason. |

For each fix routed in `CHANGES_REQUESTED`, write a short comment on the
PR via `gh pr comment $PR_NUMBER --body "..."` describing the change and
the skill that applied it, so the reviewer sees a trace.

After every fix, re-run Phase 1 against the new commit before requesting
re-review. The readiness gate is not a one-shot check.

### Phase 4 — Sandbox Teardown (Pluggable Driver)

Once the PR is `APPROVED` (with all required checks green) or `MERGED`,
the skill resolves a teardown driver and invokes it.

#### Driver resolution

1. Read `$PATTERNS_DIR/teardown-pattern.md` and parse its driver registry.
   Each entry is a YAML block: `name`, `script_path` (relative to
   `${CLAUDE_PLUGIN_ROOT}` or `{project_root}`), `applies_when` (a glob
   expression matched against the workspace).
2. Pick the first driver whose `applies_when` matches the current
   workspace. Chapter-6 ships exactly one driver: `local-docker`, applies
   when `{project_root}/_infra/docker/docker-compose.yml` exists.
3. If multiple drivers match, call `AskUserQuestion` with the candidates
   so the user picks (this surfaces to readers that the choice is
   pluggable).
4. If zero drivers match, print a WARNING and stop — no destructive op
   without an explicit driver.

#### Driver contract (every driver implements)

A driver is a single executable script (shell or Python). It exposes
three modes via the **first positional argument**:

- `--check` → prints a JSON summary of what *would* be destroyed; exit 0.
- `--dry-run` → prints the exact shell commands it would run; exit 0.
- `--destroy` → actually performs the destroy; on success prints a JSON
  summary of what was destroyed; exit 0. On failure: non-zero exit with
  a `{"driver": "...", "error": "..."}` body on stderr.

JSON summary schema (stable across drivers):

```json
{
  "driver": "<name>",
  "started_at": "<ISO-8601 UTC>",
  "duration_s": <number>,
  "destroyed": [
    {"kind": "container", "name": "patient_360-uc"},
    {"kind": "volume",    "name": "patient_360_uc-data"},
    {"kind": "network",   "name": "patient_360_default"}
  ],
  "skipped": [
    {"kind": "<kind>", "name": "<name>", "reason": "<reason>"}
  ]
}
```

#### Invocation

Run check + dry-run first; print both to the session so the user sees the
plan. Then invoke destroy:

```bash
DRIVER_PATH="${CLAUDE_PLUGIN_ROOT}/skills/pr-process/scripts/teardown_drivers/local_docker.sh"
"$DRIVER_PATH" --check    | tee /tmp/teardown-check.json
"$DRIVER_PATH" --dry-run  | tee /tmp/teardown-plan.txt

# Confirm with user before destructive op (skip in attach mode + CI).
if [ -t 0 ]; then
  # interactive — call AskUserQuestion (Proceed / Abort)
  :
fi

SUMMARY="$("$DRIVER_PATH" --destroy)"
echo "$SUMMARY" > "{workspace_root}/outputs/pr-process/$STORY_ID.teardown.json"
```

#### Local-docker driver behaviour (shipped)

The `local-docker` driver runs three steps in order:

1. `docker compose -f {project_root}/_infra/docker/docker-compose.yml down -v --remove-orphans`
   — stops every service in the compose project AND removes the named
   volumes (`uc-data`, `marquez-db`) so the next run starts clean.
2. `docker volume prune -f --filter label=project=patient_360` — sweeps
   any project-labelled stragglers (e.g. ad-hoc volumes from CI runs).
3. **Optional**, only if `{project_root}/_infra/docker/uc-source` exists
   and was created by `make uc-ui-source`: `rm -rf` that source clone.
   The driver checks for a `.uc-ui-source` marker file before deleting.

The driver MUST NOT touch volumes outside the docker-compose project (no
unfiltered `docker volume prune`, no `docker system prune`).

#### Post-teardown comment

Comment on the PR with the summary so reviewers see the trace:

```bash
gh pr comment "$PR_NUMBER" --body "🧹 Sandbox destroyed (driver=local-docker) at $(date -u +%Y-%m-%dT%H:%M:%SZ).

\`\`\`json
$SUMMARY
\`\`\`

Generated by \`/developer-plugin:pr-process\`."
```

### Phase 5 — Verification Compliance Self-Check (mandatory before reporting OK)

The story's `## Verification` block is the contract. Even though this skill
doesn't generate code itself, it MUST confirm that the underlying ACs are
still green at end-of-phase — otherwise a regression introduced during
review (Phase 3) goes undetected.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_acs.py "$STORY_ID" --json
```

Parse the JSON output. For each AC in `acs[]`:

- `status == "FAIL"` with at least one non-`manual` check failing →
  emit one CRITICAL line per failing check:
  `CRITICAL $STORY_ID AC<N>: <check.spec> — <check.detail>`
  Then **stop**. Do NOT print the OK trailer.
- `status == "FAIL"` but every failing check is `manual:` → INFO only.
- `status == "PASS"` / `INDETERMINATE` → continue.
- `has_verification == false` → emit one WARNING and continue.

This phase is the only place this skill flips its overall result from OK
to FAILED.

## Output Format

```
RESOLVED TARGET: <value> (source: <...>)

=== Phase 1: Readiness ===
PASS  git tree clean
PASS  branch ahead of origin/main by N commits
PASS  story Approved
PASS  make lint
PASS  make test (N tests, 0 failures)
PASS  verify_acs.py — all ACs green
PASS  validate-stories — clean

=== Phase 2: Opened PR ===
PR:    https://github.com/<owner>/<repo>/pull/<N>
Title: STORY-NN-NNN: <title>
Labels: epic-01-foundation, layer:silver, requires-sandbox-teardown
Body:  <pr-body.md path>

=== Phase 3: Review ===
Reviews: 2 APPROVED, 0 CHANGES_REQUESTED
Checks:  lint ✅  unit-test ✅  integration-test ✅  pr-preview ✅

=== Phase 4: Sandbox Teardown ===
Driver: local-docker (1 match)
Plan:
  docker compose -f .../docker-compose.yml down -v --remove-orphans
  docker volume prune -f --filter label=project=patient_360
Destroyed: 5 containers, 2 volumes, 1 network (3.2s)
Comment posted: <comment URL>

=== Phase 5: AC Self-Check ===
ACs PASS: 4/4

Result: PASS
```

## Pitfall Prevention

- **NEVER run teardown without an approved PR.** Phase 4 must be gated on
  `APPROVED` or `MERGED` from Phase 3. Skipping the gate would destroy a
  developer's working environment mid-iteration.
- **NEVER use `docker system prune` or unfiltered `docker volume prune`**.
  The `local-docker` driver scopes everything to the compose project
  (`-f docker-compose.yml`) plus a project-labelled filter. Anything
  broader could nuke unrelated containers on the user's machine.
- **NEVER edit the story markdown to satisfy review comments.** Stories
  are owned by `scrum-master-plugin`. If a reviewer wants story changes,
  route the request to `/scrum-master-plugin:update-stories` and tell the
  reviewer to re-approve after.
- **NEVER short-circuit Phase 1.** Every fix routed in Phase 3 must
  re-pass Phase 1 before re-requesting review. Stale lint/test results
  hide regressions.
- **NEVER hardcode docker-compose paths or volume names.** All paths
  come from workspace discovery + the driver's own knowledge of the
  compose file it owns. The driver is the only place that names volumes.
- **NEVER swallow teardown errors.** If `docker compose down -v` fails,
  the driver exits non-zero and the skill reports CRITICAL. A silent
  partial teardown is worse than no teardown.
- **NEVER open a PR if `BRANCH == main`.** The readiness gate catches
  this, but assert it again at the `gh pr create` call just in case.

## Writing Style

- Be terse in PR-comments. Reviewers skim — use bullets, links, and short
  command quotes.
- In status output, prefer fixed-width tables (` ✅ ` / ` ❌ `) over
  long prose. The user reads this between phases.
- Always identify the driver and the PR number in any human-facing line
  so multi-PR sessions don't blur.

## File Conventions

- Story files: `{stories_dir}/EPIC-NN-<slug>/STORY-NN-NNN-<slug>.md`
- PR body template: `${CLAUDE_PLUGIN_ROOT}/skills/pr-process/pr_body.md.j2`
- Readiness aggregator: `${CLAUDE_PLUGIN_ROOT}/skills/pr-process/scripts/check_pr_readiness.py`
- Teardown drivers: `${CLAUDE_PLUGIN_ROOT}/skills/pr-process/scripts/teardown_drivers/<name>.sh`
- Driver README (contract): `${CLAUDE_PLUGIN_ROOT}/skills/pr-process/scripts/teardown_drivers/README.md`
- Outputs (per story):
  - `{workspace_root}/outputs/pr-process/<STORY_ID>.url`
  - `{workspace_root}/outputs/pr-process/<STORY_ID>.teardown.json`

## Learnings & Corrections

After every user correction, append to the learnings queue:

```bash
echo '{"skill":"pr-process","date":"'"$(date -u +%Y-%m-%d)"'","correction":"<what>","pattern":"<rule>","status":"pending"}' \
  >> "{workspace_root}/memory/developer/learnings-queue.jsonl"
```

At session end with pending entries, run `/developer-plugin:apply-learnings`.

### Active Learnings

<!-- New L-NNN entries get appended below by apply-learnings. Keep absolute
     directives ("MUST" / "NEVER") so they survive context-window pressure. -->

(no learnings yet — this skill is new)

## References

- `inputs/code/v1/teardown-pattern.md` — driver contract and extension path.
- `inputs/code/v1/ci-cd-pattern.md` § PR lifecycle workflows — the CI-side
  pair (`pr-preview.yml`, `sandbox-cleanup.yml`, `promote.yml`).
- `inputs/code/v1/docker-compose-conventions.md` — named volumes the
  local-docker driver removes.
- `developer-plugin/skills/validate-stories/SKILL.md` — Phase 1 gate.
- `developer-plugin/scripts/verify_acs.py` — Phase 1 + Phase 5 AC checks.
