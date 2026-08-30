# STORY-01-006: Build docker-compose service block — Marquez + marquez-db (postgres)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 2 |
| **Sprint** | 2 |
| **Dependencies** | STORY-01-001 |
| **Status** | In Progress |

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

As a platform engineer, I want the Marquez lineage server and its postgres backing store defined in the shared `docker-compose.yml` so that every pipeline run can emit OpenLineage events to a known-good local endpoint.

## Description

Author the `marquez` and `marquez-db` service entries in `_infra/docker/docker-compose.yml` (shared file, co-authored across STORY-01-005, STORY-01-006, STORY-01-007). Pin images per LLD §9.1.1 (`marquezproject/marquez:0.51.1`, `postgres:14`). Wire `marquez` to `marquez-db` via `depends_on` with `condition: service_healthy`. Each service declares a `healthcheck:` block — postgres uses `pg_isready`, Marquez uses an HTTP probe against `:5001/api/v1/namespaces`.

## Acceptance Criteria


- [x] `_infra/docker/docker-compose.yml` declares `marquez` (`marquezproject/marquez:0.51.1`) and `marquez-db` (`postgres:14`) per LLD §9.1.1 [LLD §9.1.1]

- [x] `marquez` declares `depends_on: marquez-db` with `condition: service_healthy` [LLD §9.1.1]

- [x] Both services declare a `healthcheck:` block such that `docker compose ps` reports `healthy` within 60s of start [LLD §9.1.1]

- [x] **Definition of Done** evidence captured in the Verification block: (a) `docker compose ps` output showing `marquez` and `marquez-db` both `healthy`, AND (b) HTTP probe `curl -fsS http://localhost:5001/api/v1/namespaces` returns 200 with a JSON body [LLD §4.2, §9.1.1]


## Technical Notes

- **Upstream references**: LLD §4.2, §9.1, §9.1.1
- **Implementation hints**: postgres healthcheck = `pg_isready -U marquez`. Marquez healthcheck = `curl -fsS http://localhost:5001/api/v1/namespaces`. Keep credentials in env vars referenced from a single compose-level `.env` file. Lineage *wiring* into Spark (OpenLineage listener config) is owned by EPIC-06; this story only stands the server up.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2, §9.1, §9.1.1 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Smoke | Marquez API reachable | curl http://localhost:5001/api/v1/namespaces |



## Verification

```yaml
AC1:
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "marquezproject/marquez:0.51.1"}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "postgres:14"}
AC2:
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "condition: service_healthy"}
AC3:
  - grep_count: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "healthcheck:", at_least: 2}
  - manual: "docker compose ps shows marquez and marquez-db both 'healthy'"
AC4:
  - manual: "Capture `docker compose ps` output (both services healthy) AND `curl -fsS http://localhost:5001/api/v1/namespaces` returning 200; paste both into the story verification log"
```


## How to Test (User)

### Prerequisites


- Docker Desktop installed and running

- STORY-01-001 done


### Steps


1. `cd patient_360 && docker compose -f _infra/docker/docker-compose.yml up -d marquez-db marquez`

2. `docker compose -f _infra/docker/docker-compose.yml ps`

3. `curl -fsS http://localhost:5001/api/v1/namespaces`


### Expected outcome


- `marquez-db` and `marquez` containers both report `healthy`

- `curl` returns HTTP 200 with JSON body listing namespaces (empty array on first start)


## Documentation Updates


- [x] Update patient_360/README.md § "Local Stack — Marquez" with service ports

User-Verified-By: Phani Vemuri 2026-05-11
