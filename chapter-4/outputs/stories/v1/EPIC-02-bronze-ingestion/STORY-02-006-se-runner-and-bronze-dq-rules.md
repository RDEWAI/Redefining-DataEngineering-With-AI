# STORY-02-006: Implement SE Runner and Bronze DQ Rules

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 3 |
| **Dependencies** | STORY-02-002 |
| **Status** | To Do |

## User Story

As a data quality engineer, I want the Spark Expectations runner and Bronze DQ rules YAML so that inline row_dq and agg_dq validation executes within each Bronze ingestion task.

## Description

Implement two components: (1) `src/quality/se_runner.py` -- a wrapper around spark-expectations that loads YAML rules, discovers rules by table name convention, executes inline row_dq and agg_dq checks with configurable action_if_failed, routes rejections to dead-letter paths, and emits pass/fail metrics. (2) `src/quality/rules/bronze_rules.yaml` -- the SE YAML rules file containing DQ rules DQ-FLD-001 through DQ-FLD-045 for all 13 Bronze tables, with each rule tagged by table name for convention-based discovery. The SE runner must support three action_if_failed modes: fail (raise exception), drop (quarantine + continue), and ignore (log + continue).

## Acceptance Criteria

- [ ] `se_runner.py` loads SE YAML rules and discovers rules by table name convention [LLD §2.3, DQS SS2]
- [ ] Inline execution supports row_dq and agg_dq rule types [LLD §5.4]
- [ ] action_if_failed: fail raises exception halting the task [LLD §5.4]
- [ ] action_if_failed: drop quarantines failing rows to dead-letter path and continues [LLD §5.4, SS8.2]
- [ ] action_if_failed: ignore logs violations and emits metrics without blocking [LLD §5.4]
- [ ] `bronze_rules.yaml` contains rules DQ-FLD-001 through DQ-FLD-045 [DQS §2]
- [ ] Each rule tagged with table name for convention-based discovery [LLD §2.3]
- [ ] Critical table rules (patients, encounters, allergies) use action_if_failed: fail [DQS §2, DRD SS1.3]
- [ ] DQ pass/fail metrics emitted via OpenTelemetry [LLD §5.4]

## Technical Notes

- **Upstream references**: LLD SS2.3 (se_runner contract), LLD SS5.4 (Inline SE Validation), DQS SS2 (Bronze DQ rules), LLD SS8.2 (Dead Letter)
- **Implementation hints**: Use `spark-expectations` library (>= 2.6.0). Rules YAML must follow SE schema with `rule_type`, `table_name`, `rule`, `action_if_failed`, and `description` fields. Convention discovery: filter rules where `table_name == config.dq_rules_table`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.3, SS5.4, SS8.2 |
| DMS | SS4 (Bronze table schemas for rule context) |
| STM | -- |
| DQS | SS2 (Bronze rules DQ-FLD-001 to DQ-FLD-045) |
