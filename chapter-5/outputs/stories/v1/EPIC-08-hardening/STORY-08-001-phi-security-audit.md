# STORY-08-001: PHI / security audit — log scrubbing + dead-letter inspection

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening — Security, Documentation, Maintenance |
| **Story Type** | hardening |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 6 |
| **Dependencies** | STORY-07-004 |
| **Status** | To Do |

## User Story

As a Compliance / Data Engineer, I want all logs and dead-letter paths audited for plain-text PHI so that the pipeline cannot leak protected health information.

## Description

Audit `utils/logging_config.py` to ensure PHI columns (`first_name`, `last_name`, `ssn`, `address`, `phone`, etc.) are masked in INFO/WARN/ERROR logs. Verify dead-letter (LLD §8.4) only stores `_raw_record` (intentional pre-validation capture) — no parsed PHI columns. Document audit results.

## Acceptance Criteria

- [ ] PHI scrubbing helper applied in all `get_logger().info|warn|error(...)` call sites that touch DataFrames [LLD §10.1]
- [ ] Audit script `scripts/phi_audit.py` greps source for direct PHI column logging and exits 0 [LLD §10.1]
- [ ] Dead-letter records contain only `_raw_record` + provenance per LLD §8.4 schema [LLD §8.4]
- [ ] Audit report written to `patient_360/docs/phi-audit-report.md` [LLD §10.1]

## Technical Notes

- **Upstream references**: LLD §8.4 (DLQ schema), §10.1 (logging conventions); DRD §1.3 (PHI sensitivity)
- **Implementation hints**: Add a redaction utility to `utils/logging_config.py` that masks known PHI columns by name.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §8.4, §10.1 |
| DMS | §3 Bronze (PHI columns) |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | redaction helper masks PHI columns | `pytest patient_360/tests/utils/test_phi_redaction_unit.py` |
| Manual | audit report inspected | Review `patient_360/docs/phi-audit-report.md` |

## Verification

```yaml
AC1:
  - grep: {file: "patient_360/src/patient_360/utils/logging_config.py", pattern: 'redact|mask|scrub'}
AC2:
  - file_exists: "patient_360/scripts/phi_audit.py"
  - manual: "run scripts/phi_audit.py and verify exit 0 with zero findings"
AC3:
  - manual: "ls warehouse/dev/dead-letter/ shows only _raw_record + provenance columns"
AC4:
  - file_exists: "patient_360/docs/phi-audit-report.md"
```

## How to Test (User)

### Prerequisites

- STORY-07-004 complete

### Steps

1. `cd patient_360 && uv run python scripts/phi_audit.py`
2. `cd patient_360 && uv run pytest tests/utils/test_phi_redaction_unit.py -v`
3. `cat patient_360/docs/phi-audit-report.md`

### Expected outcome

- Step 1: 0 findings
- Step 2: redaction tests pass
- Step 3: audit report readable; signed off

## Documentation Updates

- [ ] N/A — security-internal; report linked from `patient_360/README.md` § "Compliance"
