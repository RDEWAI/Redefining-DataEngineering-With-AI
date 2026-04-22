# STORY-02-003: Implement SparkSubmitOperator Wrapper

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 3 |
| **Dependencies** | STORY-02-002 |
| **Status** | To Do |

## User Story

As a data engineer, I want a thin SparkSubmitOperator wrapper that passes config paths and Spark parameters so that each Bronze task runs on the Spark cluster with correct resource allocation.

## Description

Implement `src/patient_360/bronze/spark_submit_wrapper.py` -- a thin wrapper around Airflow's SparkSubmitOperator. The wrapper accepts a YAML config path, reads pipeline config for Spark resource parameters (driver memory, executor memory, cores, executors from the compute section), and creates a configured SparkSubmitOperator that invokes the `ingestion_runner.py` with `--config-path` as the application argument. Spark parameters must be sourced from the pipeline config environment section.

## Acceptance Criteria

- [ ] `src/patient_360/bronze/spark_submit_wrapper.py` creates SparkSubmitOperator with correct `--config-path` argument [LLD §2.3]
- [ ] Spark resource parameters (memory, cores, executors) sourced from pipeline config compute section [LLD §6.1]
- [ ] Application entry point set to `patient_360.bronze.ingestion_runner` (cookiecutter package name) [LLD §2.3]
- [ ] Timeout and retry settings applied from per-table YAML config [LLD §8.1]

## Technical Notes

- **Upstream references**: LLD §2.3 (spark_submit_wrapper contract), LLD §6.1 (Compute Resources), LLD §8.1 (Retry Policies)
- **Developer plugin**: Use `developer-plugin:create-ingestion STORY-02-003` (story mode) to generate `spark_submit_wrapper.py`.
- **Implementation hints**: Use `airflow.providers.apache.spark.operators.spark_submit.SparkSubmitOperator`. Set `application` to `patient_360.bronze.ingestion_runner` (the cookiecutter package path). Pass `--config-path` via `application_args`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.3, SS6.1, SS8.1 |
| DMS | -- |
| STM | -- |
| DQS | -- |
