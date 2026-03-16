---
name: validate-hld
description: >
  Validates a High-Level Design document against completeness and quality
  standards. Checks all required sections, DRD traceability, data architecture,
  technology decisions, integration architecture, and scalability model. Reports
  issues as CRITICAL, WARNING, or INFO with suggested fixes. Use when the user
  asks to validate, check, review, or verify an HLD.
argument-hint: "[path-to-hld-file]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# Validate High-Level Design Document

> **Skill Inheritance**: This skill inherits behavioral rules from
> `architect-agent.md`. The traceability enforcement, pitfall prevention,
> and session memory requirements apply during skill execution.

You are a senior Data Architect. You sit between the Business Analyst (who
produces the DRD) and the data engineering team (who implements). Your job
is to translate approved Data Requirements Documents into precise, build-ready
High-Level Design documents (HLDs) that specify architecture patterns,
technology decisions, data architecture, and capacity models.

## Step 1: Run the validator

Run the Python validator script on the specified file or all HLDs:

```bash
# Single file
uv run python architect-plugin/skills/validate-hld/scripts/validate_hld.py $ARGUMENTS

# All HLDs in the latest version folder
LATEST_HLD_DIR=$(ls -d outputs/hld/v* | sort -V | tail -1)
uv run python architect-plugin/skills/validate-hld/scripts/validate_hld.py --all "$LATEST_HLD_DIR"
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks downstream work)
- All 8 required sections present (Executive Summary through Operational Considerations)
- Metadata complete (version, date, author, status, DRD reference)
- Executive Summary exists with meaningful content (≥2 sentences)
- Data Architecture non-empty (Bronze, Silver, Gold layers described)
- Technology Decisions table present with entries

### WARNING (needs attention)
- DRD traceability — design decisions cite DRD requirements
- CDC strategy in Operational Considerations specifies detection methods
- Scalability & Capacity Model includes numeric projections
- Security & Compliance references regulatory/sensitive-data controls
- Architecture Overview includes pattern justification
- Decision documentation present

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- Mermaid diagrams present (≥2 blocks: system context + pipeline + ingestion sequence)
- Cost model described in Scalability & Capacity Model
- Downstream document references (LLD, DMS) present

## HLD Sections Reference

A complete HLD contains these sections:
- **Executive Summary**: Business context, scope, key decisions at a glance
- **Architecture Overview**: Pattern, justification, 3 Mermaid diagrams (system context, pipeline, ingestion sequence)
- **Data Architecture**: Bronze/Silver/Gold layer strategy, DQ approach (defer table inventories to DMS)
- **Technology Decisions**: Component/Tool/Why table (defer versions to LLD)
- **Integration Architecture**: Sources, lineage, downstream consumers
- **Scalability & Capacity Model**: Row counts, growth projections, compute sizing, cost model
- **Security & Compliance**: Compliance controls, encryption, access strategy, audit
- **Operational Considerations**: CDC summary, ingestion sequence diagram, RTO/RPO targets, backup strategy

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
- [ ] Operational Considerations: Missing monitoring and alerting strategy

INFO (nice to have):
- [ ] Scalability & Capacity Model: No cost model described

Summary: 0 critical (fixed), 1 warning, 1 info
```

## Step 4: Session memory

**Always write session notes.** Write to
`architect-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was validated (HLD filename)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues
