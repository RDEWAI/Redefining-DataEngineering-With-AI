---
name: validate-lld
description: >
  Validates a Low-Level Design (LLD) document against completeness and quality
  standards. Checks all 14 required sections, upstream artifact references,
  DAG specification, code architecture, configuration schema, and traceability.
  Reports issues as CRITICAL, WARNING, or INFO with suggested fixes.
  Also known as: LLD review, implementation design audit, tech spec validation.
  Input formats: LLD Markdown (.md) file.
  Output format: Validation report with severity-ranked findings.
  Use when the user asks to:
  - Validate, check, review, verify, or audit an LLD
  - Assess LLD completeness or implementation quality
  - Find issues or gaps in a low-level design document
  - Run quality checks on an LLD before development
  - "Check if the LLD is ready for the development team"
argument-hint: "[lld-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
---

# Validate Low-Level Design Document

> **Skill Inheritance**: This skill inherits behavioral rules from
> `technical-lead-agent.md`. The traceability enforcement, pitfall prevention,
> and session memory requirements apply during skill execution.

You are a senior Technical Lead. You sit downstream of the Business Analyst
(DRD), Data Architect (HLD), Data Modeler (DMS), Mapping Analyst (STM), and
DQ Engineer (DQS). Your job is to ensure Low-Level Design documents meet
completeness and quality standards before handoff to the development team.

## Step 1: Run the validator

Run the Python validator script on the specified file or all LLDs:

```bash
# Single file
uv run python technical-lead-plugin/skills/validate-lld/scripts/validate_lld.py $ARGUMENTS

# All LLDs in the latest version folder
LATEST_LLD_DIR=$(ls -d outputs/lld/v* | sort -V | tail -1)
uv run python technical-lead-plugin/skills/validate-lld/scripts/validate_lld.py --all "$LATEST_LLD_DIR"
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks downstream work)
- All 14 required sections present (Design Overview through Version History)
- Metadata complete (version, date, author, status, all 5 upstream refs)
- Design Overview exists with meaningful content (≥2 sentences)
- DAG Specification has task table with ≥3 data rows
- Task Implementation Details has per-task specs with ≥3 rows
- Configuration Schema has parameter table with ≥3 rows
- Upstream Artifact References cites all 5 upstream docs (DRD, HLD, DMS, STM, DQS)

### WARNING (needs attention)
- Upstream traceability — at least 5 citations with § section references
- Error Handling mentions retry, dead letter/quarantine, and alerting
- Deployment mentions DEV and PROD environments
- Monitoring has specific metric names or metrics table
- DAG section has ≥1 Mermaid diagram
- Decision Log uses Options Considered / Rationale format
- Performance section has numeric values (MB, GB, seconds, partitions)

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- Deployment mentions rollback procedures
- DAG section mentions critical path
- Config template YAML exists alongside LLD

## LLD Sections Reference

A complete LLD contains these 14 sections:
- **1. Design Overview**: Implementation approach, key decisions at a glance
- **2. Code Architecture**: Project structure, coding conventions, templates
- **3. File Formats & Storage Layout**: Storage format, compression, partitioning
- **4. DAG Specification**: Task inventory, dependencies, Mermaid diagram, scheduling
- **5. Task Implementation Details**: Per-task I/O contracts, transform refs, DQ checks
- **6. Performance & Optimization**: Parallelism, caching, join strategies, memory
- **7. Configuration Schema**: Parameters with per-environment defaults
- **8. Error Handling**: Retry policies, dead letter queues, alerting
- **9. Deployment**: Environments, promotion, rollback, health checks
- **10. Monitoring**: Metrics, dashboards, alerting rules
- **11. Upstream Artifact References**: Hub cross-reference to DRD, HLD, DMS, STM, DQS
- **12. Traceability Matrix**: Requirements → implementation mapping
- **13. Decision Log**: Options Considered, Rationale, Trade-off
- **14. Version History**: Version tracking table

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
Validation Results for LLD-2026-03-22-patient-360.md

CRITICAL (must fix):
- [x] All critical issues have been auto-fixed

WARNING (should fix):
- [ ] DAG Specification: No Mermaid diagram for task dependencies
- [ ] Error Handling: Missing dead letter queue strategy

INFO (nice to have):
- [ ] Deployment: No rollback procedure described

Summary: 0 critical (fixed), 2 warnings, 1 info
```

## Step 4: Session memory

**Always write session notes.** Write to
`memory/lld/session-{YYYY-MM-DD}.md`:

- What was validated (LLD filename)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "validate-lld", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/lld/learnings-queue.jsonl
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
- **L-001** (2026-03-20): Always re-run the validator after fixing CRITICAL issues — never assume the fix resolves all related checks.
- **L-002** (2026-03-21): Never skip Section 11 validation — missing upstream references indicate the LLD is not a proper hub document.
-->
