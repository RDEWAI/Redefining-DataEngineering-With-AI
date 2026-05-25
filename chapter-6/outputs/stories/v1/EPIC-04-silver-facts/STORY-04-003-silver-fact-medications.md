# STORY-04-003: Implement transform_medications_silver (fact)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 7 |
| **Dependencies** | STORY-04-001 |
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

As a data engineer, I want transform `unity.bronze.synthea_medications` into `clinical_medications` (or `billing_claims`) Silver fact table so that Gold tables can join the medications fact to current-version dimensions.

## Description

Implement `src/patient_360/silver/transform_medications.py` per LLD §5.2. Reads `unity.bronze.synthea_medications` (UC-managed), enriches via FK joins to Silver dims (`is_current=TRUE`), applies STM Tab:Bronze-to-Silver transforms, writes to `warehouse/{env}/silver/clinical/clinical_medications/` with `replaceWhere ds = '{ds}'` (LLD §3.3). Inline SE per `dq_rules/clinical_medications.yml`. Empty-input behavior: `fail` for `encounters` and `allergies` (LLD §5.2), `write_empty` otherwise.

## Acceptance Criteria


- [ ] `transform_medications.py` reads `unity.bronze.synthea_medications` (UC-managed) [LLD §5.2]

- [ ] FK join uses `is_current = TRUE` filter on dim before broadcast (LLD §6.2) [LLD §6.2]

- [ ] Output written with `replaceWhere ds = '{ds}'` (LLD §4.5 idempotency) [LLD §3.3, §4.5]

- [ ] Inline SE invoked from `dq_rules/clinical_medications.yml` [LLD §5.2, §5.4; DQS §2]

- [ ] Unit tests cover happy path, FK orphan rejection, and empty-input behavior [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §5.2, §5.4, §6.2; DMS §3; STM Tab:Bronze-to-Silver; DQS §2
- **Implementation hints**: Use `F.broadcast(dim_df.filter(F.col('is_current')))` for dim joins. Schema target from DMS §3.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DMS | §3 Silver schema for medications |

| LLD | §5.2 transform_medications_silver |

| STM | Tab:Bronze-to-Silver (medications) |

| DQS | §2 row_dq + agg_dq for medications |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | transform_medications happy path + edge cases | pytest patient_360/tests/silver/test_transform_medications_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_medications.py"
  - grep: {file: "patient_360/src/patient_360/silver/transform_medications.py", pattern: "unity.bronze.synthea_medications"}
AC2:
  - grep: {file: "patient_360/src/patient_360/silver/transform_medications.py", pattern: "is_current"}
AC3:
  - grep: {file: "patient_360/src/patient_360/silver/transform_medications.py", pattern: "replaceWhere"}
AC4:
  - grep: {file: "patient_360/src/patient_360/silver/transform_medications.py", pattern: "se_runner|run_dq"}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_transform_medications_unit.py"}
```


## How to Test (User)

### Prerequisites


- Dependencies satisfied


### Steps


1. `cd patient_360 && uv run pytest tests/silver/test_transform_medications_unit.py -v`


### Expected outcome


- All unit tests pass


## Documentation Updates


- [ ] N/A — internal silver fact transform module

