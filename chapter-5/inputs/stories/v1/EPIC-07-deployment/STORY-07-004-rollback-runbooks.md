# STORY-07-004: Delta RESTORE Runbook and Pipeline Re-run Procedure

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Deployment + Rollback |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 9 |
| **Dependencies** | STORY-05-006 |
| **Status** | To Do |

## User Story

As a data operations engineer, I want rollback runbooks documenting Delta RESTORE commands and pipeline re-run procedures so that I can recover from failures within the 4-hour RTO.

## Description

Create two operational runbooks: (1) Delta RESTORE runbook with step-by-step commands to restore Gold tables to a previous version using Delta time travel. Include commands for listing available versions, verifying data before restore, and validating after restore. (2) Pipeline re-run procedure documenting how to trigger Airflow DAG for specific ds dates, including backfill scenarios and partial re-runs.

## Acceptance Criteria

- [ ] Delta RESTORE runbook with step-by-step commands for Gold tables [LLD §9.3]
- [ ] Includes version listing, pre-restore verification, post-restore validation [LLD §9.3]
- [ ] Pipeline re-run procedure for specific ds dates [LLD §9.3]
- [ ] Backfill scenario documented [LLD §9.3]
- [ ] Recovery achievable within 4-hour RTO target [DRD §4.3]

## Technical Notes

- **Upstream references**: LLD SS9.3 (Rollback), DRD SS4.3 (RTO: 4 hours, RPO: 24 hours)
- **Implementation hints**: Delta RESTORE: `RESTORE TABLE warehouse/{env}/gold/patient_summary TO VERSION AS OF {version}`. Use `DESCRIBE HISTORY` to list versions. Airflow re-run: `airflow dags trigger patient360_hourly_v1 --execution-date {ds}`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS9.3 |
| DMS | -- |
| STM | -- |
| DQS | -- |
