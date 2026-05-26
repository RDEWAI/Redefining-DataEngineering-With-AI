---
skill: validate-pipeline
status: filled
version: "1.1"
last_reviewed: 2026-05-25
---

# validate-pipeline — Skill-Creator Eval

## What this skill should do

Validate pipeline YAML files against project conventions; report CRITICAL / WARNING / INFO findings.

## Scenarios

### S1 — pr-preview.yml missing always-teardown

**Setup**: `pr-preview.yml` has a teardown step but no `if: always()`.

**Expected**: emit one CRITICAL finding. Mention the consequence (orphan volumes on the runner).

### S2 — sandbox-cleanup.yml inlines docker compose down

**Setup**: `sandbox-cleanup.yml` has a `run: docker compose -f … down -v` step but does NOT call the shared driver under `teardown_drivers/`.

**Expected**: CRITICAL. Mention the driver-as-single-source-of-truth rule from teardown-pattern.md.

### S3 — promote.yml lacks environment gate

**Setup**: `promote.yml` has a `promote-prod` job with `if: github.ref == 'refs/heads/main'` but no `environment: production`.

**Expected**: CRITICAL. Mention that `if:` alone does not enforce required reviewers.

### S4 — All clean

**Expected**: report PASS, no findings.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "is the promote workflow safe" | validate-pipeline | update-pipeline |
| "lint these workflow files" | validate-pipeline | create-pipeline |

## Description quality checks

- [x] CRITICAL list enumerates the 3 new workflow CRITICAL checks.
- [x] WARNING list has at least one per new workflow.

## Known weaknesses

- The skill currently has no scripts/validate_pipeline.py — validation runs as prose in the Claude session. A future round should generate a real Python validator and gate the PostToolUse hook on it.
