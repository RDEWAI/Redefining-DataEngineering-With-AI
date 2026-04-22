# STORY-06-003: Grafana Pipeline Health Dashboard

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability + Monitoring |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 8 |
| **Dependencies** | STORY-06-002 |
| **Status** | To Do |

## User Story

As a data operations engineer, I want a Grafana dashboard showing pipeline health metrics so that I can monitor runtime trends, task success rates, and identify degradation.

## Description

Create a Grafana dashboard JSON for Pipeline Health with panels for: (1) pipeline runtime trend (time series), (2) task-level success/failure counts (bar chart), (3) current run status indicator, (4) task duration heatmap across layers. Import into Grafana at `http://localhost:3000`.

## Acceptance Criteria

- [ ] Pipeline Health dashboard JSON created and importable into Grafana [LLD §10.2]
- [ ] Runtime trend panel shows historical pipeline execution times [LLD §10.2]
- [ ] Task status panel shows success/failure rate per task [LLD §10.2]
- [ ] Dashboard accessible at `http://localhost:3000` [LLD §10.2]

## Technical Notes

- **Upstream references**: LLD SS10.2 (Grafana dashboards)
- **Implementation hints**: Use Grafana provisioning (JSON dashboard model). Prometheus as data source. Query `pipeline.runtime.seconds` and task status metrics.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS10.2 |
| DMS | -- |
| STM | -- |
| DQS | -- |
