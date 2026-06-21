# STORY-02-007: Performance: dynamic partition overwrite pruning + shuffle.partitions + observations 8-partition tuning

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | performance-optimization |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 5 |
| **Dependencies** | STORY-02-001, STORY-02-003 |
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

As a data engineer, I want apply LLD §6.3 / §6.5 partition + shuffle tuning to Bronze writes so that `synthea_observations` (4.4M rows) writes in ~5 min and partition pruning reads only the current `ds`.

## Description

Wire `spark.sql.shuffle.partitions=8` (DEV) / 16 (STAGING) / 32 (PROD) and `spark.sql.autoBroadcastJoinThreshold=50m` per LLD §6.3 / §6.4. Set DEV Spark memory to `spark_driver_memory: 1g` and `spark_executor_memory: 1g` per LLD §6.1 + §7 (2026-05-12 pivot — was 2g/2g; reduced to avoid OOM on the 8GB Docker host shared with UC + Marquez + Postgres + Airflow). Set `synthea_observations` to 8 target partitions (LLD §6.5 partition tuning); other Bronze tables to 1-2 partitions. Verify the `mode("overwrite").insertInto(...)` write under `spark.sql.sources.partitionOverwriteMode=dynamic` replaces only the current `ds` partition (the idempotency mechanism — LLD §13 Decision 15; `replaceWhere` is NOT used because `insertInto` silently ignores it), confirmed via Spark UI / explain plan. Add a benchmark assertion that `ingest_observations` finishes within the LLD-stated 5 min on DEV.

## Acceptance Criteria


- [x] `compute.spark_shuffle_partitions` set per env (8/16/32) in `_infra/cd/config/{env}.yaml` per LLD §6.3 [LLD §6.3]

- [x] `synthea_observations` write produces ~8 output partitions per `ds` per LLD §6.5 [LLD §6.5]

- [ ] Dynamic-partition-overwrite prune verified by `EXPLAIN EXTENDED` showing only the current `ds` partition overwritten (`partitionOverwriteMode=dynamic`; no `replaceWhere`) [LLD §3.3, §4.5, §13 Decision 15]

- [ ] DEV `compute.spark_driver_memory: 1g` and `compute.spark_executor_memory: 1g` in `_infra/cd/config/dev.yaml` per LLD §6.1 + §7 (2026-05-12 pivot — was 2g/2g; downsized to fit 8GB Docker host) [LLD §6.1, §7]

- [ ] Benchmark: ingest_observations completes in < 5 min on DEV (1 executor, **1g** driver / 1g executor) per LLD §4.4 + §6.1 [LLD §4.4, §6.1]


## Technical Notes

- **Upstream references**: LLD §3.3, §4.4, §4.5, §6.3, §6.5
- **Implementation hints**: Pass `spark.sql.shuffle.partitions` from `pipeline_config`. For observations, call `df.repartition(8, 'ds')` before write.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §6.3 Parallelism, §6.5 Partition Tuning |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Benchmark | ingest_observations runtime under 5 min | pytest -m benchmark patient_360/tests/bronze/test_observations_perf.py |



## Verification

```yaml
AC1:
  - grep: {glob: "patient_360/_infra/cd/config/*.yaml", pattern: "spark_shuffle_partitions"}
AC2:
  - grep: {file: "patient_360/airflow/configs/observations.yml", pattern: 'target_partitions:\s*8|repartition.*8'}
AC3:
  - manual: "Spark UI / EXPLAIN EXTENDED check — runtime"
AC4:
  - grep: {file: "patient_360/_infra/cd/config/dev.yaml", pattern: 'spark_driver_memory:\s*1g'}
  - grep: {file: "patient_360/_infra/cd/config/dev.yaml", pattern: 'spark_executor_memory:\s*1g'}
AC5:
  - pytest: {node: "patient_360/tests/bronze/test_observations_perf.py", marker: "benchmark"}
```


## How to Test (User)

### Prerequisites


- STORY-02-001 / -02-003 done; local stack up


### Steps


1. `cd patient_360 && uv run pytest -m benchmark tests/bronze/test_observations_perf.py -v`


### Expected outcome


- Benchmark runtime under 5 min on DEV


## Documentation Updates


- [ ] N/A — internal tuning

