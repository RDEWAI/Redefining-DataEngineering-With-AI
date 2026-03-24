# STORY-03-007: Implement Derived Fields Module

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions -- SCD Type 2 |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 5 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want a derived fields module that computes calculated_age, medication_status, is_30_day_readmission, and total_visit_cost so that Silver transforms include all business-defined computed columns.

## Description

Implement `src/transforms/derived_fields.py` with functions for: (1) `calculated_age` -- compute from birthdate and deathdate (or current date if alive), (2) `medication_status` -- derive active/completed/stopped from medication dates, (3) `is_30_day_readmission` -- flag encounters within 30 days of prior discharge, (4) `total_visit_cost` -- sum of claim line items per encounter. Each function must handle edge cases: NULL dates, deceased patients (age at death), zero costs, and boundary conditions for readmission windows.

## Acceptance Criteria

- [ ] `calculated_age` computes correctly for living and deceased patients [DRD §5.2]
- [ ] `medication_status` derives active/completed/stopped from date fields [DRD §5.2]
- [ ] `is_30_day_readmission` flags encounters within 30 days of prior discharge [DRD §5.2]
- [ ] `total_visit_cost` sums claim line items per encounter [DRD §5.2]
- [ ] NULL date handling: NULL birthdate returns NULL age, NULL deathdate assumes alive [DRD §5.2]
- [ ] Unit tests cover edge cases: NULL dates, deceased patients, zero costs, boundary dates [LLD §2.4]

## Technical Notes

- **Upstream references**: DRD SS5.2 (derived field requirements), LLD SS2.1 (transforms directory)
- **Implementation hints**: Use PySpark functions: `datediff`, `months_between`, `when/otherwise`. Readmission calculation requires window functions partitioned by patient_id and ordered by encounter date. Total visit cost requires joining encounters with claims.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.1 (transforms directory) |
| DMS | SS5 (Silver schemas with derived columns) |
| STM | Tab:Bronze-to-Silver (derived field formulas) |
| DQS | SS2 (DQ rules on derived fields) |
