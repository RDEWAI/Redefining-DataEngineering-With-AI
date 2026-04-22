# STORY-02-010: Integration Test for Bronze Pipeline

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 4 |
| **Dependencies** | STORY-02-007, STORY-02-009 |
| **Status** | To Do |

## User Story

As a data engineer, I want an end-to-end integration test that validates the full Bronze pipeline path so that we confirm DuckDB source to Bronze Delta tables works correctly with inline SE validation and reconciliation.

## Description

Create `tests/bronze/test_validate_ingestion.py` (integration) that exercises the full Bronze ingestion path: DuckDB source read -> ingestion_runner -> inline SE validation -> Delta write -> reconciliation_bronze. The test must use a real SparkSession with Unity Catalog OSS (local) for Delta table registration. Test with a subset of source data (at least patients, encounters, and allergies tables to cover both critical and non-critical paths). Verify Delta tables are created with correct schemas, row counts match source, metadata columns present (`ds`, `_ingested_at`, `_source_batch_id`), and reconciliation_bronze passes.

## Acceptance Criteria

- [ ] Integration test at `tests/bronze/test_validate_ingestion.py` runs end-to-end: DuckDB source -> Bronze Delta via ingestion framework [LLD §2.4]
- [ ] Inline SE validation executes during ingestion (row_dq + agg_dq from per-table `dq_rules/{table}.yml`) [LLD §5.4]
- [ ] Delta tables created with correct StructType schemas [DMS §4]
- [ ] Row counts in Delta match source DuckDB row counts [DQS §4]
- [ ] Metadata columns (`ds`, `_ingested_at`, `_source_batch_id`) present and populated [LLD §2.3]
- [ ] Reconciliation_bronze passes for test data [LLD §5.5]
- [ ] Test uses real SparkSession with Unity Catalog OSS [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD §2.4 (Testing Strategy), LLD §5.1, §5.4, §5.5
- **Developer plugin**: Use `developer-plugin:create-ingestion STORY-02-010` (story mode) to generate `tests/bronze/test_validate_ingestion.py`.
- **Implementation hints**: Use pytest with `@pytest.mark.integration` marker. Set up test DuckDB with sample Synthea data in fixtures. Clean up Delta tables after test. Use a temporary warehouse path for test isolation.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.4, SS5.1, SS5.4, SS5.5 |
| DMS | SS2 (source), SS4 (Bronze schemas) |
| STM | Tab:Source-to-Bronze |
| DQS | SS2 (Bronze rules), SS4 (reconciliation) |
