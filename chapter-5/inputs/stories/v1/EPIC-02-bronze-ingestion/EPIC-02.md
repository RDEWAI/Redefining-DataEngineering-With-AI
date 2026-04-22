# EPIC-02: Bronze Layer -- Config-Driven Ingestion

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 2 (LLD impl-sequence) |
| **Stories** | 10 |
| **Total Points** | 33 |
| **Sprints** | Sprint 3-4 |
| **Status** | To Do |

## Objective

Build the config-driven ingestion framework with per-table YAML configs, generic ingestion runner, TaskGroup factory, inline Spark Expectations validation (with per-table `dq_rules/{table}.yml` and quarantine routing), reconciliation_bronze for cross-table checks, dead letter handling, and contract/schema migration tests. All 13 source tables land in Bronze Delta via the framework. SE runner must be fully implemented before STAGING promotion.

## Scope

### In Scope
- 13 per-table YAML configuration files (`airflow/configs/{table}.yml`)
- Generic ingestion runner (`src/patient_360/bronze/ingestion_runner.py`) with metadata columns (`ds`, `_ingested_at`, `_source_batch_id`)
- SparkSubmitOperator wrapper (`src/patient_360/bronze/spark_submit_wrapper.py`)
- TaskGroup factory (`src/patient_360/bronze/ingestion_factory.py`)
- SE runner for inline DQ (`src/patient_360/utils/se_runner.py`) with env/dq_env mapping, quarantine path, bootstrap removal
- 13 per-table Bronze DQ rule files (`dq_rules/{table}.yml`, DQ-FLD-001 to DQ-FLD-045)
- 13 per-table table contracts (`contracts/{table}.yml` + `contracts/dq/{table}.yml`)
- Reconciliation_bronze task (`src/patient_360/utils/reconciliation.py`)
- Dead letter writer
- Unit and integration tests
- Contract tests (`tests/test_contracts.py`) asserting every table has `contracts/`, `dq_rules/`, and `ddl/liquibase/changelogs/` entries

### Out of Scope
- Silver/Gold transformations
- Silver/Gold DQ rules
- Monitoring dashboards
- Liquibase DDL changelogs (handled in EPIC-07 STORY-07-002)

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-02-001 | Create Per-Table YAML Ingestion Configs | 3 | Sprint 3 | STORY-01-002, STORY-01-008 |
| STORY-02-002 | Implement Generic Ingestion Runner | 5 | Sprint 3 | STORY-02-001, STORY-01-008 |
| STORY-02-003 | Implement SparkSubmitOperator Wrapper | 2 | Sprint 3 | STORY-02-002 |
| STORY-02-004 | Implement TaskGroup Factory | 3 | Sprint 3 | STORY-02-003 |
| STORY-02-005 | Wire Factory Into DAG | 2 | Sprint 3 | STORY-02-004, STORY-01-007 |
| STORY-02-006 | Implement SE Runner, Per-Table DQ Rules, and Quarantine | 8 | Sprint 3 | STORY-02-002 |
| STORY-02-007 | Implement Reconciliation Bronze Task | 3 | Sprint 4 | STORY-02-005, STORY-02-006 |
| STORY-02-008 | Implement Dead Letter Writer | 2 | Sprint 4 | STORY-02-006 |
| STORY-02-009 | Unit Tests for Bronze Ingestion Framework | 5 | Sprint 4 | STORY-02-002, STORY-02-004, STORY-02-006 |
| STORY-02-010 | Integration Test for Bronze Pipeline | 3 | Sprint 4 | STORY-02-007, STORY-02-009 |
| STORY-02-011 | Implement Contract and Schema Migration Tests | 2 | Sprint 4 | STORY-02-001, STORY-02-006 |

## Acceptance Criteria (Epic-Level)

- [ ] All 13 source tables land in Bronze Delta tables [LLD §5.1]
- [ ] Ingestion framework uses config-driven pattern (no per-table modules) [LLD §2.3]
- [ ] Inline SE validation executes DQ-FLD-001 to DQ-FLD-045 using per-table `dq_rules/{table}.yml` [DQS §2]
- [ ] SE runner maps env to dq_env (DEV→DEV, STAGING→QA, PROD→PROD) [LLD §2.3, §5.4]
- [ ] Drop-action rejections routed to `warehouse/{env}/quarantine/bronze/{table}/` [LLD §5.4, §8.2]
- [ ] Soft-import bootstrap fallback removed from `ingestion_runner.py` [LLD §8.5]
- [ ] `reconciliation_bronze` passes cross-table query_dq checks for all 13 tables [LLD §5.5]
- [ ] Critical tables (patients, encounters, allergies, orgs, providers, payers) fail on empty input or DQ failure [LLD §5.1]
- [ ] Contract test verifies every table has `contracts/{table}.yml`, `dq_rules/{table}.yml`, and `ddl/liquibase/changelogs/{table}.xml` [LLD §2.4]
- [ ] Unit test coverage >= 90% for Bronze modules [LLD §2.4]
- [ ] Integration test passes end-to-end [LLD §2.4]

## Developer Plugin

The `developer-plugin:create-ingestion` skill supports **story mode**: pass a story ID (e.g. `STORY-02-002`) to generate only that story's deliverables, validate dependency gates, and check acceptance criteria. Stories covered: STORY-02-001 through STORY-02-004, STORY-02-006, STORY-02-009, STORY-02-010.

## Risks & Assumptions

- YAML config schema drift across 13 files -- mitigated by contract test (STORY-02-011)
- Convention-based DQ discovery may miss rules silently -- mitigated by contract test assertion
- SE runner is implemented (commit c6cbd6a) but the soft-import bootstrap fallback in `ingestion_runner.py` has not been removed -- STAGING promotion blocked until that removal is merged [LLD §8.5, Decision 14]
- Inline SE action_if_failed misconfiguration -- mitigated by unit test per table
- Assumption: DuckDB source is read-only accessible
- Per-table `dq_rules/{table}.yml` delivered in commit c6cbd6a from DQS v2 SE rules; SE schema compliance verified by `test_per_table_configs.py`. Sole remaining STORY-02-006 AC: remove soft-import bootstrap from `ingestion_runner.py`
