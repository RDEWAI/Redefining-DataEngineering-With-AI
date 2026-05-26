---
skill: create-pipeline
status: filled
version: "1.1"
last_reviewed: 2026-05-25
---

# create-pipeline — Skill-Creator Eval

## What this skill should do

Generate CI/CD pipeline configuration: skeleton edits for lint/unit-test/integration-test PLUS the three PR-lifecycle workflows (pr-preview, sandbox-cleanup, promote).

## Scenarios

### S1 — Fresh project, GitHub Actions

**Invoke**: `/developer-plugin:create-pipeline github`

**Expected**:
- Skill clarifies platform (github vs gitlab) via AskUserQuestion if not in arg.
- Edits existing skeletons under `_infra/ci/.github/workflows/{lint,unit-test,integration-test}.yml` rather than overwriting.
- Creates `_infra/ci/.github/workflows/pr-preview.yml` matching the embedded template — must have `if: always()` teardown.
- Creates `_infra/ci/.github/workflows/sandbox-cleanup.yml` — must call `teardown_drivers/local_docker.sh --destroy`.
- Creates `_infra/ci/.github/workflows/promote.yml` — must gate `promote-prod` on `environment: production`.
- Phase 3 invokes validate-pipeline on the new files.

### S2 — Existing skeletons are honoured

**Setup**: `lint.yml` already has caching configured.

**Expected**: skill EDITS lint.yml additively. Never re-creates from scratch. Existing caching survives.

### S3 — GitLab platform

**Invoke**: `/developer-plugin:create-pipeline gitlab`

**Expected**: writes `_infra/ci/.gitlab-ci.yml`; does NOT write the three `pr-*.yml` files (GitLab pipelines have a different shape — out of scope for this round).

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "set up CI for this project" | create-pipeline | update-pipeline |
| "generate the sandbox-cleanup workflow" | create-pipeline | pr-process (which calls the driver, doesn't generate workflows) |
| "make sure the promote step requires manual approval" | create-pipeline | update-pipeline (if no existing promote.yml) |

## Description quality checks

- [x] First sentence states the skill's job.
- [x] Three new workflow filenames listed.
- [x] Argument-hint format (`[platform: github|gitlab]`).
- [x] Ownership split with create-scaffold explicit.

## Known weaknesses

- GitLab CI is mentioned but no exemplar gitlab-ci.yml golden is committed yet.
- The promote.yml template uses `workflow_dispatch.inputs` typed as `choice`; older GitHub runners (≤actions/runner-v2.300) ignore `type:` — eval should warn if the runner is older.
