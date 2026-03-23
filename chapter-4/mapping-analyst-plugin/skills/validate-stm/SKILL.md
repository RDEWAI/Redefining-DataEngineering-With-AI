---
name: validate-stm
description: >
  Validates a Source-to-Target Mapping (STM) Excel workbook for completeness
  and quality. Checks all 8 required sheets, column headers, transformation
  completeness, DMS traceability, and lineage coverage. Reports issues as
  CRITICAL, WARNING, or INFO with suggested fixes.
  Also known as: STM review, mapping quality check, transformation audit.
  Input formats: STM Excel workbook (.xlsx).
  Output format: Validation report with severity-ranked findings.
  Use when the user asks to:
  - Validate, check, review, verify, or audit an STM
  - Assess STM completeness or mapping quality
  - Find issues or gaps in transformation mappings
  - Run quality checks on an STM before handoff
argument-hint: "[stm-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
---

# Validate STM

Validate a Source-to-Target Mapping (STM) Excel workbook for completeness and quality.

## Role Context

You are the Mapping Analyst in the artifact chain: DRD → HLD → DMS → **STM** → DQS → LLD → Stories.
You produce STM documents as Excel workbooks (.xlsx) with 8 sheets covering all Medallion layer
transformations. The output format is .xlsx (not markdown).

## STM Sections Reference (8 Sheets)

| Sheet | Standard Columns |
|---|---|
| **Summary** | Key-value metadata (Version, Created, Author, Status, DMS Ref, HLD Ref) |
| **Source-to-Bronze** | source_table, source_column, source_type, target_table, target_column, target_type, transformation, notes |
| **Bronze-to-Silver** | source_table, source_column, source_type, target_table, target_column, target_type, transformation, null_handling, default_value, business_rule_ref, dms_ref |
| **Silver-to-Gold** | target_table, target_column, target_type, source_expression, join_logic, scd_type, grain, dms_ref |
| **Code Systems** | code_system, source_value_pattern, target_value, case_expression, notes |
| **Null Handling** | table, column, layer, criticality, null_rate_observed, action, default_value, business_rule_ref |
| **Edge Cases** | category, scenario, affected_tables, handling_rule, severity, dq_rule_ref |
| **Lineage** | gold_table, gold_column, silver_expression, bronze_column, source_column, transformation_chain |

## Steps

1. **Find the STM file to validate.**
   If a file path is provided, use it. Otherwise, find the latest:
   ```bash
   ls -d outputs/stm/v* | sort -V | tail -1
   ```
   Then find the most recent .xlsx in that directory.

2. **Run the validator:**
   ```bash
   uv run python mapping-analyst-plugin/skills/validate-stm/scripts/validate_stm.py <file.xlsx>
   ```

3. **Interpret results:**
   - **CRITICAL** issues MUST be fixed before the STM is usable
   - **WARNING** issues should be addressed for production quality
   - **INFO** issues are suggestions for improvement

4. **If CRITICAL issues found**, fix them:
   - Load the workbook with openpyxl
   - Add missing sheets, headers, or data rows
   - Save and re-validate

5. **Report final status** to the user with:
   - Summary counts (CRITICAL / WARNING / INFO)
   - Specific issues found and fixes applied
   - Remaining warnings for user awareness

### 6. Write Session Memory

Save session summary to `memory/stm/session-{YYYY-MM-DD}.md`:
- File validated and outcome (PASS / FAIL)
- CRITICAL and WARNING counts
- Issues found and fixes applied
- Open items for next session

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "validate-stm", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/stm/learnings-queue.jsonl
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
