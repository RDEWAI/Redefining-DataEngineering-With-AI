# STORY-04-011: Implement Reconciliation Silver Task

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-02-007 |
| **Status** | To Do |

## User Story

As a data quality engineer, I want a Silver reconciliation task that runs cross-table query_dq checks after all Silver transforms complete so that FK orphans, row count discrepancies, and SCD2 version anomalies are caught before Gold processing.

## Description

Extend `src/quality/reconciliation.py` with Silver reconciliation logic and wire `reconciliation_silver` into the Airflow DAG. The task runs after all 13 Silver tasks complete and executes: (1) row count reconciliation (Bronze vs Silver per table), (2) FK orphan cross-checks (e.g., encounters reference valid patients), (3) SCD2 version count sanity (version count within expected range for dimension tables). On CRITICAL failure, block Gold processing.

## Acceptance Criteria

- [ ] Row count reconciliation: Bronze vs Silver per table [DQS §4]
- [ ] FK orphan cross-check: encounter FKs resolve to valid patients/orgs/providers [DQS §4]
- [ ] SCD2 version sanity: version count within expected range for 4 dimension tables [DQS §4]
- [ ] `reconciliation_silver` depends on all 13 Silver tasks [LLD §4.2]
- [ ] CRITICAL failure blocks all Gold tasks [LLD §5.5]
- [ ] Alert on `p360-critical` for CRITICAL failures [LLD §8.3]

## Technical Notes

- **Upstream references**: LLD SS5.5, DQS SS4, LLD SS8.3
- **Implementation hints**: Reuse the reconciliation.py module from STORY-02-007, extending with Silver-specific checks. SCD2 sanity: assert `count(DISTINCT scd2_version)` is reasonable (e.g., < 10 versions per natural key for patients).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.5, SS8.1, SS8.3 |
| DMS | SS5, SS6 |
| STM | -- |
| DQS | SS4 (Silver reconciliation rules) |
