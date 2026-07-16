# STORY-05-002: Implement build_patient_clinical_history_gold

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Tables |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 8 |
| **Dependencies** | STORY-05-001 |
| **Status** | To Do |

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

As a data engineer, I want build the `patient_clinical_history` Gold consumer table joining current-version Silver dimensions to facts so that the patient_clinical_history consumer group has a denormalized table that meets the < 2s p90 query SLA.

## Description

Implement `src/patient_360/gold/build_clinical_history.py` (or `build_patient_summary.py`) per LLD §5.3. Reads current-version `unity.silver.clinical_patients` (`is_current=TRUE`) via `spark.read.table(...)`, joins to relevant Silver facts, denormalizes via ARRAY<STRUCT> (LLD §5.3 / NFR-1), then full-overwrite `insertInto`s the `ddl/migrations/*.sql`-pre-created `unity.gold.patient_clinical_history` UC table — `df.write.mode('overwrite').insertInto("unity.gold.patient_clinical_history")` (Decision 12/15 re-adopted 2026-06-18; never `saveAsTable`/path-based `.save`). Inline SE via `dq_rules/patient_clinical_history.yml`. Empty-input: `fail` (LLD §5.3 — consumer table must have data).

## Acceptance Criteria


- [ ] `build_patient_clinical_history_gold` reads current-version SCD2 dims (`is_current=TRUE`) [LLD §5.3, §6.2]

- [ ] Output written full-overwrite via `insertInto("unity.gold.patient_clinical_history")` (pre-created UC table); no `saveAsTable`/path-based `.save` (Decision 12/15) [LLD §3.3]

- [ ] Inline SE invoked from `dq_rules/patient_clinical_history.yml` [LLD §5.3, §5.4; DQS §2 Gold]

- [ ] Empty-input behavior: `fail` [LLD §5.3]

- [ ] Unit tests cover join correctness + denormalization shape [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §5.3, §5.4, §6.2; DMS §4; STM Tab:Silver-to-Gold; DQS §2 Gold
- **Implementation hints**: Use `F.collect_list(F.struct(...))` to build ARRAY<STRUCT> denorms.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DMS | §4 Gold schema for patient_clinical_history |

| LLD | §5.3 build_patient_clinical_history_gold |

| STM | Tab:Silver-to-Gold (patient_clinical_history) |

| DQS | §2 Gold rules for patient_clinical_history |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | build_patient_clinical_history join + denorm | pytest patient_360/tests/gold/test_build_patient_clinical_history_unit.py |



## Verification

```yaml
AC1:
  - grep: {glob: "patient_360/src/patient_360/gold/build_*.py", pattern: "is_current"}
AC2:
  - grep: {glob: "patient_360/src/patient_360/gold/build_*.py", pattern: "insertInto.*unity\\.gold\\.patient_clinical_history|unity\\.gold\\.patient_clinical_history"}
  - forbidden_grep: {glob: "patient_360/src/patient_360/gold/build_*.py", pattern: "saveAsTable|\\.save\\(\\s*f?['\"].*warehouse", reason: "Gold insertInto pre-created unity.gold.<table>; no saveAsTable/path-based .save per LLD §13 Decision 12/15 (re-adopted 2026-06-18)"}
AC3:
  - grep: {glob: "patient_360/src/patient_360/gold/build_*.py", pattern: "se_runner|run_dq"}
AC4:
  - grep: {glob: "patient_360/src/patient_360/gold/build_*.py", pattern: "fail|empty_input"}
AC5:
  - pytest: {node: "patient_360/tests/gold/test_build_patient_clinical_history_unit.py"}
```


## How to Test (User)

### Prerequisites


- Dependencies satisfied


### Steps


1. `cd patient_360 && uv run pytest tests/gold/test_build_patient_clinical_history_unit.py -v`


### Expected outcome


- Unit tests pass


## Documentation Updates


- [ ] N/A — internal Gold builder module

