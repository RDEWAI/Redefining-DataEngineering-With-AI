# STORY-04-012: Local integration test: trigger Silver fact tasks against Unity Catalog OSS

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 7 |
| **Dependencies** | STORY-04-011 |
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

As a data engineer, I want trigger the `patient360_hourly_v1` Airflow DAG and validate the 9 Silver fact tables land in Unity Catalog OSS local with reconciliation passing so that Silver fact layer reaches Done with auditable cross-table reconciliation + SE evidence.

## Description

Trigger Airflow DAG, validate 9 Silver fact tables in `unity.silver.*` (`clinical_*` + `billing_claims`), FK orphan count = 0, row count Bronze→Silver matches per DQS §4. Confirm `silver_se_stats` populated for every table; `<table>_error` tables exist (or empty) for clean runs.

## Acceptance Criteria


- [ ] Airflow DAG runs Silver fact tasks + `reconciliation_silver` to success on local Airflow [LLD §4.2]

- [ ] 9 Silver fact tables visible in Unity Catalog OSS local [LLD §3.2]

- [ ] `silver_se_stats` populated for each Silver table; FK orphans = 0 (DQS §4) [DQS §4, LLD §8.6.1]

- [ ] `reconciliation_silver` success: row counts Bronze→Silver match within DQS §4 thresholds [DQS §4]


## Technical Notes

- **Upstream references**: LLD §3.2, §4.2, §8.6.1; DQS §4
- **Implementation hints**: Same DAG-trigger pattern as Bronze; assert on `unity.silver.*`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2 Silver tasks, §5.5 |

| DQS | §4 reconciliation |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Integration | DAG silver fact run + UC tables | pytest -m integration patient_360/tests/integration/test_silver_facts_uc.py |

| Smoke | DAG parses | pytest patient_360/tests/silver/test_dag_unit.py |

| DQ | silver_se_stats + FK orphans | pytest -m integration patient_360/tests/integration/test_silver_dq_evidence.py |

| Unit | transform unit suite | pytest patient_360/tests/silver/ |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_silver_facts_uc.py::test_dag_runs", marker: "integration"}
AC2:
  - pytest: {node: "patient_360/tests/integration/test_silver_facts_uc.py::test_9_silver_facts_in_uc", marker: "integration"}
AC3:
  - pytest: {node: "patient_360/tests/integration/test_silver_dq_evidence.py::test_silver_se_stats_populated", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/test_silver_dq_evidence.py::test_silver_reconciliation_success", marker: "integration"}
```


## How to Test (User)

### Prerequisites


- STORY-04-011 done


### Steps


1. `cd patient_360 && docker compose exec airflow airflow dags trigger patient360_hourly_v1`

2. `uv run pytest -m integration tests/integration/test_silver_facts_uc.py tests/integration/test_silver_dq_evidence.py -v`


### Expected outcome


- DAG runs Silver fact tasks to success; tests pass; reconciliation succeeds


## Documentation Updates


- [ ] Update patient_360/README.md § "Local integration testing" with the Silver fact trigger flow

- [ ] Update patient_360/docs/runbooks/silver-integration-test.md

