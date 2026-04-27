# EPIC-07: Release & CI/CD

| Field | Value |
|-------|-------|
| **LLD Section** | §9 |
| **Epic Scope** | crosscut |
| **Stories** | 4 |
| **Total Points** | 16 |
| **Sprints** | 5 |
| **Status** | To Do |

## Objective

Cross-layer release work: GitHub Actions CI workflows (lint, unit, integration), Liquibase DDL changelogs for all 29 tables, DEV→STAGING→PROD promotion runbook, full-pipeline E2E load test, and rollback procedure per LLD §9. This is system-wide deploy — per-layer epics intentionally skipped `deploy-validation`.

## Scope

### In Scope
- `.github/workflows/lint.yml`, `unit-test.yml`, `integration-test.yml` per LLD §9.3
- Liquibase changelogs under `ddl/liquibase/changelogs/` (29 tables)
- Promotion runbook per environment per LLD §9.3
- Full-pipeline E2E load test (run + reconcile + assert SLA) per LLD §9.3
- Rollback runbook (Delta RESTORE + re-run) per LLD §9.4

### Out of Scope
- Layer-specific work (lives in EPIC-02..05)
- Observability (EPIC-06)

## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|
| STORY-07-001 | GitHub Actions CI — lint + unit + integration workflows | release | 5 | 5 | STORY-05-005 |
| STORY-07-002 | Liquibase DDL changelogs for all 29 tables | release | 5 | 5 | STORY-01-003 |
| STORY-07-003 | DEV→STAGING→PROD promotion runbook + full-pipeline E2E load test | release | 3 | 5 | STORY-07-001, STORY-07-002 |
| STORY-07-004 | Rollback runbook — Delta RESTORE + re-run procedure | release | 3 | 5 | STORY-07-003 |

## Acceptance Criteria (Epic-Level)

- [ ] CI green on `main` for lint + unit + integration jobs [LLD §9.3]
- [ ] All 29 tables have Liquibase changelogs under `ddl/liquibase/changelogs/` [LLD §9.1]
- [ ] Full-pipeline E2E load test runs in < 30 min on STAGING and meets DQ thresholds [LLD §4.4, §9.3]
- [ ] Rollback runbook tested — Delta RESTORE on Gold tables succeeds [LLD §9.4]

## Risks & Assumptions

- Production freeze window per team-capacity §5 — schedule accordingly
- 2-reviewer rule for PROD promotion enforced via branch protection [LLD §9.3]
