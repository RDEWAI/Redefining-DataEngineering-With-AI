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

## Workflow

### Phase 1: Read Current State
Read the existing pipeline file and understand its current structure.

### Phase 2: Clarify
Use `AskUserQuestion` to confirm the exact change needed.

### Phase 3: Apply Edits
Edit in-place. Add a comment with the change date and rationale.

### Phase 4: Validate
Invoke `/developer-plugin:validate-pipeline` on the updated file.
