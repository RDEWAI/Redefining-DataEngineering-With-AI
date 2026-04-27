# STORY-02-003: Generate 13 per-table Bronze YAML configs

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 2 |
| **Dependencies** | STORY-02-001 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want one ingestion config YAML per Bronze source table so that the factory generates 13 ingestion tasks driven by data, not code.

## Description

Author 13 YAML files under `patient_360/airflow/configs/` — one per Bronze source table (`patients`, `encounters`, `conditions`, `medications`, `observations`, `allergies`, `immunizations`, `procedures`, `claims`, `careplans`, `organizations`, `providers`, `payers`). Each file declares `source`, `target`, `contract`, `dq_rules`, `empty_input_behavior`, `se_action_if_failed`. Critical tables (`patients`, `encounters`, `allergies`, `organizations`, `providers`, `payers`) override `empty_input_behavior: fail` per LLD §5.1.

## Acceptance Criteria

- [ ] 13 YAML files exist in `patient_360/airflow/configs/*.yml` (one per Bronze table) [LLD §4.2, Decision 7]
- [ ] 6 critical tables (`patients`, `encounters`, `allergies`, `organizations`, `providers`, `payers`) declare `empty_input_behavior: fail` [LLD §5.1, Decision 11]
- [ ] Each config declares `target: unity.bronze.synthea_<table>` per Decision 15 [LLD Decision 15]
- [ ] Each config points to its `dq_rules/{table}.yml` file [LLD §5.1, Decision 10]

## Technical Notes

- **Upstream references**: LLD §4.2 (task inventory), §5.1 (per-table mapping with empty-input override flagged), Decision 7 (one YAML per table), Decision 10 (DQ convention discovery), Decision 11 (empty-input default + override), Decision 15 (UC saveAsTable target)
- **Implementation hints**: Use a small Jinja template + a Python script driven by the LLD §5.1 table to generate the 13 files in one pass.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.2, §5.1, Decision 7, Decision 10, Decision 11, Decision 15 |
| DMS | §3 Bronze schemas (13 tables) |
| STM | Source-to-Bronze (identical for all 13) |
| DQS | §2 row_dq, agg_dq |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Contract | All 13 YAMLs parse and conform to schema | `pytest patient_360/tests/bronze/test_configs_schema.py` |
| Contract | 6 critical tables have `empty_input_behavior: fail` | `pytest patient_360/tests/bronze/test_critical_empty_input.py` |

## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/airflow/configs/*.yml", equals: 13}
AC2:
  - grep_count: {glob: "patient_360/airflow/configs/*.yml", pattern: 'empty_input_behavior:\s*fail', equals: 6}
AC3:
  - grep_count: {glob: "patient_360/airflow/configs/*.yml", pattern: 'unity.bronze.synthea_', equals: 13}
AC4:
  - grep_count: {glob: "patient_360/airflow/configs/*.yml", pattern: 'dq_rules/', equals: 13}
```

## How to Test (User)

### Prerequisites

- STORY-02-001 complete

### Steps

1. `ls patient_360/airflow/configs/*.yml | wc -l`
2. `cd patient_360 && uv run pytest tests/bronze/test_configs_schema.py -v`
3. `grep -l "empty_input_behavior: fail" patient_360/airflow/configs/*.yml | wc -l`

### Expected outcome

- Step 1: 13
- Step 2: all tests pass
- Step 3: 6 (patients, encounters, allergies, organizations, providers, payers)

## Documentation Updates

- [ ] Update `patient_360/airflow/configs/README.md` § "Per-table config schema" describing each YAML key
