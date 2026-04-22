# STORY-01-004: Set Up Structured Logging Framework

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 1 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want structured JSON logging with standard fields so that pipeline execution events are machine-parseable for monitoring and debugging.

## Description

Implement `src/utils/logging_config.py` providing a structured JSON logging configuration. All log entries must include: timestamp, level, logger name, message, and pipeline context fields (pipeline_run_id, dag_id, task_id, ds). The logging configuration must be importable by all pipeline modules and must integrate with Python's standard `logging` module. Log levels must be configurable per environment.

## Acceptance Criteria

- [ ] `logging_config.py` produces structured JSON log output [development-standards.md SS6]
- [ ] Log entries include timestamp, level, logger_name, message, pipeline_run_id, dag_id, task_id, ds [development-standards.md SS6]
- [ ] Log level is configurable per environment (DEBUG for DEV, INFO for STAGING/PROD) [LLD §7]
- [ ] Unit tests verify JSON structure and required fields are present [LLD §2.4]

## Technical Notes

- **Upstream references**: development-standards.md SS6, LLD SS2.1 (utils directory)
- **Implementation hints**: Use Python's `logging.config.dictConfig` with a JSON formatter. Consider `python-json-logger` library for cleaner structured output.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.1 (Project Structure -- utils) |
| DMS | -- |
| STM | -- |
| DQS | -- |
