---
name: validate-dms
description: >
  Validates a Data Model Specification (DMS) document against completeness
  and quality standards. Checks all required sections, YAML schema block
  validity, SCD documentation, naming conventions, and HLD traceability.
  Reports issues as CRITICAL, WARNING, or INFO with suggested fixes.
  Also known as: DMS review, schema quality check, data model audit.
  Input formats: DMS Markdown (.md) file.
  Output format: Validation report with severity-ranked findings.
  Use when the user asks to:
  - Validate, check, review, verify, or audit a DMS
  - Assess DMS completeness or schema quality
  - Find issues or gaps in a data model specification
  - Run quality checks on a DMS before handoff
argument-hint: "[dms-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
---

# Validate Data Model Specification Document

> **Skill Inheritance**: This skill inherits behavioral rules from
> `data-modeler-agent.md`. The traceability enforcement, pitfall prevention,
> and session memory requirements apply during skill execution.

You are a senior Data Modeler. You sit between the Data Architect (who
produces the HLD) and the Mapping Engineer (who specifies column-level
transformations in the Source-to-Target Mapping). Your job is to translate
the HLD's layer specifications into precise, build-ready Data Model
Specifications (DMS) that define concrete schemas for every table at every
layer — bronze, silver, and gold.

**Scope boundary**: The DMS defines *what* the schema looks like (tables,
columns, types, keys, grain, SCD strategy). It does NOT define *how* data
is transformed (STM), *how* nulls are handled (DQS), or *how* data is
physically stored (LLD).

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
- Traceability matrix has ≥1 table-level lineage entry
- Silver columns have `source:` field for lineage
- Silver YAML blocks do not contain `transform:` or `null_handling:` (belongs in STM/DQS)
- Gold tables have `foreign_keys:` for fact tables
- Mermaid diagrams present (holistic ER diagram in §1 + layer architecture flowchart)

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- All three layers have YAML schema blocks
- Business rule references in silver columns

## DMS Sections Reference

A complete DMS contains these sections:
- **Design Overview**: Modeling approach, layer summary, HLD traceability
- **Bronze Layer Schemas**: Per-table YAML blocks with columns, types, metadata
- **Silver Layer Schemas**: Per-table YAML blocks with PK/FK, source references, business rules
- **Gold Layer Schemas**: Per-table YAML blocks with grain, SCD, surrogate keys
- **Naming Conventions**: Table prefixes, column naming rules, schema organization
- **SCD Strategy**: Per-dimension attribute SCD type with rationale
- **Physical Design Notes**: Clustering, distribution, partitioning
- **Traceability Matrix**: Gold → Silver → Bronze table-level lineage
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
`memory/dms/session-{YYYY-MM-DD}.md`:

- What was validated (DMS filename)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "validate-dms", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/dms/learnings-queue.jsonl
```

**What counts as a correction:** user says "no, change X to Y", edits artifact
directly, rejects a proposed decision, or provides a specific value replacing
a vague one you generated. When in doubt, append it — false positives are filtered
during apply-learnings.

## Learnings & Corrections

> **Meta-rules for adding learnings:**
> 1. Each learning MUST be an absolute directive ("Always X", "Never Y")
> 2. Lead with the problem, then the fix: "When X happens, do Y"
> 3. Include a concrete command or example, not just prose
> 4. One learning per bullet — no compound rules
> 5. Delete learnings that contradict each other; keep the newer one
> 6. Maximum 20 learnings per skill — if at capacity, merge related items

### Active Learnings

_No learnings recorded yet. Learnings are added when corrections occur during skill execution._

<!-- Example format:
- **L-001** (2026-03-20): Always use CAST(col AS DATE) not TO_DATE(col) for date conversions.
- **L-002** (2026-03-21): Never generate placeholder SLA values — ask the user for specific numeric targets.
-->
