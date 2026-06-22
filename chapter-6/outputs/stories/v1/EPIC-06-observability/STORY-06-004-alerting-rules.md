# STORY-06-004: Wire alerting rules + PagerDuty / Slack channels per LLD §10.3

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability & Lineage |
| **Story Type** | observability |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 10 |
| **Dependencies** | STORY-06-003 |
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

As a data engineer, I want route the LLD §10.3 alerting rules to PagerDuty `p360-critical` and Slack `#data-alerts-{env}` so that on-call gets paged within the LLD-stated response times for pipeline failures and DQ regressions.

## Description

Author Grafana / Alertmanager rule files for the 7 LLD §10.3 alert conditions (Pipeline failure, Pipeline SLA miss, Allergy data failure, Row count anomaly, etc.). Route CRITICAL → PagerDuty `p360-critical`; WARNING → Slack `#data-alerts-{env}`. Allergy failures double-route to Clinical Ops Director (DQS §1).

## Acceptance Criteria


- [ ] All 7 LLD §10.3 alert rules defined in `_infra/observability/alerts/*.yaml` [LLD §10.3]

- [ ] CRITICAL rules route to PagerDuty `p360-critical` [LLD §8.5, §10.3]

- [ ] Allergy DQ failures route to PagerDuty + Clinical Ops Director per DQS §1 [DQS §1, LLD §8.5]


## Technical Notes

- **Upstream references**: LLD §8.5, §10.3; DQS §1
- **Implementation hints**: Use Grafana unified alerting + Alertmanager.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §8.5 Alerting, §10.3 Rules |

| DQS | §1 Allergy elevated path |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Manual UI check | trigger a synthetic alert | force a pipeline failure and observe PagerDuty/Slack |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/_infra/observability/alerts/*.yaml", equals: 7}
AC2:
  - grep: {glob: "patient_360/_infra/observability/alerts/*.yaml", pattern: "p360-critical"}
AC3:
  - grep: {glob: "patient_360/_infra/observability/alerts/*.yaml", pattern: "Clinical Ops|allergy"}
```


## How to Test (User)

### Prerequisites


- STORY-06-003 done


### Steps


1. Force a synthetic pipeline failure and observe PagerDuty/Slack notifications


### Expected outcome


- CRITICAL alerts arrive within 15 min; allergy failure double-routes


## Documentation Updates


- [ ] Update patient_360/_infra/observability/README.md with alert routing matrix

