# STORY-08-002: Broadcast Join and Caching Optimization

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening + Performance |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 10 |
| **Dependencies** | STORY-07-003 |
| **Status** | To Do |

## User Story

As a data engineer, I want broadcast join hints and caching applied to Gold table builds so that dimension joins avoid shuffles and shared DataFrames are not recomputed.

## Description

Add explicit `broadcast()` hints in all Gold build tasks for dimension table joins (clinical_patients: 5.7K rows, reference_payers: 10 rows). Add `.cache()` calls for clinical_patients and clinical_encounters which are shared across all 3 Gold tasks. Verify no shuffle joins occur for dimension lookups in Spark execution plans. Verify broadcast threshold set to 50 MB.

## Acceptance Criteria

- [ ] Broadcast hints applied for clinical_patients and reference_payers in Gold tasks [LLD §6.2]
- [ ] clinical_patients and clinical_encounters cached across Gold builds [LLD §6.4]
- [ ] Spark execution plans show BroadcastHashJoin for dimension lookups [LLD §6.2]
- [ ] No shuffle joins for dimension-to-fact operations in Gold [LLD §6.2]
- [ ] `spark.sql.autoBroadcastJoinThreshold` set to 50 MB [LLD §6.2]

## Technical Notes

- **Upstream references**: LLD SS6.2 (Join Strategy), SS6.4 (Caching Strategy)
- **Implementation hints**: Filter `is_current=TRUE` on SCD2 dimensions before broadcast to keep payload at natural key count. `.cache()` returns immediately -- actual caching happens on first action. Unpersist after all Gold tasks complete.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS6.2, SS6.4 |
| DMS | SS5 (dimension table sizes) |
| STM | -- |
| DQS | -- |
