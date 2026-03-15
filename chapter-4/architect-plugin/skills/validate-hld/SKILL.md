---
name: validate-hld
description: >
  Validates a High-Level Design document against completeness and quality
  standards. Checks all required sections, DRD traceability, layer specs,
  technology stack, CDC strategy, and capacity planning. Reports issues
  as CRITICAL, WARNING, or INFO with suggested fixes. Use when the user
  asks to validate, check, review, or verify an HLD.
argument-hint: "[path-to-hld-file]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# Validate High-Level Design Document

> **Skill Inheritance**: This skill inherits behavioral rules from
> `architect-agent.md`. The traceability enforcement, pitfall prevention,
> and session memory requirements apply during skill execution.

You are a Data Architect Agent. Validate an HLD against completeness and
quality standards.

## Step 1: Run the validator

Run the Python validator script on the specified file or all HLDs:

```bash
# Single file
uv run python chapter-4/architect-plugin/skills/validate-hld/scripts/validate_hld.py $ARGUMENTS

# All HLDs in the latest version folder
LATEST_HLD_DIR=$(ls -d chapter-4/outputs/hld/v* | sort -V | tail -1)
uv run python chapter-4/architect-plugin/skills/validate-hld/scripts/validate_hld.py --all "$LATEST_HLD_DIR"
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks downstream work)
- All 8 required sections present
- Metadata complete (version, date, author, status, DRD reference)
- Layer specifications non-empty (Bronze, Silver, Gold)
- Technology stack table present with entries

### WARNING (needs attention)
- DRD traceability — design decisions cite DRD requirements
- CDC strategy specifies detection methods
- Capacity projections include numeric values
- Security references compliance/regulatory/sensitive-data controls
- Pattern selection includes justification
- Decision documentation present

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- Mermaid diagrams present
- Cost estimates included

## Step 2.5: Fix CRITICAL issues before presenting

If the validator reports CRITICAL issues, **fix them using the Edit tool
before presenting results to the user**. For content requiring user
judgment, use `AskUserQuestion`.

After fixing, re-run the validator to confirm CRITICALs are resolved.

## Step 3: Report findings

Call `AskUserQuestion` to ask which warnings the user wants fixed:

```json
{
  "questions": [
    {
      "question": "The validator found warnings. Which would you like me to fix?",
      "header": "Warnings",
      "multiSelect": false,
      "options": [
        { "label": "Fix all", "description": "Fix all warnings now" },
        { "label": "High-priority", "description": "Fix only high-priority warnings" },
        { "label": "Report only", "description": "Leave warnings for later, just report them" }
      ]
    }
  ]
}
```

Format as a checklist:

```
Validation Results for HLD-2026-03-14-pipeline-v1.md

CRITICAL (must fix):
- [x] All critical issues have been auto-fixed

WARNING (should fix):
- [ ] Section 8: CDC strategy missing fallback methods

INFO (nice to have):
- [ ] Section 5: No cost estimates included

Summary: 0 critical (fixed), 1 warning, 1 info
```

## Step 4: Session memory

**Always write session notes.** Write to
`chapter-4/architect-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was validated (HLD filename)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues
