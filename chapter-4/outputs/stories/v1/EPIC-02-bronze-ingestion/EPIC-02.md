# EPIC-02: Bronze Layer -- Config-Driven Ingestion

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 2 (LLD impl-sequence) |
| **Stories** | 10 |
| **Total Points** | 33 |
| **Sprints** | Sprint 3-4 |
| **Status** | To Do |

## Objective

Build the config-driven ingestion framework with per-table YAML configs, generic ingestion runner, TaskGroup factory, inline Spark Expectations validation, reconciliation_bronze for cross-table checks, and dead letter handling. All 13 source tables land in Bronze Delta via the framework.

## Scope

### In Scope
- 13 per-table YAML configuration files
- Generic ingestion runner (ingestion_runner.py)
- SparkSubmitOperator wrapper
- TaskGroup factory (ingestion_factory.py)
- SE runner for inline DQ (se_runner.py)
- Bronze DQ rules YAML (DQ-FLD-001 to DQ-FLD-045)
- Reconciliation_bronze task
- Dead letter writer
- Unit and integration tests

### Out of Scope
- Silver/Gold transformations
- Silver/Gold DQ rules
- Monitoring dashboards

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-02-001 | Create Per-Table YAML Ingestion Configs | 3 | Sprint 3 | STORY-01-002, STORY-01-008 |
| STORY-02-002 | Implement Generic Ingestion Runner | 5 | Sprint 3 | STORY-02-001, STORY-01-008 |
| STORY-02-003 | Implement SparkSubmitOperator Wrapper | 2 | Sprint 3 | STORY-02-002 |
| STORY-02-004 | Implement TaskGroup Factory | 3 | Sprint 3 | STORY-02-003 |
| STORY-02-005 | Wire Factory Into DAG | 2 | Sprint 3 | STORY-02-004, STORY-01-007 |
| STORY-02-006 | Implement SE Runner and Bronze DQ Rules | 5 | Sprint 3 | STORY-02-002 |
| STORY-02-007 | Implement Reconciliation Bronze Task | 3 | Sprint 4 | STORY-02-005, STORY-02-006 |
| STORY-02-008 | Implement Dead Letter Writer | 2 | Sprint 4 | STORY-02-006 |
| STORY-02-009 | Unit Tests for Bronze Ingestion Framework | 5 | Sprint 4 | STORY-02-002, STORY-02-004, STORY-02-006 |
| STORY-02-010 | Integration Test for Bronze Pipeline | 3 | Sprint 4 | STORY-02-007, STORY-02-009 |

## Acceptance Criteria (Epic-Level)

- [ ] All 13 source tables land in Bronze Delta tables [LLD §5.1]
- [ ] Ingestion framework uses config-driven pattern (no per-table modules) [LLD §2.3]
- [ ] Inline SE validation executes DQ-FLD-001 to DQ-FLD-045 [DQS §2]
- [ ] Reconciliation_bronze passes for all 13 tables [LLD §5.5]
- [ ] Critical tables fail on empty input or DQ failure [LLD §5.1]
- [ ] Non-critical table DQ failures quarantined to dead-letter [LLD §8.2]
- [ ] Unit test coverage >= 90% for Bronze modules [LLD §2.4]
- [ ] Integration test passes end-to-end [LLD §2.4]

## Risks & Assumptions

- YAML config schema drift across 13 files -- mitigated by unit test validation
- Convention-based DQ discovery may miss rules silently -- mitigated by assertion test
- Inline SE action_if_failed misconfiguration -- mitigated by unit test per table
- Assumption: DuckDB source is read-only accessible
