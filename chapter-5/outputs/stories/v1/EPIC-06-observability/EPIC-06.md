# EPIC-06: Observability — Lineage, Metrics, Dashboards

| Field | Value |
|-------|-------|
| **LLD Section** | §10 |
| **Epic Scope** | crosscut |
| **Stories** | 3 |
| **Total Points** | 9 |
| **Sprints** | 4 |
| **Status** | To Do |

## Objective

Wire OpenLineage emitters (Marquez), OpenTelemetry metrics (Prometheus + Grafana), and Loki log aggregation across the pipeline per LLD §10. Includes the 2 Airflow tasks `emit_lineage` and `emit_metrics` that close the DAG, plus DQ dashboards and alerting rules per §10.3.

## Scope

### In Scope
- `emit_lineage` Airflow task wiring OpenLineage to Marquez per §10.2
- `emit_metrics` Airflow task wiring OpenTelemetry to Prometheus per §10.1
- Grafana dashboards: pipeline runtime, DQ pass rate, SE error drop rate per §10.2
- Alerting rules in Prometheus per §10.3

### Out of Scope
- Layer-specific perf instrumentation (lives in each layer epic)

## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|
| STORY-06-001 | emit_lineage task + OpenLineage Marquez integration | observability | 3 | 4 | STORY-05-005 |
| STORY-06-002 | emit_metrics task + OpenTelemetry → Prometheus wiring | observability | 3 | 4 | STORY-05-005 |
| STORY-06-003 | Grafana DQ + pipeline-runtime dashboards + alerting rules | observability | 3 | 4 | STORY-06-001, STORY-06-002 |

## Acceptance Criteria (Epic-Level)

- [ ] Marquez UI shows lineage edges for the latest pipeline run [LLD §10.2]
- [ ] Grafana DQ pass-rate panel renders SE stats from `*_se_stats` tables [LLD §10.2]
- [ ] Alerting rules fire for runtime > 45 min and DQ pass rate < threshold [LLD §10.3, §8.5]

## Risks & Assumptions

- Taylor P. (50% allocation) is the natural owner — observability matches their skill matrix
- Marquez/Grafana run in the local docker stack (EPIC-01)
