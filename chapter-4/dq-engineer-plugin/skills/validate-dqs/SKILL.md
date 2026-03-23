---
name: validate-dqs
description: >
  Validates a Data Quality Specification (DQS) document against completeness
  and quality standards. Checks all required sections, metadata, field-level
  rules, referential integrity, statistical tests, reconciliation rules,
  alert framework, and traceability. Reports issues as CRITICAL, WARNING,
  or INFO with suggested fixes.
  Also known as: DQS review, quality rules audit, DQ specification check.
  Input formats: DQS Markdown (.md) file.
  Output format: Validation report with severity-ranked findings.
  Use when the user asks to:
  - Validate, check, review, verify, or audit a DQS
  - Assess DQS completeness or rule quality
  - Find issues or gaps in quality specifications
  - Run quality checks on a DQS before handoff
argument-hint: "[dqs-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
---

# Validate Data Quality Specification

> **Skill Inheritance**: This skill inherits behavioral rules from
> `dq-engineer-agent.md`. The DQ elicitation protocol, pitfall prevention,
> and session memory requirements apply during skill execution.

You are a senior Data Quality Engineer. You sit downstream of the Mapping
Analyst (who produces the STM) and upstream of the engineering team. Your job
is to translate approved Source-to-Target Mappings into precise, build-ready
Data Quality Specifications (DQS) that define validation rules, statistical
baselines, reconciliation checks, and alert/escalation frameworks across all
Medallion layers.

## Step 1: Run the validator

Run the Python validator script on the specified file or all DQSs:

```bash
# Single file
uv run python dq-engineer-plugin/skills/validate-dqs/scripts/validate_dqs.py \
  $ARGUMENTS

# All DQSs in the latest version folder
LATEST_DQS_DIR=$(ls -d outputs/dqs/v* | sort -V | tail -1)
uv run python dq-engineer-plugin/skills/validate-dqs/scripts/validate_dqs.py \
  --all "$LATEST_DQS_DIR"
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks downstream work)
- All 9 required sections present (Overview through Version History)
- Metadata complete (Version, Created, Author, Status, STM or DMS reference)
- Field-Level Validation Rules section has rule tables with DQ- rule IDs
- Referential Integrity section has at least one FK check
- Overview defines CRITICAL, WARNING, and INFO severity levels
- At least 3 rule IDs in DQ-{CATEGORY}-{nnn} format

### WARNING (needs attention)
- Field-level rules cover bronze, silver, AND gold layers (not gold layer only)
- Reconciliation Rules section has at least one rule
- Alert & Escalation Framework has severity routing or threshold definitions
- Freshness & SLA Monitoring has per-consumer entries
- STM referenced at least twice (traceability)
- DMS referenced at least twice (traceability)
- Traceability Matrix has data rows
- Statistical Distribution Tests have numeric baselines or thresholds

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- DRD referenced for business context
- Alert framework mentions notification channels (Slack, PagerDuty, email)

## DQS Sections Reference

A complete DQS contains these sections:
- **Overview**: Severity definitions (CRITICAL/WARNING/INFO), rule ID
  conventions (DQ-FLD, DQ-REF, DQ-STA, DQ-REC, DQ-FRS), scope table
- **Field-Level Validation Rules**: Per-layer tables (bronze, silver, gold)
  with rule IDs, expressions, severity, and action
- **Referential Integrity Rules**: FK checks with orphan action and severity
- **Statistical Distribution Tests**: Baselines, thresholds, frequency
- **Reconciliation Rules**: Source-to-target comparisons with tolerance
- **Freshness & SLA Monitoring**: Per-consumer latency targets and alert
  channels
- **Alert & Escalation Framework**: Severity routing, breach actions, contacts
- **Traceability Matrix**: Rule-to-DRD, rule-to-DMS, rule-to-STM mapping
- **Version History**: Change log entries

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
Validation Results for DQS-2026-03-17-patient-360.md

CRITICAL (must fix):
- [x] All critical issues have been auto-fixed

WARNING (should fix):
- [ ] Field-Level Validation: No bronze layer rules found

INFO (nice to have):
- [ ] Alert Framework: No notification channels specified

Summary: 0 critical (fixed), 1 warning, 1 info
```

## Step 4: Session memory

**Always write session notes.** Write to
`memory/dqs/session-{YYYY-MM-DD}.md`:

- What was validated (DQS filename)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues
- Coverage gaps identified (missing layers, missing table rules)

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "validate-dqs", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/dqs/learnings-queue.jsonl
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
