# EPIC-06: Observability & Lineage

| Field | Value |
|-------|-------|
| **LLD Section** | §4.2, §10 |
| **Epic Scope** | crosscut |
| **Stories** | 4 |
| **Total Points** | 12 |
| **Sprints** | 9-10 |
| **Status** | Draft |

<!--
  Epic Scope vocabulary:
    - layer      → medallion layer epic (Bronze/Silver Dims/Silver Facts/Gold). MUST include closure sequence: performance-optimization → integration-test → (optional) deploy-validation.
    - foundation → scaffold/infra epic (no closure sequence required).
    - crosscut   → cross-layer concerns (observability, release, hardening).
-->

## Objective

Wire OpenLineage → Marquez, OpenTelemetry → Grafana, and the LLD §10.3 alert rules. The `dq_pass_rate` facet and stats tables are surfaced for HIPAA audit (NFR-7) and DQ visibility.



## Scope

### In Scope

- OpenLineage Spark listener + emit_lineage task

- OTel metrics + emit_metrics task

- 4 Grafana dashboards

- 7 alert rules routed to PagerDuty + Slack


### Out of Scope

- Layer-specific work (lives in layer epics)


## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|

| STORY-06-001 | Wire OpenLineage Spark listener + Marquez emit_lineage task | observability | 3 | 9 | STORY-05-005 |

| STORY-06-002 | Wire OpenTelemetry metrics + emit_metrics task | observability | 3 | 9 | STORY-05-005 |

| STORY-06-003 | Build Grafana dashboards: Pipeline Health, DQ, SLA, Capacity | observability | 3 | 9 | STORY-06-002 |

| STORY-06-004 | Wire alerting rules + PagerDuty / Slack channels per LLD §10.3 | observability | 3 | 10 | STORY-06-003 |




## Acceptance Criteria (Epic-Level)


- [ ] Marquez has lineage edges for every DAG run with `dq_pass_rate` facet [LLD §10, NFR-7]

- [ ] Grafana renders all 4 dashboards with live data [LLD §10.2]

- [ ] Synthetic alert reaches PagerDuty / Slack within LLD §10.3 response time [LLD §10.3]


## Risks & Assumptions


- OTel collector failure must not block the pipeline (LLD §8.1 fail-open).

