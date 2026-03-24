# STORY-07-002: Docker Image Build

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Deployment + Rollback |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 9 |
| **Dependencies** | STORY-07-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want a production Docker image built from python:3.11-slim with health check so that the pipeline runs in a consistent container environment.

## Description

Create `Dockerfile` using `python:3.11-slim` as base, install PySpark, Delta Lake, spark-expectations, and all pipeline dependencies. Include a `/health` endpoint per LLD SS9.4. Add a GitHub Actions build workflow that builds and tags the image on merge to main.

## Acceptance Criteria

- [ ] Dockerfile based on `python:3.11-slim` [LLD §9.2]
- [ ] PySpark 4.0.0, Delta Lake 4.x, spark-expectations installed [LLD §1]
- [ ] `/health` endpoint returns 200 when driver is healthy [LLD §9.4]
- [ ] Image builds successfully in CI [LLD §9.2]
- [ ] Image size optimized (multi-stage build if needed) [LLD §9.2]

## Technical Notes

- **Upstream references**: LLD SS9.2, SS9.4
- **Implementation hints**: Use multi-stage build to separate build deps from runtime. Health check endpoint can be a simple Flask/FastAPI route on the Spark driver.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS9.2, SS9.4 |
| DMS | -- |
| STM | -- |
| DQS | -- |
