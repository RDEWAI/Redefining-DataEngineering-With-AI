# STORY-01-006: Docker Compose Development Environment

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 1 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want a Docker Compose setup that runs Spark, DuckDB, Marquez, and Grafana locally so that I can develop and test the full pipeline stack on my machine.

## Description

Create `docker-compose.yaml` defining containers for: Apache Spark 4.0.0 (master + worker), DuckDB (source database with Synthea data), Marquez (OpenLineage backend), Grafana (dashboards), Prometheus (metrics), and Unity Catalog OSS (catalog/metastore). Configure networking so all services can communicate. Include health checks for each service. The Spark container must have PySpark, Delta Lake 4.x, Java 17, and spark-expectations pre-installed. DuckDB container must have the Synthea schema with sample data loaded.

## Acceptance Criteria

- [ ] `docker-compose.yaml` defines Spark, DuckDB, Marquez, Grafana, Prometheus, and Unity Catalog OSS containers [LLD §9.1]
- [ ] All containers start successfully with `docker compose up` [LLD §9.1]
- [ ] Spark master UI accessible at configured port [LLD §9.1]
- [ ] Marquez UI accessible at `http://localhost:5001` [LLD §10.1]
- [ ] Grafana accessible at `http://localhost:3000` [LLD §10.2]
- [ ] Unity Catalog OSS API accessible at `http://localhost:8080` [LLD §7.1]
- [ ] Health checks pass for all services [LLD §9.4]

## Technical Notes

- **Upstream references**: LLD SS9.1 (Environment Definitions), infrastructure-specs.md SS4, LLD SS10 (Monitoring)
- **Implementation hints**: Use official images where available. Spark image should be built from `python:3.11-slim` base per LLD SS9.2. Network all services on a shared Docker network. Marquez and Grafana containers are non-blocking (observability only).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS9.1 (Environment Definitions), SS9.4 (Health Check), SS10 (Monitoring) |
| HLD | SS5.1 (Technology Stack) |
| DMS | -- |
| DQS | -- |
