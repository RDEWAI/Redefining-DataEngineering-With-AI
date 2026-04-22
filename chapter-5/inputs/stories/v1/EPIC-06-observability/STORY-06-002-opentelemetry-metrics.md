# STORY-06-002: OpenTelemetry Metrics Emission

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability + Monitoring |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 8 |
| **Dependencies** | STORY-05-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want pipeline metrics pushed to Prometheus via OpenTelemetry so that Grafana dashboards can display runtime, row counts, and DQ scores.

## Description

Implement the `emit_metrics` Airflow task in `src/utils/metrics.py`. Push metrics including: pipeline runtime (seconds), task-level runtimes, row counts per table per layer, DQ pass/fail rates per table, inline SE rejection counts, and reconciliation results. Metrics emitted to OpenTelemetry collector at `http://localhost:4317`. Non-blocking per circuit breaker pattern.

## Acceptance Criteria

- [ ] `emit_metrics` task pushes metrics to OpenTelemetry endpoint [LLD §10.1]
- [ ] Metrics include: pipeline runtime, row counts, DQ pass rates, rejection counts [LLD §10.1]
- [ ] Metrics visible in Prometheus after pipeline run [LLD §10.1]
- [ ] Connection failure triggers warning, not task failure (circuit breaker) [LLD §8.5]
- [ ] Task depends on reconciliation_gold [LLD §4.2]

## Technical Notes

- **Upstream references**: LLD SS10.1, SS4.2, SS8.5
- **Implementation hints**: Use `opentelemetry-api` and `opentelemetry-sdk` with OTLP exporter. Define metric names following OpenTelemetry conventions: `pipeline.runtime.seconds`, `pipeline.rows.count`, `pipeline.dq.pass_rate`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS10.1, SS4.2, SS8.5 |
| DMS | -- |
| STM | -- |
| DQS | -- |
