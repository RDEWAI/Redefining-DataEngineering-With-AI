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

Create 13 YAML configuration files in `src/config/tables/`, one per source table. Each YAML must define: source table name, schema_ref (pointing to the StructType in schemas.py), output path pattern, empty_input_behavior (fail or write_empty), dq_rules_table name for convention-based rule discovery, action_if_failed (fail or drop), timeout, and retries. Critical tables (patients, encounters, allergies, organizations, providers, payers) must override empty_input_behavior to `fail` and action_if_failed to `fail`. All others use defaults (`write_empty` and `drop`).

## Acceptance Criteria

- [ ] 13 YAML files exist in `src/config/tables/`: one per source table [LLD §2.3]
- [ ] Each YAML defines source, schema_ref, output_path, empty_input_behavior, dq_rules_table, action_if_failed [LLD §5.1]
- [ ] Critical tables (patients, encounters, allergies, organizations, providers, payers) set empty_input_behavior: fail and action_if_failed: fail [LLD §5.1, DRD SS1.3]
- [ ] Non-critical tables set empty_input_behavior: write_empty and action_if_failed: drop [LLD §5.1]
- [ ] Output paths follow pattern `warehouse/{env}/bronze/synthea_{table}/ds={ds}/` [LLD §3.2]
- [ ] All 13 YAMLs parse without error through the config loader [LLD §7]

## Technical Notes

- **Upstream references**: LLD SS2.3 (Module Interface Contracts), LLD SS5.1 (Bronze Tasks), DAG definition YAML (bronze_table_configs)
- **Implementation hints**: Reference the `dag-definition.yaml` bronze_table_configs section for exact per-table settings. The `dq_rules_table` field value must match the table name convention used in `bronze_rules.yaml` for SE rule discovery.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.3, SS5.1 (all 13 Bronze task configs) |
| DMS | SS2 (source table names) |
| STM | Tab:Source-to-Bronze |
| DQS | SS2 (Bronze rule references per table) |
