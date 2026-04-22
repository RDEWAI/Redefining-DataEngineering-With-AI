# STORY-05-004: Implement Gold DQ Rules YAML

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Layer + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 7 |
| **Dependencies** | STORY-02-006 |
| **Status** | To Do |

## User Story

As a data quality engineer, I want the Gold layer SE YAML rules file so that inline DQ validation enforces consumer-table quality standards including ARRAY validations.

## Description

Create `src/quality/rules/gold_rules.yaml` containing DQ rules DQ-FLD-105 through DQ-FLD-140+ for all 3 Gold tables. Rules include ARRAY column validations (non-empty arrays for patients with known conditions), patient completeness checks (5,767 patients), and billing amount validations. All Gold rules use action_if_failed: fail since Gold tables are consumer-facing.

## Acceptance Criteria

- [ ] `gold_rules.yaml` contains rules DQ-FLD-105 through DQ-FLD-140+ [DQS §2]
- [ ] ARRAY validation rules for patient_summary (allergies, conditions, medications arrays) [DQS §2]
- [ ] Patient completeness rule: exactly 5,767 patients in output [DQS §2, DRD SS4.4]
- [ ] All rules use action_if_failed: fail [DQS §2]
- [ ] Rules compatible with spark-expectations >= 2.6.0 YAML format [LLD §5.4]

## Technical Notes

- **Upstream references**: DQS SS2 (Gold rules), LLD SS5.4
- **Implementation hints**: ARRAY validations in SE can check `size(array_col) > 0` or `array_col IS NOT NULL`. Completeness is an agg_dq rule: `count(DISTINCT patient_id) = 5767`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.4 |
| DMS | SS5 (Gold table schemas) |
| STM | -- |
| DQS | SS2 (Gold rules DQ-FLD-105 to DQ-FLD-140+) |
