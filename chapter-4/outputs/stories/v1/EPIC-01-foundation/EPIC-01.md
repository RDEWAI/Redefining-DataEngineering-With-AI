# EPIC-01: Foundation


| Field            | Value                       |
| ---------------- | --------------------------- |
| **LLD Section**  | Phase 1 (LLD impl-sequence) |
| **Stories**      | 8                           |
| **Total Points** | 23                          |
| **Sprints**      | Sprint 1-2                  |
| **Status**       | To Do                       |


## Objective

Establish the project scaffold, configuration framework, test infrastructure, Docker development environment, Airflow DAG skeleton, and StructType schema definitions. This epic produces no data output but creates the foundation that all subsequent epics build upon.

## Scope

### In Scope

- Project directory structure per LLD SS2.1
- Configuration loader and template (LLD SS7)
- Structured JSON logging framework
- Pytest test infrastructure with SparkSession fixtures
- Docker Compose for Spark, DuckDB, Marquez, Grafana, Unity Catalog OSS
- Airflow DAG skeleton with correct schedule and defaults
- StructType schema definitions for all 13 source tables

### Out of Scope

- Actual data ingestion or transformation
- DQ rule implementation
- CI/CD pipeline (handled in EPIC-07)
- Production deployment

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

- All directories from LLD SS2.1 project structure exist with **init**.py files [LLD §2.1]
- Config loader parses YAML with DEV/STAGING/PROD overrides [LLD §7]
- `pytest` runs green with SparkSession fixture [LLD §2.4]
- Docker Compose starts all services successfully [LLD §9.1]
- DAG visible in Airflow UI with correct schedule [LLD §4.1]
- All 13 StructType schemas defined and unit-tested [DMS §2]

## Risks & Assumptions

- Docker networking for Spark + Marquez + Grafana + Unity Catalog OSS may require iteration
- Assumption: DuckDB source data is available locally for development
- Assumption: Team has Docker Desktop or equivalent installed

