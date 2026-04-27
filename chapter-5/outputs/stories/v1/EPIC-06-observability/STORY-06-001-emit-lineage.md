# STORY-06-001: emit_lineage task + OpenLineage Marquez integration

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

As a Data Engineer, I want OpenLineage events emitted from Airflow tasks to Marquez so that lineage is visible in the Marquez UI for every pipeline run.

## Description

Add the OpenLineage Airflow integration (`openlineage-airflow` package) configured to emit to `http://localhost:5001` (Marquez). Add the `emit_lineage` task per LLD §4.2 — runs after `reconciliation_gold` to flush any tail events. Verify Marquez UI lists `bronze_*`, `silver_*`, `gold_*` datasets with edges between them.

## Acceptance Criteria

- [ ] `patient_360/airflow/dags/patient360_hourly_v1.py` contains `emit_lineage` PythonOperator/BashOperator [LLD §4.2]
- [ ] OpenLineage configured via `OPENLINEAGE_URL=http://localhost:5001` env var [LLD §10.2]
- [ ] `monitoring.marquez_endpoint` config key honored [LLD §7.1]
- [ ] Marquez UI shows lineage edges for the latest run [LLD §10.2]

## Technical Notes

- **Upstream references**: LLD §4.2 (emit_lineage task), §7.1 (monitoring.marquez_endpoint), §10.2 (dashboard specs)
- **Implementation hints**: `pip install openlineage-airflow`. Set the OL transport via env vars in docker-compose.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.2, §7.1, §10.2 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | env-var wiring | `pytest patient_360/tests/observability/test_openlineage_unit.py` |
| Manual | Marquez UI shows edges | Manual UI inspection at `http://localhost:5001` |

## Verification

```yaml
AC1:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: 'emit_lineage'}
AC2:
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: 'OPENLINEAGE_URL'}
AC3:
  - grep: {file: "patient_360/_infra/cd/config/dev.yaml", pattern: 'marquez_endpoint'}
AC4:
  - manual: "Marquez UI at http://localhost:5001 shows bronze→silver→gold edges for run"
```

## How to Test (User)

### Prerequisites

- STORY-05-005 green; pipeline ran end-to-end at least once

### Steps

1. `open http://localhost:5001` (or `curl http://localhost:5001/api/v1/lineage?...`)
2. `cd patient_360 && uv run pytest tests/observability/test_openlineage_unit.py -v`

### Expected outcome

- Step 1: Marquez UI shows the `patient360_hourly_v1` job with bronze/silver/gold datasets connected
- Step 2: unit tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Observability — Lineage" with Marquez UI link and screenshot pointer
