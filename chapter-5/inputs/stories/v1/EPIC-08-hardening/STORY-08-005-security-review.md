# STORY-08-005: Security Review and PHI Verification

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening + Performance |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 10 |
| **Dependencies** | STORY-07-003 |
| **Status** | To Do |

## User Story

As a data engineer, I want a security review verifying PHI is dropped at the Silver boundary so that HIPAA compliance is enforced and SSN never appears in Silver or Gold tables.

## Description

Perform a comprehensive security review: (1) Verify SSN and other PII columns are dropped at Bronze-to-Silver boundary per DRD SS7. (2) Scan Silver and Gold Delta tables for presence of SSN patterns. (3) Verify dead-letter path access is restricted. (4) Verify no PII in log output. (5) Document the security checklist with pass/fail results.

## Acceptance Criteria

- [ ] SSN column absent from all Silver and Gold tables [DRD §7]
- [ ] PII columns dropped at Bronze-to-Silver boundary [DRD §7, LLD SS5.2]
- [ ] Pattern scan confirms no SSN-like values in Silver/Gold data [DRD §7]
- [ ] Dead letter access restricted to data-ops role [LLD §8.2]
- [ ] No PII in structured log output [development-standards.md SS6]
- [ ] Security checklist documented with results [DRD §7]

## Technical Notes

- **Upstream references**: DRD SS7 (Security and PHI), LLD SS5.2, LLD SS8.2
- **Implementation hints**: SSN pattern: regex `\d{3}-\d{2}-\d{4}`. Scan with Spark SQL: `SELECT * FROM silver_table WHERE col RLIKE '\\d{3}-\\d{2}-\\d{4}'` across all string columns. Document as a runnable test for CI.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2, SS8.2 |
| DMS | SS5 (Silver/Gold schemas -- verify no PII columns) |
| STM | -- |
| DQS | -- |
