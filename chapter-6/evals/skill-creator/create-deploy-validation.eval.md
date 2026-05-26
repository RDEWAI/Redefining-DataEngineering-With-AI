---
skill: create-deploy-validation
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# create-deploy-validation — Skill-Creator Eval

## What this skill should do

Generate per-layer local deploy smoke artifacts: shell scripts under `_infra/cd/` that re-apply Liquibase + re-sync DAG bag, plus a pytest integration module that drives them.

## Scenarios

### S1 — Bronze deploy smoke

**Invoke**: `/developer-plugin:create-deploy-validation STORY-02-099` (deploy-validation story).

**Expected**:
- Emits `_infra/cd/apply-bronze-liquibase.sh` (idempotent Liquibase update).
- Emits `_infra/cd/sync-bronze-dags.sh` (rsync DAGs into the Airflow container).
- Emits `tests/integration/bronze/test_deploy_smoke.py` (asserts each script exits 0 + re-triggered DAG run completes).

### S2 — Hard rules

- Scripts must be idempotent (re-running them never errors).
- Tests must assert Airflow reports no DAG import errors after sync.
- Never inlines table names — reads them from the story's deliverable map.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "build the deploy smoke for bronze" | create-deploy-validation | create-integration-test |
| "scripts that reapply liquibase locally" | create-deploy-validation | create-scaffold |
| "test the dag bag sync works" | create-deploy-validation | create-integration-test |

## Description quality checks

- [x] Pairs 1:1 with scrum-master deploy-validation story type.
- [x] Local-only scope explicit (no cloud).

## Known weaknesses

- No fallback if the docker-compose stack isn't running — the eval should test that case.
