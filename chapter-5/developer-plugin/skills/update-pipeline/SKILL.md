---
name: update-pipeline
description: >
  Updates an existing CI/CD pipeline configuration to reflect changes in
  project structure, dependencies, or deployment targets.
  Use when the user asks to:
  - Update, modify, or extend an existing CI/CD pipeline
  - Add a new stage or job to the pipeline
  - Change the deployment target or runner
argument-hint: "[pipeline-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Update CI/CD Pipeline

You are a senior DevOps / Data Engineer. Apply incremental edits to an
existing CI/CD configuration without removing existing stages unless
explicitly instructed.

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

Before editing CI config, load the latest coding-patterns handbook:

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

### Phase 1: Read Current State
Read the existing pipeline file and understand its current structure.

### Phase 2: Clarify
Use `AskUserQuestion` to confirm the exact change needed.

### Phase 3: Apply Edits
Edit in-place. Add a comment with the change date and rationale.

### Phase 4: Validate
Invoke `/developer-plugin:validate-pipeline` on the updated file.
