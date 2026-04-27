# STORY-01-003: Generate per-table StructType schema contracts from DMS

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Runtime Bootstrap |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 1 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want per-table contract YAML files generated from the DMS so that ingestion and transformation modules enforce consistent StructType schemas across Bronze, Silver, and Gold layers.

## Description

Generate `patient_360/contracts/{table}.yml` for every table in the DMS — 13 Bronze + 13 Silver + 3 Gold = 29 contracts — each containing the StructType column list, types, nullability, and pointers to `ddl/liquibase/changelogs/{table}.xml` and `dq_rules/{table}.yml`. Generate matching `patient_360/contracts/dq/{table}.yml` pointer files. Contracts are the source of truth for schema enforcement at write time.

## Acceptance Criteria

- [ ] 13 Bronze contract files exist under `patient_360/contracts/synthea_*.yml` [DMS §3 Bronze, LLD §2.1]
- [ ] 13 Silver contract files exist under `patient_360/contracts/clinical_*.yml`, `reference_*.yml`, `billing_*.yml` [DMS §4 Silver, LLD §5.2]
- [ ] 3 Gold contract files exist for `patient_summary`, `patient_clinical_history`, `patient_billing_summary` [DMS §5 Gold, LLD §5.3]
- [ ] Each contract YAML declares `columns:`, `ddl_path:`, `dq_path:` keys [LLD §2.1]

## Technical Notes

- **Upstream references**: DMS §3-5 (layer schemas), LLD §2.1 (Module-to-Template mapping)
- **Implementation hints**: Iterate the DMS embedded YAML schema blocks; write one contract per table. Bronze tables are prefixed `synthea_*`; Silver tables `clinical_*`, `reference_*`, `billing_*`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.1, §5.1, §5.2, §5.3 |
| DMS | §3, §4, §5 |
| STM | Source-to-Bronze, Bronze-to-Silver, Silver-to-Gold |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | Every contract YAML parses and matches DMS schema | `pytest patient_360/tests/contracts/test_contract_parity.py` |
| Contract | All 29 contracts present | `ls patient_360/contracts/*.yml \| wc -l` |

## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/contracts/synthea_*.yml", equals: 13}
AC2:
  - file_count: {glob: "patient_360/contracts/{clinical,reference,billing}_*.yml", equals: 13}
AC3:
  - file_exists: "patient_360/contracts/patient_summary.yml"
  - file_exists: "patient_360/contracts/patient_clinical_history.yml"
  - file_exists: "patient_360/contracts/patient_billing_summary.yml"
AC4:
  - grep_count: {glob: "patient_360/contracts/*.yml", pattern: 'ddl_path:', equals: 29}
```

## How to Test (User)

### Prerequisites

- STORY-01-001 complete

### Steps

1. `ls patient_360/contracts/*.yml | wc -l`
2. `cd patient_360 && uv run pytest tests/contracts/ -v`

### Expected outcome

- Step 1 reports 29
- Step 2 all tests pass

## Documentation Updates

- [ ] Update `patient_360/contracts/README.md` § "Contract Schema" describing the YAML format
