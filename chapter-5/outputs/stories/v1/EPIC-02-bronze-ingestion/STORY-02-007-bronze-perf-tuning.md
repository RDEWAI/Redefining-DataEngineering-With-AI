# STORY-02-007: Performance: replaceWhere partition pruning + shuffle.partitions + observations 8-partition tuning

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

Wire `spark.sql.shuffle.partitions=8` (DEV) / 16 (STAGING) / 32 (PROD) and `spark.sql.autoBroadcastJoinThreshold=50m` per LLD §6.3 / §6.4. Set `synthea_observations` to 8 target partitions (LLD §6.5 partition tuning); other Bronze tables to 1-2 partitions. Verify `replaceWhere ds = '{ds}'` prunes correctly via Spark UI / explain plan. Add a benchmark assertion that `ingest_observations` finishes within the LLD-stated 5 min on DEV.

## Acceptance Criteria


- [ ] `compute.spark_shuffle_partitions` set per env (8/16/32) in `_infra/cd/config/{env}.yaml` per LLD §6.3 [LLD §6.3]

- [ ] `synthea_observations` write produces ~8 output partitions per `ds` per LLD §6.5 [LLD §6.5]

- [ ] `replaceWhere` prune verified by `EXPLAIN EXTENDED` showing partition filter pushdown [LLD §3.3, §4.5]

- [ ] Benchmark: ingest_observations completes in < 5 min on DEV (1 executor, 2g) per LLD §4.4 [LLD §4.4]


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

