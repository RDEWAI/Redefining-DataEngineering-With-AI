# STORY-07-003: Environment Promotion Flow (DEV -> STAGING -> PROD)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Deployment + Rollback |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 9 |
| **Dependencies** | STORY-07-002 |
| **Status** | To Do |

## User Story

As a data engineer, I want automated DEV deployment on merge and manual approval gates for STAGING and PROD so that the promotion process follows the defined review protocol.

## Description

Implement the 3-stage promotion flow: (1) DEV: auto-deploy on merge to main via `make run-pipeline`. (2) STAGING: manual approval workflow, run integration tests in STAGING environment. (3) PROD: manual approval + 2 reviewers required, run DQ threshold check in STAGING before allowing PROD promotion. All per LLD SS9.2 promotion process.

## Acceptance Criteria

- [ ] DEV auto-deploys on merge to main [LLD §9.2]
- [ ] STAGING requires manual approval before promotion [LLD §9.2]
- [ ] STAGING promotion runs integration tests [LLD §9.2]
- [ ] PROD requires manual approval + 2 reviewers [LLD §9.2]
- [ ] PROD promotion checks DQ thresholds from STAGING run [LLD §9.2]

## Technical Notes

- **Upstream references**: LLD SS9.2 (Promotion Process)
- **Implementation hints**: Use GitHub Actions environment protection rules for STAGING and PROD approvals. `make run-pipeline` for DEV, `make test-integration` for STAGING validation.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS9.2 |
| DMS | -- |
| STM | -- |
| DQS | -- |
