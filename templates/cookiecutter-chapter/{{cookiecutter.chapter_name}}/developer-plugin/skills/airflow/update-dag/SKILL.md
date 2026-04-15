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

## Workflow

### Phase 0: Read Current State
- Read the existing DAG file
- Read the latest LLD from `inputs/` to understand what changed
- Diff the two to determine the minimal set of edits needed

### Phase 1: Clarify Changes
Use `AskUserQuestion` to confirm scope if the diff is ambiguous.

### Phase 2: Apply Edits
- Edit in-place for same-day changes
- Bump the version comment at the top of the file
- Preserve all existing task IDs unless explicitly renamed

### Phase 3: Validate
Invoke `/developer-plugin:validate-dag` on the updated file.
