# STORY-08-001: Performance Tuning for Observations Table

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening + Performance |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 10 |
| **Dependencies** | STORY-07-003 |
| **Status** | To Do |

## User Story

As a data engineer, I want the observations table processing tuned for the 4.4M row dataset so that it completes within 8 minutes meeting the critical path SLA.

## Description

Tune shuffle partitions, memory settings, and write parallelism for the observations table (largest in the pipeline at 4.4M rows, ~800 MB Delta). Verify that `transform_observations_silver` completes within 8 minutes in DEV. Adjust `spark.sql.shuffle.partitions` to 8, verify 8 output files of ~75 MB each. Profile and optimize any shuffle-heavy operations.

## Acceptance Criteria

- [ ] Observations Silver transform completes within 8 min in DEV [LLD §4.4]
- [ ] Shuffle partitions set to 8 producing ~75 MB files [LLD §6.5]
- [ ] No OOM errors during processing [LLD §6.5]
- [ ] Performance profiled and bottlenecks documented [LLD §6.5]

## Technical Notes

- **Upstream references**: LLD SS6.5 (Partition Tuning), SS4.4 (Critical Path)
- **Implementation hints**: Use Spark UI to identify shuffle stages. Consider coalesce after transformation to control output file count. Monitor with `spark.executor.memoryOverhead` if OOM occurs.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS6.5, SS4.4 |
| DMS | -- |
| STM | -- |
| DQS | -- |
