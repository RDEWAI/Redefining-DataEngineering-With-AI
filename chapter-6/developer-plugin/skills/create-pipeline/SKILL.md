---
name: create-pipeline
description: >
  Generates CI/CD pipeline configuration (GitHub Actions / GitLab CI) from
  the project structure and LLD artifact. Produces lint, test, and deploy
  workflow files targeting the medallion pipeline.
  Use when the user asks to:
  - Create, generate, or scaffold a CI/CD pipeline
  - Set up GitHub Actions or GitLab CI for the project
  - Automate testing and deployment of the data pipeline
argument-hint: "[platform: github|gitlab]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create CI/CD Pipeline

You are a senior DevOps / Data Engineer. Your job is to generate CI/CD
pipeline configuration that automates lint, test, and deploy for the
medallion data pipeline.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Coding Patterns & Libraries Handbook

Before generating CI config, load the latest coding-patterns handbook:

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required pattern docs for this skill:**

- `$PATTERNS_DIR/ci-cd-pattern.md` — stage layout, pinned action SHAs, UV in CI
- `$PATTERNS_DIR/LIBRARIES.md` — pinned Python / pytest / ruff versions driving the matrix

### Library freshness check

```bash
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, pause and call **AskUserQuestion** with options `Refresh now` / `Proceed with cached versions` / `Cancel`. On Refresh, invoke `/developer-plugin:refresh-libraries` then resume.

### References trailer (in output)

Emit a `### References` section citing consumed pattern docs + LIBRARIES.md vintage. Add a stale-cache warning if the user proceeded with cached versions.

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

### Phase 0: Upstream Gate

Resolve upstream versions via the shared helper (uses `outputs/dev-lock.yaml`
when present, otherwise falls back to latest `v{N}`):

```bash
eval "$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --export)"
LATEST_LLD_DIR="${LATEST_LLD_DIR:-$(ls -d {workspace_root}/outputs/lld/v* | sort -V | tail -1)}"
```

Confirm the LLD in `$LATEST_LLD_DIR/` has `Status: Approved`.

### Phase 1: Clarify Platform & Stages
Use `AskUserQuestion` to confirm:
- CI/CD platform (GitHub Actions / GitLab CI)
- Deployment target (local / Kubernetes / Astronomer / MWAA)
- Required stages: lint → unit-test → integration-test → deploy

### Phase 2: Generate Pipeline Config

**Ownership split with create-scaffold.** The cookiecutter template
already ships three skeleton workflow files — `lint.yml`, `unit-test.yml`,
`integration-test.yml` — each calling the corresponding `make` target.
Those are create-scaffold's domain. This skill:

- May **edit** the three skeletons to add deploy steps, env matrices, or
  caching — never re-create them from scratch.
- **Creates** every other pipeline file: `deploy-*.yml`, `release-*.yml`,
  `promote-*.yml`, `_infra/ci/.gitlab-ci.yml` (if GitLab), and any
  platform-specific config (Astronomer, MWAA).

Write targets:
- **GitHub Actions**: new files under `{project_root}/_infra/ci/.github/workflows/` (but not the three skeleton names listed above — edit those, don't overwrite).
- **GitLab CI**: `{project_root}/_infra/ci/.gitlab-ci.yml`.

Guidelines:
- Include caching for `uv` dependencies.
- Run `uv run pytest tests/` in the test stage (or invoke `make test`).
- Run `uv run ruff check src/` in the lint stage (or invoke `make lint`).
- Deploy stage only runs on `main` branch.

### Phase 3: Validate
Invoke `/developer-plugin:validate-pipeline` on the generated files.

### Phase 4: Verification Compliance Self-Check (MANDATORY before reporting OK)

The story's `## Verification` block is the contract. After every prior
phase has emitted its files, run the AC verifier against the target
story and refuse to declare OK if any mechanical verifier still fails.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/../scripts/verify_acs.py STORY-NN-NNN --json
```

(For batch / multi-story dispatch, run once per story.)

Parse the JSON output. For each AC in `acs[]`:

- `status == "FAIL"` and at least one check has a non-`manual` kind
  that failed → emit one CRITICAL line per failing check:
  `CRITICAL STORY-NN-NNN AC<N>: <check.spec> — <check.detail>`
  Then **stop**. Do NOT mark the plan task `done`. Do NOT print the
  OK trailer. The orchestrator's Phase 2 Step 3.5 reads this and halts
  the story.
- `status == "FAIL"` but every failing check is `manual:` → INFO only
  (manual checks can't fail mechanically; treat as author note).
- `status == "PASS"` / `INDETERMINATE` → continue.
- `has_verification == false` → emit one WARNING line
  `STORY-NN-NNN: no Verification block — generation completed without
  AC compliance check.` Then continue.

This phase is the **only** place this skill flips its overall result
from OK to FAILED. Skills that ignore it leave gaps the orchestrator
cannot see.
