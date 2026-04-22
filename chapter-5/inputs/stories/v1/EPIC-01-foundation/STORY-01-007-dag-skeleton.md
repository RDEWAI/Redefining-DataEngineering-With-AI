# STORY-01-007: Airflow DAG Skeleton

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 2 |
| **Dependencies** | STORY-01-002, STORY-01-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want an Airflow DAG skeleton with the correct schedule, concurrency, and retry defaults so that task development in later sprints can plug into a working orchestration framework.

## Description

Create `airflow/dags/patient360_hourly_v1.py` (per cookiecutter scaffold layout in LLD §2.1 and §4) with the DAG configuration defined in LLD Section 4.1. The DAG must have the correct schedule (`0 * * * *`), timezone (UTC), catchup enabled, max_active_runs of 1, and concurrency of 16. Default args must include owner, retry settings, and email configuration. The DAG should import the ingestion factory module (`src/patient_360/bronze/ingestion_factory.py`, stubbed for now) and define placeholder task groups for bronze_ingestion, silver_dimensions, silver_facts, gold_build, and observability. The DAG must be visible in the Airflow UI.

## Acceptance Criteria

- [ ] `airflow/dags/patient360_hourly_v1.py` exists with DAG ID `patient360_hourly_v1` [LLD §4.1]
- [ ] Schedule set to `0 * * * *` (hourly), timezone UTC, catchup True [LLD §4.1]
- [ ] Max active runs = 1, concurrency = 16 [LLD §4.1]
- [ ] Default args include retries: 2, retry_delay: 120s, timeout: 60 min [LLD §4.1]
- [ ] DAG imports ingestion factory module (stub) for bronze TaskGroup [LLD §4.2]
- [ ] DAG is visible in Airflow UI with correct tags [LLD §4.1]

## Technical Notes

- **Upstream references**: LLD §4.1 (DAG Configuration), LLD §4.2 (Task Inventory), dag-definition.yaml (derived artifact)
- **Implementation hints**: Use the Airflow TaskFlow API or classic operators. The bronze_ingestion TaskGroup will be wired in EPIC-02 using `ingestion_factory.py` from `src/patient_360/bronze/`. For now, create a dummy task to make the DAG parseable. DAG file location is `airflow/dags/patient360_hourly_v1.py` (cookiecutter scaffold layout, not a root-level `dags/` directory). Tags: `patient-360`, `medallion`, `hourly`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS4.1 (DAG Configuration), SS4.2 (Task Inventory) |
| HLD | SS5.3 (Orchestration) |
| DMS | -- |
| DQS | -- |
