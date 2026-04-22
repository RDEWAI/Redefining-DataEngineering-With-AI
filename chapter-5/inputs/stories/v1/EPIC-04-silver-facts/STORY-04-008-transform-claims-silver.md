# STORY-04-008: Transform Claims to Silver

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the claims fact table transformed to Silver with FK validation so that billing records are linked to valid encounters for downstream billing summary.

## Description

Implement `src/pipelines/silver/transform_claims.py` that reads Bronze `synthea_claims`, validates FKs against encounters, and writes to `warehouse/{env}/silver/billing/billing_claims/`. Inline SE with action_if_failed: drop. Rules DQ-FLD-093 to DQ-FLD-094.

## Acceptance Criteria

- [ ] Reads from Bronze and writes to Silver `billing_claims` [LLD §5.2]
- [ ] FK validated against clinical_encounters [DMS §5]
- [ ] Inline SE validates rules DQ-FLD-093 to DQ-FLD-094 with action_if_failed: drop [DQS §2]
- [ ] Empty input writes empty table [LLD §5.2]

## Technical Notes

- **Upstream references**: LLD SS5.2, DQS SS2 (DQ-FLD-093 to DQ-FLD-094)
- **Implementation hints**: Claims feed the billing_summary Gold table. Billing domain schema (`silver/billing/`) separates it from clinical tables.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 |
| DMS | SS5 (billing_claims schema) |
| STM | Tab:Bronze-to-Silver (claims) |
| DQS | SS2 (DQ-FLD-093 to DQ-FLD-094) |
