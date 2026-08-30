# STORY-05-005: Local integration test: trigger Gold tasks against Unity Catalog OSS local

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Tables |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 8 |
| **Dependencies** | STORY-05-004, STORY-05-006 |
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

As a data engineer, I want trigger the Airflow DAG, run all 3 Gold tasks against Unity Catalog OSS local, and validate consumer outputs so that Gold layer reaches Done with the data freshness, completeness, and SE evidence required by LLD §10.4.

## Description

Trigger Airflow DAG; assert 3 Gold tables in `unity.gold.*` (`patient_summary`, `patient_clinical_history`, `patient_billing_summary`); patient_summary row count = 5,767 (NFR-4); `reconciliation_gold` succeeds (DQS §4 + DQ-FLD-138 allergy completeness); `gold_se_stats` populated.

## Acceptance Criteria


- [ ] Airflow DAG runs Gold tasks + `reconciliation_gold` to success on local Airflow [LLD §4.2]

- [ ] 3 Gold tables visible in Unity Catalog OSS local [LLD §3.2]

- [ ] `patient_summary` row count = 5,767 (DQ-FLD-106) per NFR-4 / DQS §4 [DQS §4, LLD §10.4]

- [ ] `gold_se_stats` populated; allergy completeness assertion DQ-FLD-138 passes [DQS §2 Gold, LLD §8.6.1]

- [ ] `dq_pass_rate` for the run >= 99% per LLD §10.1 [LLD §10.1]


## Technical Notes

- **Upstream references**: LLD §3.2, §4.2, §8.6.1, §10.1, §10.4; DQS §2 Gold, §4
- **Implementation hints**: Same DAG-trigger pattern; UC OSS `/api/2.1/unity-catalog/tables`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2 Gold tasks, §10.4 SLAs |

| DQS | §2 Gold, §4 reconciliation |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Integration | Gold DAG run + UC tables + 5,767 patient row count | pytest -m integration patient_360/tests/integration/gold/test_gold_uc.py |

| DQ | gold_se_stats + allergy completeness | pytest -m integration patient_360/tests/integration/gold/test_gold_se_evidence.py |

| Smoke | Gold DAG tasks parse | pytest patient_360/tests/gold/test_dag_unit.py |

| Unit | Gold builder unit suite | pytest patient_360/tests/gold/ |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/gold/test_gold_uc.py::test_dag_runs", marker: "integration"}
AC2:
  - pytest: {node: "patient_360/tests/integration/gold/test_gold_uc.py::test_3_gold_tables_in_uc", marker: "integration"}
AC3:
  - pytest: {node: "patient_360/tests/integration/gold/test_gold_uc.py::test_patient_summary_count_5767", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/gold/test_gold_se_evidence.py::test_allergy_completeness", marker: "integration"}
AC5:
  - manual: "Grafana DQ board — visual check of dq_pass_rate gauge"
```


## How to Test (User)

### Prerequisites


- STORY-05-004, STORY-05-006 done


### Steps


1. `cd patient_360 && make ddl-apply` (pre-create UC tables) then `docker compose exec airflow airflow dags trigger patient360_hourly_v1`

2. `uv run pytest -m integration tests/integration/gold/test_gold_uc.py tests/integration/gold/test_gold_se_evidence.py -v`


### Expected outcome


- DAG run reaches success

- All integration tests pass; patient_summary count = 5,767


## Documentation Updates


- [ ] Update patient_360/README.md § "Local integration testing" with the Gold trigger flow

- [ ] Add patient_360/docs/runbooks/gold-integration-test.md

