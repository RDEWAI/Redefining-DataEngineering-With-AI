# STORY-08-003: Delta VACUUM and OPTIMIZE Scheduling

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening + Performance |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 10 |
| **Dependencies** | STORY-07-003 |
| **Status** | To Do |

## User Story

As a data operations engineer, I want scheduled Delta VACUUM and OPTIMIZE tasks so that small files are compacted and expired data is cleaned up automatically.

## Description

Create scheduled maintenance tasks for: (1) Weekly VACUUM with 7-day retention (168 hours) for all Delta tables. (2) Auto-compact enabled for PROD only. (3) Dead letter cleanup: remove files older than 30 days (90 days for allergy dead letters). Implement as Airflow DAG tasks or standalone Make targets.

## Acceptance Criteria

- [ ] Weekly VACUUM scheduled with 168-hour retention [LLD §3.1]
- [ ] Auto-compact enabled for PROD environment only [LLD §3.1]
- [ ] Dead letter cleanup: 30-day retention, 90-day for allergy [LLD §3.4, SS8.2]
- [ ] Maintenance does not interfere with pipeline execution window [LLD §4.1]

## Technical Notes

- **Upstream references**: LLD SS3.1 (Storage Format), SS3.4 (Retention Policy), SS8.2
- **Implementation hints**: Delta VACUUM: `VACUUM table_path RETAIN 168 HOURS`. Schedule outside peak hours. OPTIMIZE: `OPTIMIZE table_path ZORDER BY (partition_column)` if applicable.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS3.1, SS3.4, SS8.2 |
| DMS | -- |
| STM | -- |
| DQS | -- |
