# STORY-06-004: Grafana DQ Scores Dashboard

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability + Monitoring |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 8 |
| **Dependencies** | STORY-06-002 |
| **Status** | To Do |

## User Story

As a data quality engineer, I want a Grafana dashboard showing DQ pass rates by layer and table so that I can identify quality trends and emerging issues.

## Description

Create a Grafana dashboard JSON for DQ Scores with panels for: (1) DQ pass rate by layer (Bronze, Silver, Gold), (2) per-table DQ pass rate trend, (3) rejection counts by table and severity, (4) inline SE metrics (action_if_failed distribution). Source data from Prometheus via OpenTelemetry metrics.

## Acceptance Criteria

- [ ] DQ Scores dashboard JSON created and importable into Grafana [LLD §10.2]
- [ ] Pass rate panels show by layer and by table [LLD §10.2]
- [ ] Rejection count panel shows trends over time [LLD §10.2]
- [ ] Inline SE action_if_failed distribution visible [LLD §10.2]

## Technical Notes

- **Upstream references**: LLD SS10.2
- **Implementation hints**: Query `pipeline.dq.pass_rate` and `pipeline.dq.rejections` metrics. Group by `layer` and `table_name` labels.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS10.2 |
| DMS | -- |
| STM | -- |
| DQS | SS2-3 (DQ rule context for dashboard design) |
