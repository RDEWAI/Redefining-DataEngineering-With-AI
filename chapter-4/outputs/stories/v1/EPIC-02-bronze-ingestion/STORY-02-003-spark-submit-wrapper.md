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

Implement `src/pipelines/bronze/spark_submit_wrapper.py` -- a thin wrapper around Airflow's SparkSubmitOperator. The wrapper accepts a YAML config path, reads pipeline config for Spark resource parameters (driver memory, executor memory, cores, executors from the compute section), and creates a configured SparkSubmitOperator that invokes the `ingestion_runner.py` with `--config-path` as the application argument. Spark parameters must be sourced from the pipeline config environment section.

## Acceptance Criteria

- [ ] `spark_submit_wrapper.py` creates SparkSubmitOperator with correct `--config-path` argument [LLD §2.3]
- [ ] Spark resource parameters (memory, cores, executors) sourced from pipeline config compute section [LLD §6.1]
- [ ] Application entry point set to `src.pipelines.bronze.ingestion_runner` [LLD §2.3]
- [ ] Timeout and retry settings applied from per-table YAML config [LLD §8.1]

## Technical Notes

- **Upstream references**: LLD SS2.3 (spark_submit_wrapper contract), LLD SS6.1 (Compute Resources), LLD SS8.1 (Retry Policies)
- **Implementation hints**: Use `airflow.providers.apache.spark.operators.spark_submit.SparkSubmitOperator`. Set `application` to the ingestion runner module path. Pass `--config-path` via `application_args`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.3, SS6.1, SS8.1 |
| DMS | -- |
| STM | -- |
| DQS | -- |
