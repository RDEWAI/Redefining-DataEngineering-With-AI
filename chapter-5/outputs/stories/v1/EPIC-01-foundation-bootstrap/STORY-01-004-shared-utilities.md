# STORY-01-004: Implement scd2 / derived_fields / delta_helpers utilities

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Runtime Bootstrap |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 1 |
| **Dependencies** | STORY-01-002 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want shared SCD2, derived-fields, code-systems, delta-helper, and metrics utilities so that Silver and Gold tasks reuse a single implementation of cross-cutting logic.

## Description

Implement the cross-layer utility modules listed in LLD §2.1: `scd2.py` (SHA-256 hash + MERGE INTO helper for SCD Type 2), `derived_fields.py` (age, encounter_duration, etc.), `code_systems.py` (SNOMED/ICD-10 lookup helpers), `delta_helpers.py` (replaceWhere, table-existence), and `metrics.py` (OpenTelemetry emitters). Unit tests cover each helper.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/utils/scd2.py` exposes `apply_scd2(spark, target, source, key_cols, hash_cols)` [LLD §5.2 SCD2 notes, DMS §6]
- [ ] `patient_360/src/patient_360/utils/derived_fields.py` exposes derived field functions [STM Bronze-to-Silver]
- [ ] `patient_360/src/patient_360/utils/delta_helpers.py` exposes `replace_where(df, table, ds)` [LLD §4.5]
- [ ] `patient_360/src/patient_360/utils/metrics.py` exposes `emit_metric(name, value, tags)` [LLD §10.1]
- [ ] `patient_360/tests/utils/test_scd2_unit.py` exercises hash + MERGE [LLD §5.2]

## Technical Notes

- **Upstream references**: LLD §5.2 (SCD2 processing), §4.5 (idempotency), §10.1 (metrics); STM Bronze-to-Silver derived fields
- **Implementation hints**: SCD2 uses SHA-256 hash on tracked columns. `apply_scd2` should generate Delta `MERGE INTO` SQL.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3, §4.5, §5.2, §10.1 |
| DMS | §6 SCD2 strategy |
| STM | Bronze-to-Silver derived fields |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | SCD2 hash + MERGE generates correct SQL | `pytest patient_360/tests/utils/test_scd2_unit.py` |
| Unit | Derived fields | `pytest patient_360/tests/utils/test_derived_fields.py` |
| Unit | Delta helpers | `pytest patient_360/tests/utils/test_delta_helpers.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/utils/scd2.py"
  - grep: {file: "patient_360/src/patient_360/utils/scd2.py", pattern: 'def apply_scd2'}
AC2:
  - file_exists: "patient_360/src/patient_360/utils/derived_fields.py"
AC3:
  - file_exists: "patient_360/src/patient_360/utils/delta_helpers.py"
  - grep: {file: "patient_360/src/patient_360/utils/delta_helpers.py", pattern: 'replace_where'}
AC4:
  - file_exists: "patient_360/src/patient_360/utils/metrics.py"
AC5:
  - pytest: {node: "patient_360/tests/utils/test_scd2_unit.py"}
```

## How to Test (User)

### Prerequisites

- STORY-01-002 complete
- `make dev-setup` completed

### Steps

1. `cd patient_360 && uv run pytest tests/utils/ -v`

### Expected outcome

- All utility tests pass; coverage ≥ 90% on `src/patient_360/utils/`

## Documentation Updates

- [ ] N/A — internal utility modules, not user-facing
