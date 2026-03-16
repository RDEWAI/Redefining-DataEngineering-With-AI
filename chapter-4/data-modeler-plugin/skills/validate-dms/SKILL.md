---
name: validate-dms
description: >
  Validates a Data Model Specification document against completeness and quality
  standards. Checks all required sections, YAML schema block validity, SCD
  documentation, naming conventions, and HLD traceability. Reports issues
  as CRITICAL, WARNING, or INFO with suggested fixes. Use when the user
  asks to validate, check, review, or verify a DMS.
argument-hint: "[path-to-dms-file]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# Validate Data Model Specification Document

> **Skill Inheritance**: This skill inherits behavioral rules from
> `data-modeler-agent.md`. The traceability enforcement, pitfall prevention,
> and session memory requirements apply during skill execution.

You are a senior Data Modeler. You sit between the Data Architect (who
produces the HLD) and the Mapping Engineer (who specifies column-level
transformations). Your job is to translate the HLD's layer specifications
into precise, build-ready Data Model Specifications (DMS) that define
concrete schemas for every table at every layer — bronze, silver, and gold.

Validate a DMS against completeness and quality standards.

## Step 1: Run the validator

Run the Python validator script on the specified file or all DMS documents:

```bash
# Single file
uv run python data-modeler-plugin/skills/validate-dms/scripts/validate_dms.py $ARGUMENTS

# All DMS files in the latest version folder
LATEST_DMS_DIR=$(ls -d outputs/dms/v* | sort -V | tail -1)
uv run python data-modeler-plugin/skills/validate-dms/scripts/validate_dms.py --all "$LATEST_DMS_DIR"
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks downstream work)
- All 9 required sections present
- Metadata complete (version, date, author, status, HLD reference)
- Bronze schemas have ≥1 YAML block with `table:` and `columns:` keys
- Silver schemas have ≥1 YAML block with `primary_key:` defined
- Gold schemas have ≥1 YAML block with `grain:` statement
- YAML blocks parse without errors

### WARNING (needs attention)
- HLD traceability — schema decisions cite HLD sections
- SCD type documented for dimension attributes
- Naming conventions section has prefix rules
- Traceability matrix has ≥1 source→target mapping
- Silver columns have `source:` field for lineage
- Gold tables have `foreign_keys:` for fact tables

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- Mermaid ER diagrams present
- All three layers have YAML schema blocks
- Business rule references in silver columns

## DMS Sections Reference

A complete DMS contains these sections:
- **Design Overview**: Modeling approach, layer summary, HLD traceability
- **Bronze Layer Schemas**: Per-table YAML blocks with columns, types, metadata
- **Silver Layer Schemas**: Per-table YAML blocks with PK/FK, transforms, business rules
- **Gold Layer Schemas**: Per-table YAML blocks with grain, SCD, surrogate keys
- **Naming Conventions**: Table prefixes, column naming rules, schema organization
- **SCD Strategy**: Per-dimension attribute SCD type with rationale
- **Physical Design Notes**: Clustering, distribution, compression, partitioning
- **Traceability Matrix**: Gold → Silver → Bronze → Source column lineage
- **Version History**: Version, date, author, changes

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
Validation Results for DMS-2026-03-15-patient-360.md

CRITICAL (must fix):
- [x] All critical issues have been auto-fixed

WARNING (should fix):
- [ ] Section 6: SCD strategy missing for dim_provider.specialty

INFO (nice to have):
- [ ] Section 2: No Mermaid ER diagram for bronze layer

Summary: 0 critical (fixed), 1 warning, 1 info
```

## Step 4: Session memory

**Always write session notes.** Write to
`data-modeler-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was validated (DMS filename)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues
