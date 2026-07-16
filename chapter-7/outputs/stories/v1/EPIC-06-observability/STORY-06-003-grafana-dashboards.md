# STORY-06-003: Build Grafana dashboards: Pipeline Health, DQ, SLA, Capacity

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability & Lineage |
| **Story Type** | observability |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 9 |
| **Dependencies** | STORY-06-002 |
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

As a data engineer, I want have the four LLD §10.2 dashboards provisioned in Grafana via dashboard JSON so that audiences (Data Eng, Clinical Ops, Platform Eng) get the LLD-specified panels out of the box.

## Description

Author 4 dashboard JSON files under `_infra/observability/grafana/dashboards/`: Pipeline Health, Data Quality Scores, SLA Tracking, Capacity Planning. Provisioning datasource: OTel/Prometheus.

## Acceptance Criteria


- [ ] 4 dashboard JSON files exist per LLD §10.2 [LLD §10.2]

- [ ] DQ dashboard surfaces `dq.pass_rate` per layer per table per rule severity [LLD §10.2]

- [ ] SLA Tracking shows `current_time - max(_ingested_at)` panel per LLD §10.4 [LLD §10.4]


## Technical Notes

- **Upstream references**: LLD §10.2, §10.4
- **Implementation hints**: Reuse the Grafana dashboard JSON schema; provision via Grafana provisioning.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §10.2 Dashboards, §10.4 SLA |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Manual UI check | dashboards render | open Grafana http://localhost:3000 |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/_infra/observability/grafana/dashboards/*.json", equals: 4}
AC2:
  - grep: {glob: "patient_360/_infra/observability/grafana/dashboards/*.json", pattern: "dq.pass_rate|dq_pass_rate"}
AC3:
  - grep: {glob: "patient_360/_infra/observability/grafana/dashboards/*.json", pattern: "_ingested_at"}
```


## How to Test (User)

### Prerequisites


- STORY-06-002 done


### Steps


1. Open http://localhost:3000 and inspect the four dashboards


### Expected outcome


- All four dashboards render without missing panels


## Documentation Updates


- [ ] Update patient_360/_infra/observability/README.md with dashboard listing

