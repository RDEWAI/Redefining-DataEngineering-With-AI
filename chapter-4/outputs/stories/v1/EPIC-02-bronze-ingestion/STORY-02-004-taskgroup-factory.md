# STORY-02-004: Implement TaskGroup Factory

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 3 |
| **Dependencies** | STORY-02-003 |
| **Status** | To Do |

## User Story

As a data engineer, I want a TaskGroup factory that scans per-table YAML configs and creates one Airflow task per table so that adding new source tables requires only a new YAML file.

## Description

Implement `src/pipelines/bronze/ingestion_factory.py` with a `create_bronze_taskgroup(config_dir, dag)` function. The factory scans all `*.yaml` files in the config directory, creates one SparkSubmitWrapper task per file, and groups them into an Airflow TaskGroup named `bronze_ingestion`. All 13 tasks run in parallel within the TaskGroup. Task IDs follow the pattern `bronze_ingestion.ingest_{table_name}`. The factory must be callable at DAG parse time and must not execute any Spark jobs during parsing.

## Acceptance Criteria

- [ ] `ingestion_factory.py` exports `create_bronze_taskgroup(config_dir, dag)` function [LLD §2.3]
- [ ] Factory scans `src/config/tables/*.yaml` and creates one task per file [LLD §4.2]
- [ ] TaskGroup ID is `bronze_ingestion` [LLD §4.2]
- [ ] Task IDs follow pattern `bronze_ingestion.ingest_{table_name}` [LLD §4.2]
- [ ] All 13 tasks created (one per source table) and run in parallel [LLD §6.3]
- [ ] No Spark jobs executed during DAG parse time [LLD §4.1]

## Technical Notes

- **Upstream references**: LLD SS2.3 (ingestion_factory contract), LLD SS4.2 (Task Inventory), dag-definition.yaml (ingestion_framework section)
- **Implementation hints**: Use `airflow.utils.task_group.TaskGroup`. Extract table name from YAML filename (strip `.yaml` extension). The factory pattern ensures adding table 14 requires only a new YAML file in `config/tables/`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.3, SS4.2, SS6.3 |
| DMS | -- |
| STM | -- |
| DQS | -- |
