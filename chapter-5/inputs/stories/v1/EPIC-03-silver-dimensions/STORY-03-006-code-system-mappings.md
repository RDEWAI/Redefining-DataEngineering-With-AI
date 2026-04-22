# STORY-03-006: Implement Code System Mappings

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions -- SCD Type 2 |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 5 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want code system mapping functions for HL7, SNOMED, and RxNorm codes so that Silver transforms produce standardized clinical terminology.

## Description

Implement `src/transforms/code_systems.py` with mapping functions for: (1) HL7 gender codes (administrative gender to display values), (2) SNOMED encounter class codes (encounter type classification), (3) condition clinical status mapping. These mappings are defined in the STM Code Systems tab and are used by multiple Silver transforms. Each mapping should be implemented as a lookup dictionary or Spark UDF that can be applied to DataFrames.

## Acceptance Criteria

- [ ] `code_systems.py` implements HL7 gender code mapping [STM Tab:Code Systems]
- [ ] SNOMED encounter class mapping implemented [STM Tab:Code Systems]
- [ ] Condition clinical status mapping implemented [STM Tab:Code Systems]
- [ ] Each mapping is usable as a Spark UDF or lookup function [LLD §2.2]
- [ ] Unit tests verify correct mapping for all code values including unknown/null handling [LLD §2.4]

## Technical Notes

- **Upstream references**: STM Tab:Code Systems, LLD SS2.1 (transforms directory)
- **Implementation hints**: Use `pyspark.sql.functions.when/otherwise` chains or `create_map` for small lookups. For larger code systems, consider broadcast variables. Unknown codes should map to a default "Unknown" value rather than null.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.1 (transforms directory) |
| DMS | SS5 (Silver schemas with coded fields) |
| STM | Tab:Code Systems (all code mappings) |
| DQS | -- |
