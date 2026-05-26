---
name: validate-pipeline
description: >
  Validates a CI/CD pipeline configuration file for correctness and
  project conventions. Reports CRITICAL / WARNING / INFO findings.
  Use when the user asks to:
  - Validate, check, or lint a CI/CD pipeline file
  - Verify pipeline has all required stages
  - Confirm pipeline follows project standards
argument-hint: "[pipeline-file-path]"
allowed-tools: Read, Bash, Grep, Glob
context: fork
---

# Validate CI/CD Pipeline

Validate the target pipeline configuration and report findings.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Coding Patterns Handbook

Load the pattern doc this skill checks against (read-only; no freshness prompt):

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "WARNING: inputs/code/v*/ not found — pattern-conformance checks will be INDETERMINATE."
fi
```

**Pattern docs consulted:**

- `$PATTERNS_DIR/ci-cd-pattern.md` — stage layout, pinned action SHAs, UV in CI

### References trailer (in output)

Cite each pattern doc consulted, e.g. `Checked against inputs/code/v1/ci-cd-pattern.md §stages`.

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

## Checks

### CRITICAL (must fix before merge)
- YAML syntax errors
- Missing required stages: lint, test, deploy
- Hardcoded secrets or credentials (use environment variables / secrets manager)
- Deploy stage not gated on `main` branch
- **`pr-preview.yml` (file basename match)**: missing the teardown step,
  OR teardown lacks `if: always()`, OR teardown command is not
  `docker compose ... down -v --remove-orphans`. Any of these can leak
  named volumes onto the CI runner.
- **`sandbox-cleanup.yml` (file basename match)**: trigger is not
  `pull_request: closed`, OR the workflow does not invoke a script
  under `developer-plugin/skills/pr-process/scripts/teardown_drivers/`.
  Inline `docker compose down` instead of the shared driver is a
  CRITICAL: the driver is the only place the teardown contract lives.
- **`promote.yml` (file basename match)**: the `prod` deploy job lacks
  `environment: production` (or equivalent GitHub-environment gate),
  OR it triggers on plain `push: branches: [main]` without a manual
  `workflow_dispatch` step.

### WARNING (should fix)
- No dependency caching configured
- Test stage does not run `pytest`
- No artifact upload for test results
- `pr-preview.yml`: integration-test stage runs against the host
  ports of the docker-compose stack instead of `localhost` — fragile
  on shared runners.
- `sandbox-cleanup.yml`: missing artifact upload of the teardown
  summary JSON — review trail is harder to reconstruct.
- `promote.yml`: tag pattern is broader than `v*` (e.g. matches
  arbitrary tags) — easier to fire promote by accident.

### INFO (good to know)
- No parallelism configured for test stage
- No notification step on failure
- `pr-preview.yml` does not pin the integration-test marker (`-m "not e2e"`) — slower preview runs.

## Output Format

```
CRITICAL: [count] issue(s)
  - [description]

WARNING: [count] issue(s)
  - [description]

INFO: [count] item(s)
  - [description]

Result: PASS / FAIL
```
