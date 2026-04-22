# STORY-02-002: Implement Generic Ingestion Runner

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 3 |
| **Dependencies** | STORY-02-001, STORY-01-008 |
| **Status** | To Do |

## User Story

As a data engineer, I want a generic ingestion runner that reads a per-table YAML config and executes the standard Bronze ingestion pattern so that all 13 tables are loaded without writing individual ingestion modules.

## Description

Implement `src/patient_360/bronze/ingestion_runner.py` -- the core of the config-driven ingestion framework. The runner accepts a YAML config path, reads the config to determine source table (fully qualified as `synthea.{table}`), StructType schema, output path, DQ rules, and empty-input behavior. It then executes the standard pattern: (1) read source table from DuckDB, (2) add three metadata columns (`ds` string YYYY-MM-DD, `_ingested_at` TimestampType, `_source_batch_id` string `{table}:{ds}`), (3) enforce StructType schema (no inference), (4) call SE runner inline for row_dq/agg_dq validation with `action_if_failed` from config, (5) write to Delta with `replaceWhere ds = '{ds}'` for idempotency. Handle empty-input per config: if `fail`, raise error; if `write_empty`, write empty partition and succeed. In bootstrap mode (se_runner not yet available), soft-import logs `WARNING: se_runner not available` and passes data through.

## Acceptance Criteria

- [ ] `src/patient_360/bronze/ingestion_runner.py` reads per-table YAML config and extracts all required fields [LLD §2.3]
- [ ] Source data read from DuckDB using fully qualified table name `synthea.{table}` [LLD §5.1]
- [ ] Metadata columns added: `ds` (STRING, YYYY-MM-DD), `_ingested_at` (TIMESTAMP), `_source_batch_id` (STRING, `{table}:{ds}`) [LLD §2.3]
- [ ] StructType schema enforced without inference; mismatched columns raise error [LLD §2.3]
- [ ] Inline SE validation called with row_dq + agg_dq rules via se_runner.py [LLD §5.4]
- [ ] action_if_failed: fail raises exception; drop quarantines rows to `warehouse/{env}/quarantine/bronze/{table}/`; ignore logs only [LLD §5.4]
- [ ] Delta write uses `replaceWhere ds = '{ds}'` for idempotent partition overwrite [LLD §4.5]
- [ ] Empty input with behavior `fail` raises error; `write_empty` writes empty partition [LLD §2.3]
- [ ] Bootstrap soft-import: missing `se_runner` logs `WARNING: se_runner not available`; data passes through without DQ [LLD §8.5]

## Technical Notes

- **Upstream references**: LLD §2.3 (ingestion_runner contract), LLD §5.1 (Bronze task details), LLD §5.4 (Inline SE), LLD §4.5 (Idempotency), LLD §8.5 (Bootstrap mode)
- **Developer plugin**: Use `developer-plugin:create-ingestion STORY-02-002` (story mode) to generate `ingestion_runner.py`. The skill checks that STORY-02-001 configs exist first.
- **Implementation hints**: The runner is invoked by SparkSubmitOperator with `--config-path` argument. DQ rules are discovered by table name convention from `dq_rules/{table}.yml`. The SE runner (STORY-02-006) is a dependency for the inline DQ portion, but the ingestion logic (read, transform, write) can be developed first with DQ as a pluggable step.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.3, SS5.1, SS5.4, SS4.5 |
| DMS | SS2 (source schemas), SS4 (Bronze table schemas) |
| STM | Tab:Source-to-Bronze (transformation rules) |
| DQS | SS2 (Bronze DQ rules -- inline execution) |
