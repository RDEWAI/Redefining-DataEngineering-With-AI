---
skill: update-pipeline
status: filled
version: "1.1"
last_reviewed: 2026-05-25
---

# update-pipeline — Skill-Creator Eval

## What this skill should do

Apply incremental edits to existing pipeline YAML without destroying load-bearing invariants.

## Scenarios

### S1 — Add caching to lint.yml

**Invoke**: `/developer-plugin:update-pipeline _infra/ci/.github/workflows/lint.yml` plus instruction "add uv cache".

**Expected**: edits in-place, adds `setup-uv` cache wiring, adds comment with date + rationale, does not remove any existing step.

### S2 — Cannot remove `if: always()` from pr-preview.yml

**Invoke**: ask the skill to "simplify the teardown step in pr-preview.yml".

**Expected**: refuses, prints the Hard rule from SKILL.md: "the teardown step must remain `if: always()`". Suggests opening a separate change to refactor the integration smoke instead.

### S3 — Cannot inline `docker compose down` into sandbox-cleanup.yml

**Setup**: user requests "just run docker compose down here so we don't need the driver".

**Expected**: refuses; references the shared-driver contract from teardown-pattern.md and the validate-pipeline CRITICAL check.

### S4 — Bumping action SHAs across all workflows

**Invoke**: "update actions/checkout to v6 everywhere".

**Expected**: ruff-style mechanical replace across `_infra/ci/.github/workflows/*.yml`; preserves indentation; comment block at top of each file notes the bump date.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "tweak the python matrix in unit-test.yml" | update-pipeline | create-pipeline |
| "add a slack notification step to the deploy job" | update-pipeline | create-pipeline |
| "delete the lint workflow" | (refuse — destructive) | — |

## Description quality checks

- [x] Argument-hint clear.
- [x] References the six pipeline file shapes via the table.
- [x] Hard rules block survives accidental edits.

## Known weaknesses

- SKILL.md does not enumerate which mechanical refactors are safe vs unsafe; the harness can only check Hard rules text presence.
