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

## Checks

### CRITICAL (must fix before merge)
- YAML syntax errors
- Missing required stages: lint, test, deploy
- Hardcoded secrets or credentials (use environment variables / secrets manager)
- Deploy stage not gated on `main` branch

### WARNING (should fix)
- No dependency caching configured
- Test stage does not run `pytest`
- No artifact upload for test results

### INFO (good to know)
- No parallelism configured for test stage
- No notification step on failure

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
