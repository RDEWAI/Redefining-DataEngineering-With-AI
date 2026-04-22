# STORY-07-003: Environment Promotion Flow (DEV -> STAGING -> PROD)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Deployment + Rollback |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 9 |
| **Dependencies** | STORY-07-002, STORY-02-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want automated DEV deployment on merge and manual approval gates for STAGING and PROD so that the promotion process follows the defined review protocol.

## Description

Implement the 3-stage local promotion flow per LLD §9.3. All environments run locally (no containers): (1) DEV: run `airflow dags trigger patient360_hourly_v1` after `make test` passes. (2) STAGING: manual approval gate; run `make test` with integration markers against STAGING config (STAGING UC OSS, STAGING warehouse path); STAGING promotion is blocked until `se_runner.py` is implemented (STORY-02-006) per LLD Decision 14. (3) PROD: manual approval + 2 reviewers; STAGING DQ scores must be above threshold; use `_infra/cd/{staging,prod}/promote.sh` scripts. Create the `_infra/cd/` scripts, environment-specific config bundles, and `_infra/cd/airflow-sync.sh` for DAG syncing per scaffold layout in LLD §9.1.

## Acceptance Criteria

- [ ] DEV pipeline runs via `airflow dags trigger patient360_hourly_v1` after `make test` passes locally [LLD §9.3]
- [ ] STAGING promotion requires manual approval and `make test` (integration markers) passing against STAGING config [LLD §9.3]
- [ ] STAGING promotion blocked until `se_runner.py` is implemented (STORY-02-006 complete) [LLD §8.5, Decision 14]
- [ ] PROD promotion requires manual approval + 2 reviewers [LLD §9.3]
- [ ] PROD promotion verifies STAGING DQ scores above threshold [LLD §9.3]
- [ ] `_infra/cd/{dev,staging,prod}/promote.sh` scripts created and executable [LLD §9.1]
- [ ] `_infra/cd/airflow-sync.sh` syncs DAG files to Airflow DAGs directory [LLD §9.1]
- [ ] No Docker container build/push -- local-only execution throughout [LLD §9.3, Decision 12]

## Technical Notes

- **Upstream references**: LLD §9.1 (scaffold `_infra/cd/`), LLD §9.3 (Promotion Process + Make targets), LLD §8.5 (SE bootstrap -- STAGING blocked), LLD §13 Decision 12 (Local-Only Architecture), LLD §13 Decision 14 (STAGING promotion checklist)
- **Implementation hints**: Environment separation relies on config (`warehouse/{env}/` paths, UC OSS namespace). Promote scripts call `make test` with env-specific config file. No `docker build` or container registry push.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §9.1 (scaffold infra), §9.3 (Promotion Process + Make targets), §8.5 (bootstrap), §13 Decision 12, Decision 14 |
| DMS | -- |
| STM | -- |
| DQS | -- |
