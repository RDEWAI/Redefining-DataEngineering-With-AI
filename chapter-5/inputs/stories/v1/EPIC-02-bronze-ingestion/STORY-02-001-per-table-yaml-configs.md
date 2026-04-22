# STORY-02-001: Create Per-Table YAML Ingestion Configs

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 3 |
| **Dependencies** | STORY-01-002, STORY-01-008 |
| **Status** | To Do |

## User Story

As a data engineer, I want per-table YAML configuration files for all 13 source tables so that the ingestion framework can drive Bronze loading declaratively.

## Description

Create 13 YAML configuration files in `airflow/configs/`, one per source table. Each YAML must define: source table name (fully qualified as `synthea.{table}`), schema_ref (pointing to `contracts/{table}.yml`), output path pattern, empty_input_behavior (fail or write_empty), dq_rules_table name for convention-based rule discovery (matches `dq_rules/{table}.yml` by table name), se_action_if_failed (fail or drop), quarantine_path, timeout, and retries. Critical tables (patients, encounters, allergies, organizations, providers, payers) must override empty_input_behavior to `fail` and se_action_if_failed to `fail`. All others use defaults (`write_empty` and `drop`).

## Acceptance Criteria

- [ ] 13 YAML files exist in `airflow/configs/`: one per source table [LLD §2.3]
- [ ] Each YAML defines `source.table` as fully qualified `synthea.{table}` (not bare table name) [LLD §5.1]
- [ ] Each YAML defines source, schema_ref, output_path, empty_input_behavior, dq_rules_table, se_action_if_failed, quarantine_path [LLD §5.1]
- [ ] Metadata columns declared: `ds`, `_ingested_at`, `_source_batch_id` [LLD §2.3]
- [ ] Critical tables (patients, encounters, allergies, organizations, providers, payers) set empty_input_behavior: fail and se_action_if_failed: fail [LLD §5.1, DRD §1.3]
- [ ] Non-critical tables set empty_input_behavior: write_empty and se_action_if_failed: drop [LLD §5.1]
- [ ] Output paths follow pattern `warehouse/{env}/bronze/synthea_{table}/` [LLD §3.2]
- [ ] Quarantine paths follow pattern `warehouse/{env}/quarantine/bronze/{table}/` [LLD §7.1]
- [ ] All 13 YAMLs parse without error through the config loader [LLD §7]

## Technical Notes

- **Upstream references**: LLD §2.3 (Module Interface Contracts for `airflow/configs/{table}.yml`), LLD §5.1 (Bronze Tasks), LLD §7.1 (`ingestion.quarantine_path`)
- **Developer plugin**: Use `developer-plugin:create-ingestion STORY-02-001` (story mode) to generate this story's deliverables. The skill validates all 13 configs against the LLD §5.1 task table and checks `dq_rules/` sync.
- **Implementation hints**: `dq_rules_table` field must match the table name convention for SE rule discovery (`dq_rules/{table}.yml`). Use `synthea.{table}` as the fully qualified source table name (schema-qualified) for DuckDB reads.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3, §5.1 (all 13 Bronze task configs), §7.1 (quarantine_path) |
| DMS | §2 (source table names) |
| STM | Tab:Source-to-Bronze |
| DQS | §2 (Bronze rule references per table) |
