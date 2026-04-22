# EPIC-01: Foundation


| Field            | Value                       |
| ---------------- | --------------------------- |
| **LLD Section**  | Phase 1 (LLD impl-sequence) |
| **Stories**      | 8                           |
| **Total Points** | 23                          |
| **Sprints**      | Sprint 1-2                  |
| **Status**       | To Do                       |


## Objective

Establish the project scaffold (via cookiecutter-chapter template), configuration framework, test infrastructure, Docker development environment, Airflow DAG skeleton, and StructType schema definitions. This epic produces no data output but creates the foundation that all subsequent epics build upon.

## Scope

### In Scope

- Project directory structure via `cookiecutter inputs/lld/v1/templates/cookiecutter-chapter/` (LLD §2.1, Decision 13)
- Configuration loader and template (LLD §7)
- Structured JSON logging framework
- Pytest test infrastructure with SparkSession fixtures (layer-mirrored: `tests/{bronze,silver,gold}/`)
- Docker Compose for local dev: UC OSS, Marquez, Grafana, Prometheus, Loki (`_infra/docker/docker-compose.yml`)
- Airflow DAG skeleton with correct schedule and defaults
- StructType schema definitions for all 13 source tables

### Out of Scope

- Actual data ingestion or transformation
- DQ rule implementation
- CI/CD pipeline (handled in EPIC-07)
- Production deployment
- Liquibase DDL migrations (handled in EPIC-07)

## Stories


| ID           | Title                                              | Points | Sprint   | Dependencies               |
| ------------ | -------------------------------------------------- | ------ | -------- | -------------------------- |
| STORY-01-001 | Create Project Directory Structure                 | 2      | Sprint 1 | None                       |
| STORY-01-002 | Implement Configuration Loader                     | 3      | Sprint 1 | STORY-01-001               |
| STORY-01-003 | Create Configuration Template YAML                 | 2      | Sprint 1 | STORY-01-002               |
| STORY-01-004 | Set Up Structured Logging Framework                | 2      | Sprint 1 | STORY-01-001               |
| STORY-01-005 | Set Up Test Infrastructure                         | 3      | Sprint 1 | STORY-01-001               |
| STORY-01-006 | Docker Compose Development Environment             | 3      | Sprint 1 | STORY-01-001               |
| STORY-01-007 | Airflow DAG Skeleton                               | 3      | Sprint 2 | STORY-01-002, STORY-01-006 |
| STORY-01-008 | Define StructType Schemas for All 13 Bronze Tables | 5      | Sprint 2 | STORY-01-001               |


## Acceptance Criteria (Epic-Level)

- [ ] Cookiecutter scaffold renders correctly; all directories from LLD §2.1 exist with `__init__.py` files [LLD §2.1, Decision 13]
- [ ] Config loader parses YAML with DEV/STAGING/PROD overrides including new catalog/quarantine params [LLD §7]
- [ ] `pytest` runs green with SparkSession fixture in layer-mirrored test layout [LLD §2.4]
- [ ] Docker Compose (`_infra/docker/docker-compose.yml`) starts UC OSS, Marquez, Grafana, Prometheus, Loki [LLD §9.1]
- [ ] DAG visible in Airflow UI with correct schedule [LLD §4.1]
- [ ] All 13 StructType schemas defined and unit-tested [DMS §2]

## Risks & Assumptions

- Cookiecutter template rendering may require manual path adjustments if template is not finalized
- Docker networking for UC OSS + Marquez + Grafana may require iteration
- Assumption: DuckDB source data is available locally for development
- Assumption: Team has Docker Desktop or equivalent installed

