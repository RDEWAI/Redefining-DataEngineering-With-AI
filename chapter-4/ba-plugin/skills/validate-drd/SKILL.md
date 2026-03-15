---
name: validate-drd
description: >
  Validates a Data Requirements Document against completeness and quality
  standards. Checks all required sections, metadata, source systems, consumers,
  SLAs, and business rules. Reports issues as CRITICAL, WARNING, or INFO with
  suggested fixes. Use when the user asks to validate, check, review, or
  verify a DRD.
argument-hint: "[path-to-drd-file]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# Validate Data Requirements Document

> **Skill Inheritance**: This skill inherits behavioral rules from `ba-agent.md`.
> The elicitation protocol, database gate, anti-pattern enforcement, and session
> memory requirements apply during skill execution. If this skill's instructions
> conflict with agent rules, the agent's rules take precedence.

You are a Business Analyst Agent. Validate a DRD against completeness and
quality standards.

## Step 1: Run the validator

Run the Python validator script on the specified file or all DRDs:

```bash
# Single file
uv run python chapter-4/ba-plugin/skills/validate-drd/scripts/validate_drd.py $ARGUMENTS

# All DRDs in the output directory
uv run python chapter-4/ba-plugin/skills/validate-drd/scripts/validate_drd.py --all chapter-4/outputs/drd/
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks downstream work)
- All 9 required sections present (including Section 7: Regulatory and Compliance)
- Version metadata complete (version, date, author, status)
- At least one source system documented
- At least one data consumer identified
- Content sections (2-5, 7) are not empty

### WARNING (needs attention)
- SLAs defined with numeric targets
- Critical fields identified
- Business rules documented
- Freshness requirements specified
- Open questions tracked
- Tolerance thresholds set
- Regulatory subsections (7.1-7.5): applicable regulations, data classification,
  retention periods, access controls, audit requirements
- Vague language detected (anti-patterns: "real-time", "fast", "all data",
  "comprehensive", "up-to-date", "all users", "standard compliance")

### INFO (suggestions for improvement)
- Placeholder text remaining (`[TO BE DETERMINED]`, `[TBD]`, `[NEEDS VERIFICATION]`)
  — also checks that placeholders include owner name and due date
- Approval section empty
- Edge cases not documented

## Step 2.5: Fix CRITICAL issues before presenting

If the validator reports CRITICAL issues, **fix them using the Edit tool before
presenting results to the user**. The goal is to hand the user a clean DRD with
only WARNINGs and INFOs to review.

- For structural issues (missing sections, incomplete metadata): add the missing
  structure with `[TO BE DETERMINED]` placeholders
- For content issues that require user judgment (e.g., which source system to add,
  what consumer to name): use `AskUserQuestion` to ask the user before fixing
- After fixing, re-run the validator to confirm CRITICALs are resolved

## Step 3: Report findings

For each remaining issue, provide:
1. The section with the problem
2. What is missing or incorrect
3. A suggested fix in **business-friendly language**

Use `AskUserQuestion` to present the findings and ask the user which WARNINGs
they want to address:

```
AskUserQuestion: "Validation found {N} warnings. Which would you like me to fix?"

Options:
- "Fix all warnings"
- "Fix only the high-priority ones (SLAs, critical fields)"
- "Leave warnings as-is — I'll handle them later"
```

Format the report as a checklist the user can act on:

```
Validation Results for DRD-2026-01-29-patient-360.md

CRITICAL (must fix):
- [x] All critical issues have been auto-fixed

WARNING (should fix):
- [ ] Section 4.3: No SLAs defined. Add response time and availability targets.

INFO (nice to have):
- [ ] Section 5.4: No edge cases documented. Consider what happens with missing data.

Summary: 0 critical (fixed), 1 warning, 1 info
```

## Step 4: Session memory

**Always write session notes regardless of validation outcome.** Write to
`chapter-4/ba-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was validated (DRD filename)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied (bulleted list)
- Key decisions made and their rationale
- Remaining issues the user chose not to address (with assigned owners and due dates)
