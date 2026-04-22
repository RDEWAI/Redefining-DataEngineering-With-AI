# STORY-04-004: Transform Observations to Silver

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the observations fact table transformed to Silver with partition tuning for the largest table so that 4.4M rows process within the pipeline SLA.

## Description

Implement `src/pipelines/silver/transform_observations.py` that reads Bronze `synthea_observations`, validates FKs against encounters, and writes to `warehouse/{env}/silver/clinical/clinical_observations/`. This is the largest table (4.4M rows, ~800 MB) and requires shuffle partition tuning to 8 partitions per LLD SS6.5. Inline SE with action_if_failed: drop. On the critical path -- processing time ~8 min.

## Acceptance Criteria

- [ ] Reads from Bronze and writes to Silver `clinical_observations` [LLD §5.2]
- [ ] FK validated against clinical_encounters [DMS §5]
- [ ] Shuffle partitions tuned to 8 for observations processing [LLD §6.5]
- [ ] Inline SE validates rules DQ-FLD-077 to DQ-FLD-079 with action_if_failed: drop [DQS §2]
- [ ] Processes 4.4M rows within ~8 min per critical path estimate [LLD §4.4]
- [ ] Empty input writes empty table [LLD §5.2]

## Technical Notes

- **Upstream references**: LLD SS5.2, SS6.5 (Partition Tuning), SS4.4 (Critical Path), DQS SS2
- **Implementation hints**: This table is on the critical path. Set `spark.sql.shuffle.partitions=8` within the task. Target 8 output files of ~75 MB each. Monitor memory usage in DEV -- may need executor memory increase.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2, SS6.5, SS4.4 |
| DMS | SS5 (clinical_observations schema) |
| STM | Tab:Bronze-to-Silver (observations) |
| DQS | SS2 (DQ-FLD-077 to DQ-FLD-079) |
