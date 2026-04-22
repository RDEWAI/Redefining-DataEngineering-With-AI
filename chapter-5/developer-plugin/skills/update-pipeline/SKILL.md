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

## Workflow

### Phase 1: Read Current State
Read the existing pipeline file and understand its current structure.

### Phase 2: Clarify
Use `AskUserQuestion` to confirm the exact change needed.

### Phase 3: Apply Edits
Edit in-place. Add a comment with the change date and rationale.

### Phase 4: Validate
Invoke `/developer-plugin:validate-pipeline` on the updated file.
