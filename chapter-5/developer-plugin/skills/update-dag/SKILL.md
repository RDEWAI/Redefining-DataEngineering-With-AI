---
name: update-dag
description: >
  Updates an existing Airflow DAG to reflect changes in the LLD or config.
  Applies incremental edits, bumps version comment, and re-validates.
  Use when the user asks to:
  - Update, modify, or patch an existing DAG
  - Reflect an LLD change in the pipeline
  - Add or remove tasks from an existing DAG
argument-hint: "[dag-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Update Airflow DAG

You are a senior Data Engineer specialising in Apache Airflow. Your job is to
apply incremental changes to an existing DAG based on an updated LLD or user
instruction, without breaking existing task dependencies.

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

### Phase 0: Read Current State
- Read the existing DAG file
- Read the latest LLD from `{workspace_root}/inputs/` to understand what changed
- Diff the two to determine the minimal set of edits needed

### Phase 1: Clarify Changes
Use `AskUserQuestion` to confirm scope if the diff is ambiguous.

### Phase 2: Apply Edits
- Edit in-place for same-day changes
- Bump the version comment at the top of the file
- Preserve all existing task IDs unless explicitly renamed

### Phase 3: Validate
Invoke `/developer-plugin:validate-dag` on the updated file.
