# STORY-02-005: Wire Factory Into DAG

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 3 |
| **Dependencies** | STORY-02-004, STORY-01-007 |
| **Status** | To Do |

## User Story

As a data engineer, I want the ingestion factory wired into the Airflow DAG so that the `bronze_ingestion` TaskGroup with 13 parallel tasks appears in the Airflow UI.

## Description

Update `dags/patient360_hourly_v1.py` to import the ingestion factory and call `create_bronze_taskgroup()` to generate the `bronze_ingestion` TaskGroup. Set the TaskGroup as the first step in the DAG, with `reconciliation_bronze` as its downstream dependency. Verify the DAG parses correctly in Airflow and shows 13 tasks inside the `bronze_ingestion` TaskGroup in the Airflow UI Graph view.

## Acceptance Criteria

- [ ] DAG imports and calls `create_bronze_taskgroup(config_dir, dag)` [LLD §4.2]
- [ ] `bronze_ingestion` TaskGroup visible in Airflow UI with 13 child tasks [LLD §4.2]
- [ ] All 13 tasks display correct task IDs (e.g., `bronze_ingestion.ingest_patients`) [LLD §4.2]
- [ ] TaskGroup has downstream dependency to `reconciliation_bronze` [LLD §4.3]
- [ ] DAG parses without import errors in Airflow scheduler [LLD §4.1]

## Technical Notes

- **Upstream references**: LLD SS4.2 (Task Inventory), LLD SS4.3 (DAG Dependency Diagram)
- **Implementation hints**: Add `from src.pipelines.bronze.ingestion_factory import create_bronze_taskgroup` at the top of the DAG file. Call within the DAG context manager.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS4.1, SS4.2, SS4.3 |
| DMS | -- |
| STM | -- |
| DQS | -- |
