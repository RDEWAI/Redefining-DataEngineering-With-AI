# STORY-01-003: Implement shared SCD2, derived_fields, and code_systems utilities

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 2 |
| **Dependencies** | STORY-01-002 |
| **Status** | In Progress |

<!--
  Story Type vocabulary (required):
    - build                    → primary construction work
    - performance-optimization → layer-scoped perf tuning (LLD §6); runs BEFORE integration-test
    - integration-test         → triggers layer DAG on local Airflow against Unity Catalog OSS local; validates landed data in UC local
    - deploy-validation        → layer-scoped DDL/DAG/config deploy smoke (optional; only when LLD prescribes it)
    - observability            → layer-scoped lineage/metrics/dashboard wiring
    - release                  → cross-layer promotion/rollback (trailing epic only)
    - hardening                → cross-layer security/docs/maintenance (trailing epic only)
    - runtime-bootstrap        → JDK/Docker/UC catalog/source-data prerequisites (≥1 per backlog, typically EPIC-01)
-->


## User Story

As a data engineer, I want have a generic SCD2 merge function and reusable derived-field/code-system helpers so that all Silver dimension transforms reuse one tested SCD2 implementation.

## Description

Implement `src/patient_360/utils/scd2.py` (`apply_scd2(df, natural_keys, hash_columns, effective_date)` using SHA-256 hash comparison + Delta MERGE INTO per DMS §6 / LLD §5.2), `derived_fields.py` (DRD §5.2 derived fields like `age_at_visit`, `bmi_category`), and `code_systems.py` (HL7 / SNOMED / LOINC mapping per STM Tab:Code Systems). Each module has unit tests with synthetic DataFrames.

## Acceptance Criteria


- [x] `scd2.py::apply_scd2` performs SHA-256 hash-based MERGE INTO closing existing row and inserting new version [LLD §5.2, DMS §6]

- [x] `derived_fields.py` implements `age_at_visit`, `bmi_category`, and other DRD §5.2 fields [DRD §5.2]

- [x] `code_systems.py` exposes lookup helpers for HL7, SNOMED, LOINC code mappings per STM Tab:Code Systems [STM Tab:Code Systems]

- [x] Unit tests at `tests/utils/test_scd2_unit.py` cover insert/match/no-change cases [LLD §2.4]


## Technical Notes

- **Upstream references**: DMS §6, LLD §5.2, DRD §5.2, STM Tab:Code Systems
- **Implementation hints**: SCD2 MERGE pattern: matched-with-changed-hash closes existing (`is_current=False`, `effective_to=current_date-1`) then inserts new row; matched-with-same-hash is no-op.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DMS | §6 SCD2 |

| LLD | §5.2 Silver Tasks |

| STM | Tab:Code Systems |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | scd2 merge edge cases (insert/update/no-change) | pytest patient_360/tests/utils/test_scd2_unit.py |

| Unit | derived fields + code system lookups | pytest patient_360/tests/utils/test_derived_fields_unit.py patient_360/tests/utils/test_code_systems_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/utils/scd2.py"
  - grep: {file: "patient_360/src/patient_360/utils/scd2.py", pattern: "MERGE INTO"}
AC2:
  - file_exists: "patient_360/src/patient_360/utils/derived_fields.py"
AC3:
  - file_exists: "patient_360/src/patient_360/utils/code_systems.py"
AC4:
  - pytest: {node: "patient_360/tests/utils/test_scd2_unit.py"}
```


## How to Test (User)

### Prerequisites


- STORY-01-002 done


### Steps


1. `cd patient_360 && uv run pytest tests/utils/test_scd2_unit.py -v`


### Expected outcome


- All SCD2 tests pass (insert, match-with-change, match-no-change scenarios)


## Documentation Updates


- [x] N/A — internal-only utility modules, not user-facing

