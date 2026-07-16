# STORY-04-011: Performance: shuffle.partitions tuning + observations 8-partition repartition

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts |
| **Story Type** | performance-optimization |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 7 |
| **Dependencies** | STORY-04-010 |
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

As a data engineer, I want apply LLD §6.3 / §6.5 partition + shuffle tuning to Silver fact writes so that `clinical_observations` (~4.3M rows) finishes within LLD §4.4 critical-path budget (~8 min).

## Description

Set Silver fact writes to use `spark.sql.shuffle.partitions` from pipeline config (8/16/32 per env). Repartition `clinical_observations` to 8 output partitions (LLD §6.5). Verify sort-merge join is selected for encounters↔observations (340K × 4.4M).

## Acceptance Criteria


- [ ] `clinical_observations` write produces ~8 partitions per `ds` [LLD §6.5]

- [ ] EXPLAIN EXTENDED on encounters↔observations confirms sort-merge join [LLD §6.2]

- [ ] Benchmark: `transform_observations_silver` < 8 min on DEV per LLD §4.4 [LLD §4.4]


## Technical Notes

- **Upstream references**: LLD §4.4, §6.2, §6.3, §6.5
- **Implementation hints**: Repartition before write; check explain plan via Spark UI.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §6.2-§6.5 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Benchmark | transform_observations_silver runtime | pytest -m benchmark patient_360/tests/silver/test_observations_perf.py |



## Verification

```yaml
AC1:
  - grep: {file: "patient_360/src/patient_360/silver/transform_observations.py", pattern: "repartition.*8"}
AC2:
  - manual: "Spark UI explain plan check — sort-merge join"
AC3:
  - pytest: {node: "patient_360/tests/silver/test_observations_perf.py", marker: "benchmark"}
```


## How to Test (User)

### Prerequisites


- STORY-04-010 done


### Steps


1. `cd patient_360 && uv run pytest -m benchmark tests/silver/test_observations_perf.py -v`


### Expected outcome


- Benchmark under 8 min


## Documentation Updates


- [ ] N/A — internal tuning

