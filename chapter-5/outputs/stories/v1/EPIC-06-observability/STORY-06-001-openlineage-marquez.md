# STORY-06-001: Wire OpenLineage Spark listener + Marquez emit_lineage task

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability & Lineage |
| **Story Type** | observability |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 9 |
| **Dependencies** | STORY-05-005 |
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

As a data engineer, I want have every Spark job emit OpenLineage events to Marquez and surface a `dq_pass_rate` run facet so that lineage and DQ pass rate are queryable from the Marquez UI for HIPAA audit (NFR-7).

## Description

Configure `spark.extraListeners=io.openlineage.spark.agent.OpenLineageSparkListener` and `spark.openlineage.transport.url=http://marquez:5001/api/v1` in pipeline config. Add `emit_lineage` Airflow task per LLD §4.2 that summarizes the run and posts the SE pass-rate facet.

## Acceptance Criteria


- [ ] OpenLineage Spark listener configured in pipeline config (all envs) [LLD §10, HLD §5.6]

- [ ] `emit_lineage` task in DAG fires after `reconciliation_gold` per LLD §4.2 [LLD §4.2]

- [ ] Marquez run facets include `dq_pass_rate` gauge per LLD §8.6.1 [LLD §8.6.1, §10.1]


## Technical Notes

- **Upstream references**: LLD §4.2, §8.6.1, §10, HLD §5.6
- **Implementation hints**: Use `openlineage-spark` jar via `spark.jars.packages`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2, §10.1 |

| HLD | §5.6 Observability stack |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Manual UI check | Marquez run lineage edges + dq_pass_rate facet | open http://localhost:5001 and inspect last run |

| Smoke | OpenLineage listener config present | grep openlineage in config |



## Verification

```yaml
AC1:
  - grep: {glob: "patient_360/_infra/cd/config/*.yaml", pattern: "openlineage"}
AC2:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "emit_lineage"}
AC3:
  - manual: "Marquez UI — visual check of dq_pass_rate facet"
```


## How to Test (User)

### Prerequisites


- STORY-05-005 done

- Marquez up


### Steps


1. `cd patient_360 && docker compose exec airflow airflow dags trigger patient360_hourly_v1`

2. Open http://localhost:5001 and inspect the run lineage and run facets


### Expected outcome


- Marquez UI shows job graph for the run

- `dq_pass_rate` facet visible on the latest run


## Documentation Updates


- [ ] N/A — internal listener config

