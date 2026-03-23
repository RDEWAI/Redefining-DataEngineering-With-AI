# Implementation Sequence: Patient 360 Medallion Pipeline


| Field               | Value                                |
| ------------------- | ------------------------------------ |
| **Generated From**  | LLD-2026-03-23-patient-360.md (v1.2) |
| **Generated**       | 2026-03-23                           |
| **Estimated Total** | 8-10 sprints (2-week sprints)        |


---

## Overview

This document defines the recommended build order for the Patient 360 pipeline. Each phase builds on the previous one, ensuring that developers can test incrementally and that safety-critical paths (allergy data) are validated early.

The sequence is derived from:

- LLD Section 2 (Code Architecture) -- project structure, ingestion framework, and module interface contracts
- LLD Section 4 (DAG Specification) -- task dependencies, TaskGroup factory, and critical path
- LLD Section 9 (Deployment) -- environment promotion flow
- LLD Section 12 (Traceability Matrix) -- requirement coverage per phase

**v1.2 changes**: Phase 2 restructured to integrate inline SE validation within ingestion tasks (replacing standalone dq_gate_bronze) and add reconciliation_bronze for cross-table query_dq checks. Phases 4 and 5 similarly updated: inline SE replaces dq_gate_silver/dq_gate_gold; reconciliation_silver and reconciliation_gold added. Coverage targets updated to >= 90% unit test coverage. Integration tests now use pytest + Unity Catalog OSS.

---

## Phase 1: Foundation (Sprint 1-2)

**Goal**: Project scaffold, configuration framework, and dev environment.


| #   | Task                          | LLD Section                 | Deliverable                                 | Acceptance Criteria                                            |
| --- | ----------------------------- | --------------------------- | ------------------------------------------- | -------------------------------------------------------------- |
| 1.1 | Create project structure      | LLD SS2.1                    | `src/` directory tree per code architecture | All directories created with `__init__.py`; includes `src/config/tables/` and `src/quality/reconciliation.py` |
| 1.2 | Implement config loader       | LLD SS7                      | `src/config/pipeline_config.py`             | Loads YAML config; resolves DEV/STAGING/PROD overrides         |
| 1.3 | Create config template        | LLD SS7.2                    | `config/config-template.yaml`               | Valid YAML with all 3 environments; includes ingestion framework + inline SE section |
| 1.4 | Set up logging framework      | development-standards.md SS6 | `src/utils/logging_config.py`               | Structured JSON logs with required fields                      |
| 1.5 | Set up test infrastructure    | development-standards.md SS5 | `tests/` directory, fixtures, conftest.py   | `pytest` runs green with empty test suite                      |
| 1.6 | Docker Compose setup          | LLD SS9.1                    | `docker-compose.yaml`                       | Spark, DuckDB, Marquez, Grafana containers start               |
| 1.7 | Airflow DAG skeleton          | LLD SS4.1                    | `dags/patient360_hourly_v1.py`              | DAG visible in Airflow UI; imports ingestion factory (no tasks yet) |
| 1.8 | Define StructType schemas     | DMS SS2                      | `src/config/schemas.py`                     | All 13 Bronze StructType schemas defined                       |


**Dependencies**: None (foundation phase).

**Risks**: Docker networking configuration for Spark + Marquez + Grafana may require iteration.

---

## Phase 2: Bronze Layer -- Config-Driven Ingestion with Inline SE (Sprint 3-4)

**Goal**: Build the config-driven ingestion framework with inline SE validation and reconciliation_bronze for cross-table checks.

This phase implements LLD Decisions 6-11: Bronze-only scope, per-table YAML configs, TaskGroup factory, SparkSubmitOperator wrapper, convention-based DQ discovery, default+override empty-input behavior. DQ checks are executed inline within each task via spark-expectations action_if_failed (fail/drop/ignore).


| #   | Task                                | LLD Section       | Deliverable                                          | Acceptance Criteria                                                        |
| --- | ----------------------------------- | ----------------- | ---------------------------------------------------- | -------------------------------------------------------------------------- |
| 2.1 | Create per-table YAML configs       | LLD SS2.3, SS5.1   | `src/config/tables/*.yaml` (13 files)                | Each YAML defines source, schema_ref, output_path, empty_input_behavior, dq_rules_table, action_if_failed |
| 2.2 | Implement generic ingestion runner  | LLD SS2.3          | `src/pipelines/bronze/ingestion_runner.py`           | Reads YAML config arg, reads source, adds metadata, enforces schema, calls SE inline (row_dq + agg_dq), writes Delta with `replaceWhere` |
| 2.3 | Implement SparkSubmitOperator wrapper | LLD SS2.3, D9    | `src/pipelines/bronze/spark_submit_wrapper.py`       | Thin wrapper that passes `--config-path` to ingestion runner; sets Spark params from pipeline config |
| 2.4 | Implement TaskGroup factory         | LLD SS2.3, D8     | `src/pipelines/bronze/ingestion_factory.py`          | Scans `config/tables/`, creates TaskGroup with 1 SparkSubmitWrapper task per YAML file |
| 2.5 | Wire factory into DAG               | LLD SS4.2          | Updated `dags/patient360_hourly_v1.py`               | DAG shows `bronze_ingestion` TaskGroup with 13 tasks in Airflow UI |
| 2.6 | Implement Bronze DQ rules           | DQS SS2 (Bronze)   | `src/quality/rules/bronze_rules.yaml`                | SE YAML with rules DQ-FLD-001 through DQ-FLD-045; each rule tagged with table name and action_if_failed |
| 2.7 | Implement SE runner (inline mode)   | LLD SS2.3, SS5.4, D10 | `src/quality/se_runner.py`                       | Loads YAML rules, discovers rules by table name convention, executes inline with action_if_failed (fail/drop/ignore), routes rejections to dead-letter |
| 2.8 | Implement `reconciliation_bronze`   | LLD SS5.5          | `src/quality/reconciliation.py` + task in Airflow DAG | Runs query_dq rules (row count reconciliation, freshness, completeness); blocks Silver on CRITICAL failure |
| 2.9 | Dead letter writer                  | LLD SS8.2          | `src/utils/delta_helpers.py`                         | Writes rejected records to Parquet with rejection metadata                 |
| 2.10 | Unit tests: ingestion framework    | LLD SS2.4          | `tests/unit/test_ingestion_runner.py`, `test_ingestion_factory.py` | >= 90% coverage; config loading, schema enforcement, empty-input behavior (fail + write_empty), inline SE action_if_failed |
| 2.11 | Unit tests: DQ convention discovery | LLD SS2.4, D10    | `tests/unit/test_dq_convention.py`                   | Every table in config/tables/ has >= 1 matching rule in bronze_rules.yaml |
| 2.12 | Integration test: Bronze            | LLD SS2.4          | `tests/integration/test_bronze_pipeline.py`          | End-to-end: DuckDB source -> Bronze Delta tables via ingestion framework + inline SE + reconciliation |


**Dependencies**: Phase 1 complete (project structure, config, schemas).

**Milestone**: All 13 source tables land in Bronze Delta via config-driven framework with inline SE validation and reconciliation_bronze passing.

**Key design rationale**: The ingestion framework eliminates 13 individual `ingest_*.py` modules. Inline SE validation within each task provides immediate DQ feedback during ingestion (fail/drop/ignore) without a separate gate task. reconciliation_bronze runs cross-table query_dq checks after all 13 tasks complete.

---

## Phase 3: Silver Dimensions -- SCD Type 2 (Sprint 5)

**Goal**: SCD Type 2 processing for 4 dimension tables with inline SE validation. This is the most complex transformation logic.


| #   | Task                             | LLD Section          | Deliverable                                       | Acceptance Criteria                                                        |
| --- | -------------------------------- | -------------------- | ------------------------------------------------- | -------------------------------------------------------------------------- |
| 3.1 | SCD2 generic merge function      | LLD SS2.3             | `src/transforms/scd2.py`                          | SHA-256 hash; Delta MERGE INTO; version management                         |
| 3.2 | `transform_patients_silver`      | LLD SS5.2             | `src/pipelines/silver/transform_patients.py`      | SCD2 on patients; PHI columns dropped; derived fields computed; inline SE (action_if_failed: fail) |
| 3.3 | `transform_organizations_silver` | LLD SS5.2             | `src/pipelines/silver/transform_organizations.py` | SCD2 on organizations; inline SE (action_if_failed: fail)                  |
| 3.4 | `transform_providers_silver`     | LLD SS5.2             | `src/pipelines/silver/transform_providers.py`     | SCD2 on providers; inline SE (action_if_failed: fail)                      |
| 3.5 | `transform_payers_silver`        | LLD SS5.2             | `src/pipelines/silver/transform_payers.py`        | SCD2 on payers; inline SE (action_if_failed: fail)                         |
| 3.6 | Code system mappings             | STM Tab:Code Systems | `src/transforms/code_systems.py`                  | HL7 gender, SNOMED encounter class, condition status                       |
| 3.7 | Derived fields module            | DRD SS5.2             | `src/transforms/derived_fields.py`                | calculated_age, medication_status, is_30_day_readmission, total_visit_cost |
| 3.8 | Unit tests: SCD2                 | LLD SS2.4             | `tests/unit/test_scd2.py`                         | New record, unchanged record, changed record, multiple changes             |
| 3.9 | Unit tests: Derived fields       | LLD SS2.4             | `tests/unit/test_derived_fields.py`               | Edge cases: NULL dates, deceased patients, zero costs                      |


**Dependencies**: Phase 2 complete (Bronze layer providing input data).

**Risks**: SCD2 merge logic complexity -- ensure hash includes all tracked columns per DMS SS6.

---

## Phase 4: Silver Facts + Reconciliation (Sprint 6)

**Goal**: All 9 Silver fact tables with inline SE validation and reconciliation_silver for cross-table checks.


| #    | Task                             | LLD Section       | Deliverable                                       | Acceptance Criteria                                   |
| ---- | -------------------------------- | ----------------- | ------------------------------------------------- | ----------------------------------------------------- |
| 4.1  | `transform_encounters_silver`    | LLD SS5.2          | `src/pipelines/silver/transform_encounters.py`    | FK to patients, organizations, providers validated; inline SE (action_if_failed: fail) |
| 4.2  | `transform_conditions_silver`    | LLD SS5.2          | `src/pipelines/silver/transform_conditions.py`    | FK validated; inline SE (action_if_failed: drop)      |
| 4.3  | `transform_medications_silver`   | LLD SS5.2          | `src/pipelines/silver/transform_medications.py`   | FK validated; medication_status derived; inline SE (action_if_failed: drop) |
| 4.4  | `transform_observations_silver`  | LLD SS5.2          | `src/pipelines/silver/transform_observations.py`  | Largest table (4.4M rows); partition tuning; inline SE (action_if_failed: drop) |
| 4.5  | `transform_allergies_silver`     | LLD SS5.2          | `src/pipelines/silver/transform_allergies.py`     | Safety critical; NULL severity -> "Unknown"; inline SE (action_if_failed: fail) |
| 4.6  | `transform_immunizations_silver` | LLD SS5.2          | `src/pipelines/silver/transform_immunizations.py` | FK validated; inline SE (action_if_failed: drop)      |
| 4.7  | `transform_procedures_silver`    | LLD SS5.2          | `src/pipelines/silver/transform_procedures.py`    | FK validated; inline SE (action_if_failed: drop)      |
| 4.8  | `transform_claims_silver`        | LLD SS5.2          | `src/pipelines/silver/transform_claims.py`        | FK validated; billing domain; inline SE (action_if_failed: drop) |
| 4.9  | `transform_careplans_silver`     | LLD SS5.2          | `src/pipelines/silver/transform_careplans.py`     | FK validated; inline SE (action_if_failed: drop)      |
| 4.10 | Silver DQ rules                  | DQS SS2 (Silver)   | `src/quality/rules/silver_rules.yaml`             | SE YAML with rules DQ-FLD-046 through DQ-FLD-104; each rule has action_if_failed |
| 4.11 | `reconciliation_silver`          | LLD SS5.5          | Task in Airflow DAG                               | Runs query_dq rules (row count, FK orphan cross-check, SCD2 version sanity); blocks Gold on CRITICAL failure |
| 4.12 | Integration test: Silver         | LLD SS2.4          | `tests/integration/test_silver_pipeline.py`       | Bronze -> Silver with inline SE + reconciliation_silver passing |


**Dependencies**: Phase 3 complete (dimension tables available for FK validation).

**Priority note**: `transform_allergies_silver` (4.5) should be implemented and tested first within this phase due to its safety-critical nature [DRD SS1.3].

---

## Phase 5: Gold Layer + Reconciliation (Sprint 7)

**Goal**: Three consumer-ready denormalized tables with inline SE validation and reconciliation_gold for cross-table checks.


| #   | Task                          | LLD Section     | Deliverable                                            | Acceptance Criteria                                                |
| --- | ----------------------------- | --------------- | ------------------------------------------------------ | ------------------------------------------------------------------ |
| 5.1 | `build_patient_summary_gold`  | LLD SS5.3        | `src/pipelines/gold/build_patient_summary.py`          | ARRAY for allergies, conditions, medications; broadcast dim joins; inline SE (action_if_failed: fail) |
| 5.2 | `build_clinical_history_gold` | LLD SS5.3        | `src/pipelines/gold/build_patient_clinical_history.py` | Full encounter history with readmission flags; inline SE (action_if_failed: fail) |
| 5.3 | `build_billing_summary_gold`  | LLD SS5.3        | `src/pipelines/gold/build_patient_billing_summary.py`  | Cost data; billing role only; inline SE (action_if_failed: fail)   |
| 5.4 | Gold DQ rules                 | DQS SS2 (Gold)   | `src/quality/rules/gold_rules.yaml`                    | SE YAML including ARRAY validations DQ-FLD-105 through DQ-FLD-140+; action_if_failed: fail for all |
| 5.5 | `reconciliation_gold`         | LLD SS5.5        | Task in Airflow DAG                                    | Runs query_dq rules (row count, patient completeness = 5,767, allergy completeness); blocks consumer access on CRITICAL |
| 5.6 | Integration test: Gold        | LLD SS2.4        | `tests/integration/test_gold_pipeline.py`              | Silver -> Gold with inline SE + reconciliation_gold passing        |
| 5.7 | End-to-end test               | LLD SS2.4        | `tests/integration/test_e2e_pipeline.py`               | DuckDB source -> Bronze -> Silver -> Gold; all inline SE checks pass; all reconciliation tasks green |


**Dependencies**: Phase 4 complete (all Silver tables available).

**Milestone**: Full pipeline functional. All 3 Gold consumer tables populated with correct data.

---

## Phase 6: Observability + Monitoring (Sprint 8)

**Goal**: Lineage tracking, metrics collection, dashboards, and alerting.


| #   | Task                              | LLD Section      | Deliverable                                 | Acceptance Criteria                                          |
| --- | --------------------------------- | ---------------- | ------------------------------------------- | ------------------------------------------------------------ |
| 6.1 | OpenLineage integration           | LLD SS4.2, SS10.1 | `emit_lineage` task; `src/utils/metrics.py` | Lineage events emitted to Marquez; visible in Marquez UI     |
| 6.2 | OpenTelemetry metrics             | LLD SS10.1        | `emit_metrics` task; `src/utils/metrics.py` | Pipeline runtime, row counts, DQ scores pushed to Prometheus |
| 6.3 | Grafana Pipeline Health dashboard | LLD SS10.2        | Grafana dashboard JSON                      | Runtime trend, task status, success/failure rate             |
| 6.4 | Grafana DQ Scores dashboard       | LLD SS10.2        | Grafana dashboard JSON                      | DQ pass rates by layer, table, severity (inline SE metrics)  |
| 6.5 | Grafana SLA Tracking dashboard    | LLD SS10.2        | Grafana dashboard JSON                      | Data freshness, query response p90                           |
| 6.6 | Alerting rules                    | LLD SS10.3        | Grafana alerting configuration              | PagerDuty for CRITICAL; Slack for WARNING                    |
| 6.7 | Allergy escalation path           | LLD SS8.4, DQS SS1 | Alert routing configuration                 | Allergy DQ failures route to PagerDuty + Clinical Ops        |


**Dependencies**: Phase 5 complete (pipeline producing data for monitoring).

---

## Phase 7: Deployment + Rollback (Sprint 9)

**Goal**: CI/CD pipeline, environment promotion, and rollback procedures.


| #   | Task                       | LLD Section | Deliverable                   | Acceptance Criteria                               |
| --- | -------------------------- | ----------- | ----------------------------- | ------------------------------------------------- |
| 7.1 | GitHub Actions CI pipeline | LLD SS9.2    | `.github/workflows/ci.yaml`   | Lint + unit test (>= 90% coverage) on PR; integration test on merge |
| 7.2 | Docker image build         | LLD SS9.2    | Dockerfile + build workflow   | `python:3.11-slim` base; health check endpoint    |
| 7.3 | DEV auto-deploy            | LLD SS9.2    | Deploy workflow               | Auto-deploy on merge to main                      |
| 7.4 | STAGING promotion          | LLD SS9.2    | Manual approval workflow      | Integration tests run in STAGING                  |
| 7.5 | PROD promotion             | LLD SS9.2    | Manual approval + 2 reviewers | STAGING tests + DQ threshold check                |
| 7.6 | Delta RESTORE runbook      | LLD SS9.3    | Operational runbook           | Step-by-step RESTORE commands for Gold tables     |
| 7.7 | Pipeline re-run procedure  | LLD SS9.3    | Operational runbook           | Airflow trigger for specific ds dates             |
| 7.8 | Health check endpoint      | LLD SS9.4    | `/health` on Spark driver     | Returns 200 when driver is healthy                |


**Dependencies**: Phase 6 complete (monitoring in place for deployment validation).

---

## Phase 8: Hardening + Performance (Sprint 10)

**Goal**: Performance optimization, security hardening, and production readiness.


| #   | Task                             | LLD Section                 | Deliverable                       | Acceptance Criteria                                                 |
| --- | -------------------------------- | --------------------------- | --------------------------------- | ------------------------------------------------------------------- |
| 8.1 | Performance tuning: observations | LLD SS6.5                    | Tuned shuffle partitions          | observations table processes within 8 min                           |
| 8.2 | Broadcast join optimization      | LLD SS6.2                    | `broadcast()` hints in Gold tasks | Dimension joins use broadcast; no shuffle                           |
| 8.3 | Caching implementation           | LLD SS6.4                    | Cache calls in Gold tasks         | clinical_patients and clinical_encounters cached across Gold builds |
| 8.4 | Delta VACUUM + OPTIMIZE          | LLD SS3.1                    | Scheduled maintenance tasks       | Weekly VACUUM (7-day retention); auto-compact in PROD               |
| 8.5 | Load testing                     | DRD SS4.3                    | Load test results                 | Pipeline completes within 45 min under normal load                  |
| 8.6 | Security review                  | DRD SS7                      | Security checklist                | PHI dropped at Silver boundary; SSN never in Silver/Gold            |
| 8.7 | Documentation                    | development-standards.md SS7 | READMEs per module                | Docstrings, CHANGELOG, operational runbooks                         |
| 8.8 | Coverage audit                   | LLD SS2.4                    | Coverage report                   | >= 90% unit; 100% CRITICAL DQ rules                                 |


**Dependencies**: Phase 7 complete (deployment pipeline available).

**Milestone**: Production-ready pipeline. All acceptance criteria met. Go/no-go decision.

---

## Requirement Coverage by Phase


| Phase | Requirements Covered                                                                              | Key SLAs Addressed            |
| ----- | ------------------------------------------------------------------------------------------------- | ----------------------------- |
| 1     | -- (foundation)                                                                                   | --                            |
| 2     | FR-4 (ingest 13 tables), NFR-5 (idempotency), NFR-12 (read-only)                                  | --                            |
| 3     | FR-5 (SCD2 tracking), FR-6 (derived fields), NFR-6 (SSN masking)                                  | --                            |
| 4     | FR-7 (referential integrity), FR-8 (allergy never suppressed), FR-9 (default values)              | Zero missed allergies         |
| 5     | FR-1 (patient search), FR-2 (clinical history), FR-3 (billing summary), NFR-4 (100% completeness) | < 2s query, 100% patients     |
| 6     | FR-10 (lineage), NFR-7 (audit trail)                                                              | 1-hour freshness SLA tracking |
| 7     | NFR-10 (RTO 4h), NFR-11 (RPO 24h)                                                                 | Recovery SLAs                 |
| 8     | NFR-1 (2s response), NFR-2 (1h freshness)                                                         | All production SLAs           |


---

## Risk Mitigation per Phase


| Phase | Key Risk                                   | Mitigation                                                                |
| ----- | ------------------------------------------ | ------------------------------------------------------------------------- |
| 2     | YAML config schema drift across 13 files   | Unit test validates all 13 configs parse against a schema; CI enforces    |
| 2     | Convention-based DQ misses rules silently   | Unit test asserts every table config has >= 1 matching rule in bronze_rules.yaml |
| 2     | Inline SE action_if_failed misconfigured   | Unit test verifies critical tables use `fail`, non-critical use `drop`    |
| 3     | SCD2 hash mismatch causing false changes   | Unit test with known input/output pairs; verify hash columns match DMS SS6 |
| 4     | Observations table (4.4M rows) causing OOM | Tune shuffle partitions to 8; monitor memory in DEV                       |
| 5     | ARRAY Gold builds timing out               | Pre-aggregate arrays in subquery before join; cache intermediate results  |
| 6     | Marquez/Grafana connectivity issues        | Circuit breaker: lineage/metrics are non-blocking [LLD SS8.5]              |
| 7     | Failed deployment to STAGING/PROD          | Delta RESTORE provides instant rollback; pipeline re-run for correctness  |
| 8     | Performance regression under load          | Establish baseline metrics in Phase 6; alert on degradation               |
