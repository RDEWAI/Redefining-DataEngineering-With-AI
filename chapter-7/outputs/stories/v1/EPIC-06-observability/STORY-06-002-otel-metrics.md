# STORY-06-002: Wire OpenTelemetry metrics + emit_metrics task

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

As a data engineer, I want emit pipeline runtime, rows-processed, DQ pass-rate, and SCD2-versions-created metrics to OTel collector so that Grafana panels (LLD §10.2) can render the LLD §10.1 metrics for the Pipeline Health, DQ, and SLA dashboards.

## Description

Wire `emit_metrics` task per LLD §4.2. Use `metrics.py` (STORY-01-002) wrappers to emit the 10 LLD §10.1 metrics. Configure OTel collector OTLP endpoint per LLD §7.1.

## Acceptance Criteria


- [ ] `emit_metrics` task in DAG runs after `reconciliation_gold` [LLD §4.2]

- [ ] All 10 LLD §10.1 metrics emitted (`pipeline.runtime_seconds`, `dq.pass_rate`, etc.) [LLD §10.1]

- [ ] `monitoring.opentelemetry_endpoint` configurable per env per LLD §7.1 [LLD §7.1]


## Technical Notes

- **Upstream references**: LLD §4.2, §7.1, §10.1
- **Implementation hints**: OTLP gRPC endpoint to `otel-collector:4317`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2, §7.1, §10.1 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Manual UI check | Grafana metrics arrive | open http://localhost:3000 and inspect Pipeline Health dashboard |



## Verification

```yaml
AC1:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "emit_metrics"}
AC2:
  - grep_count: {file: "patient_360/src/patient_360/utils/metrics.py", pattern: "pipeline.runtime|dq.pass_rate|scd2.versions", equals: 3}
AC3:
  - grep: {glob: "patient_360/_infra/cd/config/*.yaml", pattern: "opentelemetry_endpoint"}
```


## How to Test (User)

### Prerequisites


- STORY-05-005 done

- OTel collector up


### Steps


1. Trigger DAG; open Grafana http://localhost:3000


### Expected outcome


- Pipeline Health dashboard renders runtime + row-count panels


## Documentation Updates


- [ ] N/A — internal metrics wiring

