# STORY-02-007: Implement Reconciliation Bronze Task

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 4 |
| **Dependencies** | STORY-02-005, STORY-02-006 |
| **Status** | To Do |

## User Story

As a data quality engineer, I want a reconciliation task that runs cross-table query_dq checks after all Bronze ingestion completes so that row count discrepancies, freshness issues, and completeness gaps are caught before Silver processing begins.

## Description

Implement `src/quality/reconciliation.py` with Bronze reconciliation logic and wire it into the Airflow DAG as the `reconciliation_bronze` task. The task runs after all 13 Bronze ingestion tasks complete and executes three categories of query_dq checks from DQS SS4: (1) row count reconciliation comparing source DuckDB counts against Bronze Delta counts per table, (2) data freshness validation ensuring Bronze tables were updated within the current execution window, (3) completeness assertions ensuring critical tables have non-zero rows. On CRITICAL failure, block Silver processing and alert `p360-critical`. On WARNING, log and continue.

## Acceptance Criteria

- [ ] `reconciliation.py` implements row count reconciliation (source vs Bronze per table) [DQS §4]
- [ ] Data freshness check validates Bronze tables updated within tolerance [DQS §4]
- [ ] Completeness check asserts critical tables have non-zero row counts [DQS §4]
- [ ] `reconciliation_bronze` task depends on all 13 `bronze_ingestion` tasks [LLD §4.2]
- [ ] CRITICAL failure blocks all Silver tasks downstream [LLD §5.5]
- [ ] Alert sent to `p360-critical` channel on CRITICAL failure [LLD §8.3]
- [ ] Timeout: 20 minutes, retries: 1, retry delay: 60s fixed [LLD §8.1]

## Technical Notes

- **Upstream references**: LLD SS5.5 (Reconciliation Tasks), DQS SS4 (query_dq rules), LLD SS8.3 (Alerting Thresholds)
- **Implementation hints**: Reconciliation queries run against Delta tables using Spark SQL. Row count comparison queries the source DuckDB (read-only) and the Bronze Delta table. Use the `on_critical_failure: block_silver` pattern from the DAG definition YAML.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.5, SS8.1, SS8.3 |
| DMS | SS2 (source row counts for reconciliation) |
| STM | -- |
| DQS | SS4 (query_dq reconciliation rules) |
