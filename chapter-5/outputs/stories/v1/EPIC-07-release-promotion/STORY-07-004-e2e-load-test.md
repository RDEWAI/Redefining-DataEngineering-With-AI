# STORY-07-004: Full-pipeline E2E load test (Bronze → Gold) on staging-equivalent data

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Release & Promotion |
| **Story Type** | release |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 11 |
| **Dependencies** | STORY-07-003 |
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

As a data engineer, I want run the full DAG end-to-end on a staging-equivalent dataset and confirm critical-path < 33 min so that we have evidence the LLD §4.4 critical path holds and NFR-1 / NFR-2 SLAs are met.

## Description

Run `airflow dags trigger patient360_hourly_v1` against a staging-equivalent dataset (full Phase-1 7.9M-row Synthea snapshot). Assert end-to-end runtime < 33 min, all 3 reconciliations succeed, p90 query latency on `patient_summary` < 2s (NFR-1), data freshness ≤ 1 hour (NFR-2).

## Acceptance Criteria


- [ ] Full DAG run on staging-equivalent data completes < 33 min per LLD §4.4 [LLD §4.4]

- [ ] p90 query latency on `patient_summary` < 2s per NFR-1 / DRD §4.3 [LLD §10.4, DRD §4.3]

- [ ] Data freshness ≤ 1 hour per NFR-2 [LLD §10.4]


## Technical Notes

- **Upstream references**: LLD §4.4, §10.4; DRD §4.3-§4.4
- **Implementation hints**: Capture timings via `pipeline.runtime_seconds` OTel metric.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.4 Critical Path, §10.4 SLA |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Benchmark | full pipeline runtime | pytest -m benchmark patient_360/tests/integration/test_full_pipeline_perf.py |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_full_pipeline_perf.py::test_runtime_under_33min", marker: "benchmark"}
AC2:
  - pytest: {node: "patient_360/tests/integration/test_full_pipeline_perf.py::test_p90_query_latency_under_2s", marker: "benchmark"}
AC3:
  - pytest: {node: "patient_360/tests/integration/test_full_pipeline_perf.py::test_freshness_under_1h", marker: "benchmark"}
```


## How to Test (User)

### Prerequisites


- STORY-07-003 done

- Staging-equivalent dataset seeded


### Steps


1. `cd patient_360 && uv run pytest -m benchmark tests/integration/test_full_pipeline_perf.py -v`


### Expected outcome


- All three benchmark assertions pass


## Documentation Updates


- [ ] Update patient_360/README.md § "SLA Tracking" with the E2E benchmark numbers

