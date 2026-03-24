# EPIC-07: Deployment + Rollback

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 7 (LLD impl-sequence) |
| **Stories** | 4 |
| **Total Points** | 16 |
| **Sprints** | Sprint 9 |
| **Status** | To Do |

## Objective

Establish CI/CD pipeline with GitHub Actions, Docker image build, 3-stage environment promotion flow (DEV -> STAGING -> PROD), and operational runbooks for Delta RESTORE rollback and pipeline re-run.

## Scope

### In Scope
- GitHub Actions CI (lint + unit tests on PR, integration tests on merge)
- Docker image build (python:3.11-slim base)
- Environment promotion flow with approval gates
- Delta RESTORE runbook and pipeline re-run procedure

### Out of Scope
- Performance tuning (EPIC-08)
- Monitoring dashboards (handled in EPIC-06)

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-07-001 | GitHub Actions CI Pipeline | 5 | Sprint 9 | STORY-05-006 |
| STORY-07-002 | Docker Image Build | 3 | Sprint 9 | STORY-07-001 |
| STORY-07-003 | Environment Promotion Flow | 5 | Sprint 9 | STORY-07-002 |
| STORY-07-004 | Delta RESTORE Runbook and Pipeline Re-run Procedure | 3 | Sprint 9 | STORY-05-006 |

## Acceptance Criteria (Epic-Level)

- [ ] CI blocks PRs with lint failures or < 90% coverage [LLD §9.2]
- [ ] Integration tests run automatically on merge to main [LLD §9.2]
- [ ] Docker image builds successfully with health check [LLD §9.2, SS9.4]
- [ ] PROD promotion requires 2 reviewer approval [LLD §9.2]
- [ ] Rollback runbook enables recovery within 4-hour RTO [DRD §4.3]

## Risks & Assumptions

- Failed deployment to STAGING/PROD -- mitigated by Delta RESTORE for instant rollback
- Assumption: GitHub Actions runners have Docker support for integration tests
