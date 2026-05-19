# STORY-03-005: Performance: broadcast small dims + SCD2-aware filter pushdown

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions (SCD Type 2) |
| **Story Type** | performance-optimization |
| **Priority** | P2 |
| **Story Points** | 2 |
| **Sprint** | 6 |
| **Dependencies** | STORY-03-001, STORY-03-002, STORY-03-003, STORY-03-004 |
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

As a data engineer, I want apply LLD §6.2 broadcast hints and SCD2-aware `is_current=TRUE` pre-filters so that Silver dimension reads at the natural-key cardinality (5,767 patients), not 5,767×N versions.

## Description

Set `spark.sql.autoBroadcastJoinThreshold=50m` and add explicit `broadcast()` hints when joining SCD2 dimensions to facts. Pre-filter dimensions with `WHERE is_current = TRUE` BEFORE broadcasting per LLD §6.2.

## Acceptance Criteria


- [ ] `spark.sql.autoBroadcastJoinThreshold=50m` set in pipeline config (all envs) [LLD §6.2]

- [ ] SCD2 dim reads in Silver/Gold pre-filter `is_current = TRUE` before broadcast [LLD §6.2]

- [ ] Benchmark: Silver dim reads complete < 30s on DEV [LLD §4.4]


## Technical Notes

- **Upstream references**: LLD §4.4, §6.2
- **Implementation hints**: Use F.broadcast(df) and filter is_current first.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §6.2 Join Strategy |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Benchmark | Silver dim read time | pytest -m benchmark patient_360/tests/silver/test_dims_perf.py |



## Verification

```yaml
AC1:
  - grep: {glob: "patient_360/_infra/cd/config/*.yaml", pattern: "autoBroadcastJoinThreshold|spark_broadcast_threshold"}
AC2:
  - grep_count: {glob: "patient_360/src/patient_360/silver/transform_*.py", pattern: "is_current.*True", equals: 4}
AC3:
  - pytest: {node: "patient_360/tests/silver/test_dims_perf.py", marker: "benchmark"}
```


## How to Test (User)

### Prerequisites


- STORY-03-001, STORY-03-002, STORY-03-003, STORY-03-004 done


### Steps


1. `cd patient_360 && uv run pytest -m benchmark tests/silver/test_dims_perf.py -v`


### Expected outcome


- Benchmark under 30s


## Documentation Updates


- [ ] N/A — internal tuning

