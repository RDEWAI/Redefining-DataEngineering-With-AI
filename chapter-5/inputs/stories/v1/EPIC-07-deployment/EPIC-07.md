# EPIC-07: Deployment + Rollback

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 7 (LLD impl-sequence) |
| **Stories** | 4 |
| **Total Points** | 16 |
| **Sprints** | Sprint 9 |
| **Status** | To Do |

## Objective

Establish CI/CD pipeline with GitHub Actions (in `_infra/ci/`), Liquibase DDL migrations, 3-stage local environment promotion flow (DEV -> STAGING -> PROD via Make targets), and operational runbooks for Delta RESTORE rollback and pipeline re-run. No Docker image build or container deployment -- all environments run locally per LLD §9.3 Decision 12.

## Scope

### In Scope
- GitHub Actions CI (`_infra/ci/.github/workflows/`: lint, unit-test, integration-test)
- Liquibase DDL changelogs for all 29 tables (`ddl/liquibase/changelogs/{table}.xml`) with master-changelog
- Local environment promotion flow with manual approval gates (`_infra/cd/{dev,staging,prod}/promote.sh`)
- Delta RESTORE runbook and pipeline re-run procedure
- STAGING promotion gated on `se_runner.py` implementation (STORY-02-006)

### Out of Scope
- Docker image build / container registry push (architecture is local-only, LLD Decision 12)
- Performance tuning (EPIC-08)
- Monitoring dashboards (handled in EPIC-06)

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-07-001 | GitHub Actions CI Pipeline | 5 | Sprint 9 | STORY-05-006 |
| STORY-07-002 | Liquibase DDL Migrations for All Tables | 3 | Sprint 9 | STORY-07-001 |
| STORY-07-003 | Environment Promotion Flow | 5 | Sprint 9 | STORY-07-002, STORY-02-006 |
| STORY-07-004 | Delta RESTORE Runbook and Pipeline Re-run Procedure | 3 | Sprint 9 | STORY-05-006 |

## Acceptance Criteria (Epic-Level)

- [ ] CI blocks PRs with lint failures or < 90% coverage [LLD §9.3]
- [ ] Integration tests run automatically on merge to main [LLD §9.3]
- [ ] Liquibase changelogs exist for all 29 tables and `make migrate` runs without error [LLD §9.1]
- [ ] PROD promotion requires manual + 2 reviewer approval; no container build/push [LLD §9.3]
- [ ] STAGING promotion blocked until `se_runner.py` implemented [LLD §8.5, Decision 14]
- [ ] Rollback runbook enables recovery within 4-hour RTO [DRD §4.3]

## Risks & Assumptions

- STAGING promotion is blocked by `se_runner.py` pending implementation (STORY-02-006 must complete first)
- Failed local promotion to STAGING/PROD -- mitigated by Delta RESTORE for instant rollback
- Assumption: No Docker required -- local Spark and UC OSS accessible on all dev machines
