---
name: validate-drd
description: >
  Validates a Data Requirements Document against completeness and quality
  standards. Checks all required sections, metadata, source systems, consumers,
  SLAs, and business rules. Reports issues as CRITICAL, WARNING, or INFO with
  suggested fixes. Use when the user asks to validate, check, review, or
  verify a DRD.
argument-hint: "[path-to-drd-file]"
allowed-tools: Read, Bash, Glob
---

# Validate Data Requirements Document

You are a Business Analyst Agent. Validate a DRD against completeness and
quality standards.

## Step 1: Run the validator

Run the Python validator script on the specified file or all DRDs:

```bash
# Single file
uv run python chapter-3/ba-agent-drd/skills/validate-drd/scripts/validate_drd.py $ARGUMENTS

# All DRDs in the output directory
uv run python chapter-3/ba-agent-drd/skills/validate-drd/scripts/validate_drd.py --all chapter-3/outputs/drd/
```

## Step 2: Interpret results

The validator checks 14 rules across three severity levels:

### CRITICAL (blocks downstream work)
- All 8 required sections present
- Version metadata complete (version, date, author, status)
- At least one source system documented
- At least one data consumer identified
- Content sections (2-5) are not empty

### WARNING (needs attention)
- SLAs defined
- Critical fields identified
- Business rules documented
- Freshness requirements specified
- Open questions tracked
- Tolerance thresholds set

### INFO (suggestions for improvement)
- Placeholder text remaining (`[TO BE DETERMINED]`, `[TBD]`, `[NEEDS VERIFICATION]`)
- Approval section empty
- Edge cases not documented

## Step 3: Report findings

For each issue found, provide:
1. The section with the problem
2. What is missing or incorrect
3. A suggested fix in **business-friendly language**

Format the report as a checklist the user can act on:

```
Validation Results for DRD-2026-01-29-patient-360.md

CRITICAL (must fix):
- [ ] Section 2.1: No source systems documented. Add the EHR and lab systems.

WARNING (should fix):
- [ ] Section 4.3: No SLAs defined. Add response time and availability targets.

INFO (nice to have):
- [ ] Section 5.4: No edge cases documented. Consider what happens with missing data.

Summary: 1 critical, 1 warning, 1 info
```
