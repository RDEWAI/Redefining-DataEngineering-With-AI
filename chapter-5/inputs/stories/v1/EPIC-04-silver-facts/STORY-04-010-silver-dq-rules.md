# STORY-04-010: Implement Silver DQ Rules YAML

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-02-006 |
| **Status** | To Do |

## User Story

As a data quality engineer, I want the Silver layer SE YAML rules file so that inline DQ validation executes the correct rules for all 13 Silver tables.

## Description

Create `src/quality/rules/silver_rules.yaml` containing DQ rules DQ-FLD-046 through DQ-FLD-104 for all 13 Silver tables. Each rule must specify table_name, rule_type (row_dq or agg_dq), rule expression, action_if_failed (fail for critical tables, drop for others), severity, and description. Rules cover: not-null constraints, FK referential integrity, data type validations, range checks, SCD2 integrity, and derived field correctness.

## Acceptance Criteria

- [ ] `silver_rules.yaml` contains rules DQ-FLD-046 through DQ-FLD-104 [DQS §2]
- [ ] Each rule tagged with table_name for convention-based discovery [LLD §2.3]
- [ ] Safety-critical tables (patients, encounters, allergies) use action_if_failed: fail [DQS §2]
- [ ] Non-critical tables use action_if_failed: drop [DQS §2]
- [ ] Rule types include row_dq and agg_dq [DQS §2-3]
- [ ] All rules compatible with spark-expectations >= 2.6.0 YAML format [LLD §5.4]

## Technical Notes

- **Upstream references**: DQS SS2 (Silver rules DQ-FLD-046 to DQ-FLD-104), LLD SS5.4
- **Implementation hints**: Reference DQS SS2 for exact rule definitions. SE YAML format: `rules:` list with `rule_type`, `table_name`, `column_name`, `rule`, `action_if_failed`. Can be developed in parallel with Silver transform stories.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.4 |
| DMS | SS5 (Silver table schemas for rule context) |
| STM | -- |
| DQS | SS2 (all Silver rules DQ-FLD-046 to DQ-FLD-104) |
