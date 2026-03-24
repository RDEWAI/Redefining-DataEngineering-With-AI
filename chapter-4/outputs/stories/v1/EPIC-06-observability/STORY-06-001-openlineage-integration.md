# STORY-06-001: OpenLineage Integration

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability + Monitoring |
| **Priority** | P2 -- Important |
| **Story Points** | 5 |
| **Sprint** | Sprint 8 |
| **Dependencies** | STORY-05-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want OpenLineage events emitted to Marquez after each pipeline run so that data lineage is tracked across Bronze, Silver, and Gold layers.

## Description

Implement the `emit_lineage` Airflow task and supporting code in `src/utils/metrics.py`. The task runs after reconciliation_gold completes and emits OpenLineage events to Marquez at `http://localhost:5001`. Events must include: input datasets (source tables), output datasets (target tables), transformation metadata, and run metadata (start time, end time, status). Lineage emission is non-blocking -- if Marquez is unavailable, log a warning and continue per circuit breaker pattern.

## Acceptance Criteria

- [ ] `emit_lineage` task emits OpenLineage events to Marquez endpoint [LLD §4.2, SS10.1]
- [ ] Lineage events visible in Marquez UI showing dataset dependencies [LLD §10.1]
- [ ] Input/output dataset mapping covers all Bronze, Silver, and Gold tables [LLD §10.1]
- [ ] Marquez connection failure triggers warning log, not task failure (circuit breaker) [LLD §8.5]
- [ ] Task depends on reconciliation_gold [LLD §4.2]

## Technical Notes

- **Upstream references**: LLD SS4.2, SS10.1, SS8.5 (Circuit Breaker)
- **Implementation hints**: Use `openlineage-airflow` integration or manual OpenLineage client. Marquez at `http://localhost:5001`. Non-blocking: wrap in try/except with warning log.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS10.1, SS4.2, SS8.5 |
| DMS | -- |
| STM | -- |
| DQS | -- |
