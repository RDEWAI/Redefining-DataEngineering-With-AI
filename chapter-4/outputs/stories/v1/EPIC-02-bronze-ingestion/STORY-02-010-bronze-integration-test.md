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

Create `tests/integration/test_bronze_pipeline.py` that exercises the full Bronze ingestion path: DuckDB source read -> ingestion_runner -> inline SE validation -> Delta write -> reconciliation_bronze. The test must use a real SparkSession with Unity Catalog OSS (local) for Delta table registration. Test with a subset of source data (at least patients, encounters, and allergies tables to cover both critical and non-critical paths). Verify Delta tables are created with correct schemas, row counts match source, metadata columns present, and reconciliation_bronze passes.

## Acceptance Criteria

- [ ] Integration test runs end-to-end: DuckDB source -> Bronze Delta via ingestion framework [LLD §2.4]
- [ ] Inline SE validation executes during ingestion (row_dq + agg_dq) [LLD §5.4]
- [ ] Delta tables created with correct StructType schemas [DMS §4]
- [ ] Row counts in Delta match source DuckDB row counts [DQS §4]
- [ ] Metadata columns (_ingested_at, _source_file, _pipeline_run_id) present and populated [LLD §5.1]
- [ ] Reconciliation_bronze passes for test data [LLD §5.5]
- [ ] Test uses real SparkSession with Unity Catalog OSS [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD SS2.4 (Testing Strategy), LLD SS5.1, SS5.4, SS5.5
- **Implementation hints**: Use pytest with `@pytest.mark.integration` marker. Set up test DuckDB with sample Synthea data in fixtures. Clean up Delta tables after test. Consider using a temporary warehouse path for test isolation.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.4, SS5.1, SS5.4, SS5.5 |
| DMS | SS2 (source), SS4 (Bronze schemas) |
| STM | Tab:Source-to-Bronze |
| DQS | SS2 (Bronze rules), SS4 (reconciliation) |
