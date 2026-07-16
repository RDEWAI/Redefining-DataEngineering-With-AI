# STORY-05-006: Implement reconciliation_gold task (silver-vs-gold row counts + patient/allergy completeness)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Tables |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 8 |
| **Dependencies** | STORY-05-001, STORY-05-002, STORY-05-003 |
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

As a data engineer, I want build the `reconciliation_gold` task that runs after all 3 Gold builders so that we have a fail-closed gate proving Gold row counts reconcile against Silver, patient completeness = 5,767, and allergy completeness holds before the layer is declared Done.

## Description

Implement `src/patient_360/gold/reconciliation.py` — the Gold reconciliation logic per LLD §4.2 / §6.5.3 and DQS §4. It (1) reconciles `unity.gold.*` row counts against their `unity.silver.*` sources within the DQS §4 tolerance, (2) asserts `patient_summary` distinct patient completeness = 5,767 (NFR-4 / DQS §4, DQ-FLD-106), and (3) asserts allergy completeness — `has_allergy` flag consistent with the `allergies` ARRAY<STRUCT> (DQ-FLD-138 [DQS §4]). Mirror the existing Bronze reconciliation module `src/patient_360/bronze/reconciliation.py` (same `main(args)` runner contract, same fail-closed exit). Wire the `reconciliation_gold` task into `airflow/dags/patient360_hourly_v1.py` as a `SparkSubmitOperator` (LLD §4.2 — all Spark-touching tasks) downstream of the Gold builders: edge `gold_build >> reconciliation_gold`. Add the SparkSubmit entry shim `airflow/jobs/run_gold_recon.py` (mirror `airflow/jobs/run_bronze_recon.py`). Fail-closed when reconciliation cannot execute (LLD §8.6.1).

## Acceptance Criteria


- [ ] `reconciliation_gold` reconciles `unity.gold.*` row counts vs `unity.silver.*` within DQS §4 tolerance [LLD §6.5.3, DQS §4]

- [ ] `patient_summary` patient completeness asserted = 5,767 per NFR-4 / DQS §4 [LLD §4.2, DQS §4]

- [ ] Allergy completeness asserted (DQ-FLD-138 — `has_allergy` consistent with `allergies` array) [DQS §4]

- [ ] `reconciliation_gold` task wired into the Airflow DAG downstream of all Gold builders (`gold_build >> reconciliation_gold`), `SparkSubmitOperator` [LLD §4.2]

- [ ] Unit tests cover positive reconciliation, tolerance-breach fail, and completeness-fail cases [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §4.2, §6.5.3, §8.6.1; DQS §4; DQ-FLD-138 (allergy completeness); NFR-4 (5,767 patients)
- **Implementation hints**: Mirror `src/patient_360/bronze/reconciliation.py` — same `main(args)` entry contract consumed by the SparkSubmit shim `airflow/jobs/run_gold_recon.py` (mirror `run_bronze_recon.py`). Fail-closed on tolerance breach or completeness miss.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2 reconciliation_gold task, §6.5.3 reconciliation, §8.6.1 fail-closed |

| DQS | §4 reconciliation rules; DQ-FLD-138 allergy completeness |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | reconciliation_gold row-count + completeness assertions | pytest patient_360/tests/gold/test_reconciliation_unit.py |



## Verification

```yaml
AC1:
  - grep: {file: "patient_360/src/patient_360/gold/reconciliation.py", pattern: "unity.silver|unity.gold|row count|row_count"}
AC2:
  - grep: {file: "patient_360/src/patient_360/gold/reconciliation.py", pattern: "5767|5,767|patient_summary"}
AC3:
  - grep: {file: "patient_360/src/patient_360/gold/reconciliation.py", pattern: "allerg"}
AC4:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "reconciliation_gold"}
  - file_exists: {path: "patient_360/airflow/jobs/run_gold_recon.py"}
AC5:
  - pytest: {node: "patient_360/tests/gold/test_reconciliation_unit.py"}
```


## How to Test (User)

### Prerequisites


- STORY-05-001, STORY-05-002, STORY-05-003 done


### Steps


1. `cd patient_360 && uv run pytest tests/gold/test_reconciliation_unit.py -v`


### Expected outcome


- Unit tests pass (positive reconciliation, tolerance-breach fail, completeness-fail)


## Documentation Updates


- [ ] N/A — internal Gold reconciliation task

