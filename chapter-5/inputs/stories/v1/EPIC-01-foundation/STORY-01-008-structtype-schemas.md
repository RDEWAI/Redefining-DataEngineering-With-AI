# STORY-01-008: Define StructType Schemas for All 13 Bronze Tables

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 2 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want StructType schema definitions for all 13 source tables so that Bronze ingestion enforces schemas without relying on inference.

## Description

Implement `src/config/schemas.py` containing PySpark `StructType` schema definitions for all 13 Synthea source tables: patients, encounters, conditions, medications, observations, allergies, immunizations, procedures, claims, careplans, organizations, providers, and payers. Each schema must match the column names, data types, and nullability defined in DMS Section 2 (Source Layer). Schemas must be accessible by table name (e.g., `SCHEMAS["patients"]`) for use by the ingestion runner. Include metadata columns (`_ingested_at`, `_source_file`, `_pipeline_run_id`) that are added during Bronze ingestion.

## Acceptance Criteria

- [ ] `schemas.py` defines StructType for all 13 source tables [DMS §2]
- [ ] Column names match DMS SS2 source table definitions exactly [DMS §2]
- [ ] Data types match DMS SS2 specifications (VARCHAR, DATE, NUMERIC, etc.) [DMS §2]
- [ ] Nullability constraints match DMS SS2 for each column [DMS §2]
- [ ] Metadata columns included: `_ingested_at` (TIMESTAMP), `_source_file` (STRING), `_pipeline_run_id` (STRING) [LLD §5.1]
- [ ] Schemas accessible via `SCHEMAS["table_name"]` dictionary [LLD §2.3]
- [ ] Unit tests verify schema column count, names, and types for each of 13 tables [LLD §2.4]

## Technical Notes

- **Upstream references**: DMS SS2 (Source Layer table definitions), LLD SS2.1 (schemas.py location), LLD SS5.1 (metadata columns)
- **Implementation hints**: Use `StructType([StructField(...)])` syntax. Map DMS data types to PySpark types: VARCHAR -> StringType, DATE -> DateType, NUMERIC(p,s) -> DecimalType(p,s), INTEGER -> IntegerType, TIMESTAMP -> TimestampType. The patients table has 12 columns per DMS SS4.2.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.1, SS2.3, SS5.1 |
| DMS | SS2 (all 13 source table schemas) |
| STM | Tab:Source-to-Bronze (column mappings) |
| DQS | -- |
