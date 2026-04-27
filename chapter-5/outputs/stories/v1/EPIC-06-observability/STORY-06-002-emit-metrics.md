# STORY-06-002: emit_metrics task + OpenTelemetry → Prometheus wiring

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability — Lineage, Metrics, Dashboards |
| **Story Type** | observability |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 4 |
| **Dependencies** | STORY-05-005 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want pipeline + DQ metrics shipped via OpenTelemetry to Prometheus so that Grafana dashboards have a live data source.

## Description

Wire `utils/metrics.py` to push to the OpenTelemetry collector at `http://localhost:4317` (LLD §7.1 `monitoring.opentelemetry_endpoint`). Add the `emit_metrics` Airflow task per LLD §4.2 collating per-layer runtime, row counts, DQ pass rates, and SE error drop counts. All metrics tagged with `env`, `dag_id`, `run_id`, `ds`.

## Acceptance Criteria

- [ ] `patient_360/airflow/dags/patient360_hourly_v1.py` contains `emit_metrics` task [LLD §4.2]
- [ ] `utils/metrics.py` posts to `monitoring.opentelemetry_endpoint` [LLD §7.1]
- [ ] Per-layer runtime gauges, row-count counters, DQ pass-rate gauges emitted [LLD §10.1]
- [ ] Prometheus scrapes the OTel collector and shows series in Grafana Explore [LLD §10.1]

## Technical Notes

- **Upstream references**: LLD §4.2, §7.1, §10.1 (Metrics inventory)
- **Implementation hints**: Use `opentelemetry-exporter-otlp` Python package. Tags carry full pipeline context.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.2, §7.1, §10.1 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | metrics.py emits expected series | `pytest patient_360/tests/observability/test_metrics_unit.py` |
| Manual | Prometheus has series | Open `http://localhost:9090/graph` and query `pipeline_runtime_seconds` |

## Verification

```yaml
AC1:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: 'emit_metrics'}
AC2:
  - grep: {file: "patient_360/src/patient_360/utils/metrics.py", pattern: 'opentelemetry|otlp'}
AC3:
  - pytest: {node: "patient_360/tests/observability/test_metrics_unit.py"}
AC4:
  - manual: "Prometheus query `pipeline_runtime_seconds` returns series"
```

## How to Test (User)

### Prerequisites

- STORY-05-005 green
- Docker stack with `otel-collector` + `prometheus` services up

### Steps

1. `cd patient_360 && uv run pytest tests/observability/test_metrics_unit.py -v`
2. `curl -sS 'http://localhost:9090/api/v1/query?query=pipeline_runtime_seconds'`

### Expected outcome

- Step 1: unit tests pass
- Step 2: Prometheus returns ≥ 1 series per layer

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Observability — Metrics" with Prometheus and Grafana endpoints
