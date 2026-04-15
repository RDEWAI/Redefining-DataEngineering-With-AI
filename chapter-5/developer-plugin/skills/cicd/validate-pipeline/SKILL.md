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
