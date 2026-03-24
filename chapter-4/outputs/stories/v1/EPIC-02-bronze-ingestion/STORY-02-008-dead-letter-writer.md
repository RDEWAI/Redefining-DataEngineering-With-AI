# STORY-02-008: Implement Dead Letter Writer

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 4 |
| **Dependencies** | STORY-02-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want a dead letter writer that persists rejected records with rejection metadata so that DQ failures can be investigated without losing data.

## Description

Implement dead letter writing functionality in `src/utils/delta_helpers.py`. When the SE runner quarantines rows (action_if_failed: drop), the dead letter writer persists them to `warehouse/{env}/dead-letter/{table}/{ds}/` in Parquet format. Each rejected record includes the original columns plus: `_rejection_reason` (VARCHAR), `_rejected_at` (TIMESTAMP), `_rejected_by_rule` (VARCHAR), and `_pipeline_run_id` (VARCHAR). Allergy table rejections have 90-day retention (safety-critical); all others have 30-day retention.

## Acceptance Criteria

- [ ] Dead letter writer writes to `warehouse/{env}/dead-letter/{table}/{ds}/` [LLD §8.2]
- [ ] Output format is Parquet with Snappy compression [LLD §8.2]
- [ ] Rejected records include original columns plus _rejection_reason, _rejected_at, _rejected_by_rule, _pipeline_run_id [LLD §8.2]
- [ ] Allergy table rejections set to 90-day retention [LLD §8.2, DRD SS1.3]
- [ ] All other table rejections set to 30-day retention [LLD §8.2]
- [ ] Unit tests verify schema of dead letter output and metadata column population [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD SS8.2 (Dead Letter / Quarantine Strategy), LLD SS3.2 (Storage Layout), DRD SS1.3 (allergy safety)
- **Implementation hints**: Use PySpark DataFrame write with Parquet format. Add metadata columns using `withColumn()`. Retention is managed by a scheduled cleanup job (out of scope for this story -- handled in EPIC-08).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS8.2, SS3.2, SS3.4 |
| DMS | -- |
| STM | -- |
| DQS | SS1 (rejection handling policy) |
