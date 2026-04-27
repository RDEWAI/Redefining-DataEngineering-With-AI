# STORY-01-005: Stand up docker-compose stack (UC OSS, Marquez, Grafana)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Runtime Bootstrap |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 1 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a `docker-compose.yml` defining the local Unity Catalog OSS, Marquez, Grafana, Prometheus, and Loki services so that any developer can `docker compose up -d` and have the full local stack ready.

## Description

Author `patient_360/_infra/docker/docker-compose.yml` declaring services per LLD §9.1 — `uc-oss` (Unity Catalog OSS at port 8080), `marquez` (port 5001), `grafana` (port 3000), `prometheus`, `loki`. Include health checks. Add Airflow service (LocalExecutor profile) so the same compose file boots the full local execution environment per LLD §6.1.

## Acceptance Criteria

- [ ] `patient_360/_infra/docker/docker-compose.yml` exists with `uc-oss`, `marquez`, `grafana`, `prometheus`, `loki`, `airflow` services [LLD §9.1]
- [ ] `docker compose -f patient_360/_infra/docker/docker-compose.yml up -d` succeeds [LLD §1]
- [ ] `curl http://localhost:8080/api/2.1/unity-catalog/catalogs` returns 200 [LLD §9.5]
- [ ] `curl http://localhost:5001` (Marquez) returns 200 [LLD §9.5]

## Technical Notes

- **Upstream references**: LLD §1 (overview), §9.1 (scaffold infra), §9.5 (health checks), §6.1 (Spark in-airflow-local mode)
- **Implementation hints**: Use `unitycatalog/unitycatalog:latest` image. Airflow image must have JDK 17 + Spark 4.0.0 + spark-expectations pre-installed.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §1, §6.1, §9.1, §9.5 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Smoke | Compose up succeeds and UC/Marquez return 200 | `make dev-up && curl localhost:8080/api/2.1/unity-catalog/catalogs` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/_infra/docker/docker-compose.yml"
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: 'uc-oss|unitycatalog'}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: 'marquez'}
AC2:
  - manual: "run `docker compose -f patient_360/_infra/docker/docker-compose.yml up -d` and verify exit 0"
AC3:
  - manual: "curl http://localhost:8080/api/2.1/unity-catalog/catalogs returns 200"
AC4:
  - manual: "curl http://localhost:5001 (Marquez) returns 200"
```

## How to Test (User)

### Prerequisites

- Docker Desktop running
- Ports 8080, 5001, 3000, 9090 free

### Steps

1. `cd patient_360 && docker compose -f _infra/docker/docker-compose.yml up -d`
2. `sleep 30 && curl -sS http://localhost:8080/api/2.1/unity-catalog/catalogs | jq`
3. `curl -sS http://localhost:5001`

### Expected outcome

- Step 1 prints "Started" for each service with no errors
- Step 2 returns JSON with at least one catalog
- Step 3 returns Marquez homepage

## Documentation Updates

- [ ] Update `patient_360/_infra/docker/README.md` § "Local Stack" with `docker compose up` instructions and port map
