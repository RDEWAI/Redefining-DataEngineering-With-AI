# STORY-02-009: Unit Tests for Bronze Ingestion Framework

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 4 |
| **Dependencies** | STORY-02-002, STORY-02-004, STORY-02-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want comprehensive unit tests for the ingestion framework so that config loading, schema enforcement, empty-input handling, inline SE behavior, and DQ convention discovery are verified before integration testing.

## Description

Write unit tests covering: (1) `tests/bronze/test_ingestion_runner.py` -- config loading from YAML, schema enforcement (pass and fail cases), metadata column addition (`ds`, `_ingested_at`, `_source_batch_id`), empty-input behavior (fail mode raises error, write_empty mode writes empty partition), inline SE action_if_failed behavior (fail raises, drop quarantines, ignore logs). (2) `tests/bronze/test_per_table_configs.py` -- factory creates correct number of tasks, task IDs follow naming convention, TaskGroup name is correct, all 13 `airflow/configs/*.yml` files parse without error. (3) Assert every table in `airflow/configs/` has at least one matching rule in `dq_rules/{table}.yml`. Target >= 90% line coverage across all Bronze modules.

## Acceptance Criteria

- [ ] `tests/bronze/test_ingestion_runner.py` covers config loading, schema enforcement, metadata columns (`ds`, `_ingested_at`, `_source_batch_id`), empty-input behavior [LLD §2.4]
- [ ] Inline SE action_if_failed tested: fail raises exception, drop quarantines rows to `warehouse/{env}/quarantine/bronze/{table}/`, ignore logs only [LLD §2.4, §5.4]
- [ ] `tests/bronze/test_per_table_configs.py` verifies all 13 `airflow/configs/*.yml` parse and factory creates 13 tasks with correct IDs [LLD §2.4]
- [ ] Test asserts every table config has >= 1 matching rule in `dq_rules/{table}.yml` (not `bronze_rules.yaml`) [LLD §2.4]
- [ ] Test coverage >= 90% for ingestion_runner.py, ingestion_factory.py, se_runner.py [LLD §2.4]
- [ ] All tests pass with `make test` (`uv run pytest tests/bronze/ -v`) [development-standards.md §5]

## Technical Notes

- **Upstream references**: LLD §2.4 (Testing Strategy), LLD §5.1 (Bronze task behavior), LLD §5.4 (Inline SE)
- **Developer plugin**: Use `developer-plugin:create-ingestion STORY-02-009` (story mode) to generate `tests/bronze/test_ingestion_runner.py` and `tests/bronze/test_per_table_configs.py`.
- **Implementation hints**: Use pytest fixtures for SparkSession (local mode). Mock DuckDB source reads. Use sample DataFrames with known good and bad data to test DQ rule execution. Test naming: `test_bronze_{operation}_{scenario}` per LLD §2.4 convention.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.4, SS5.1, SS5.4 |
| DMS | SS2 (source schemas for test fixtures), SS4 (Bronze schemas) |
| STM | Tab:Source-to-Bronze |
| DQS | SS2 (Bronze rules for assertion) |
