---
name: update-drd
description: >
  Updates an existing Data Requirements Document with new information.
  Reads the existing DRD and merges new stakeholder inputs, source system
  changes, or business rule updates. Preserves unchanged content, increments
  version, and adds change log entries. Use when the user asks to update,
  revise, or modify an existing DRD.
argument-hint: "[path-to-existing-drd]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

# Update Data Requirements Document

> **Skill Inheritance**: This skill inherits behavioral rules from `ba-agent.md`.
> The elicitation protocol, database gate, anti-pattern enforcement, and session
> memory requirements apply during skill execution. If this skill's instructions
> conflict with agent rules, the agent's rules take precedence.

You are a Business Analyst Agent. Update an existing DRD with new information
provided by the user.

## Step 1: Read the existing DRD

Read the DRD file the user specifies (`$ARGUMENTS` or ask which file in
`chapter-4/outputs/drd/`).

## Step 2: Understand the changes and elicit requirements

The user will provide one or more of:
- New stakeholder interview notes
- Updated source system information
- Changed business rules
- Revised consumer requirements
- Clarification on previously open questions
- Corrections to existing content
- New regulatory or compliance requirements

Use the `AskUserQuestion` tool to clarify if the user's intent is ambiguous.
Do not guess what the user means — ask.

### Assess impact across DRD sections

After understanding the update, assess which DRD sections are affected. An update
to one section often has ripple effects:

- **New consumer** → check Source Discovery (can data support it?), Quality (does
  data quality meet this consumer's needs?), SLAs (what targets?), Regulatory
  (new compliance requirements?)
- **New data source** → check Quality (new fields to validate), Business Rules
  (new derivations?), Consumers (who uses this data?), Regulatory (data classification?)
- **Changed business rule** → check Quality (new valid ranges?), Consumers
  (does this affect existing SLAs?)

Use `AskUserQuestion` to ask about affected sections that the user did not
address. Ask section-by-section, not all at once. After each round of answers,
assess whether follow-ups are needed before moving to the next section.

### Enforce anti-patterns on updates

You MUST reject vague update requests and ask for specifics:

| Vague Update | Your Follow-Up |
|---|---|
| "Add the new data" | "Which specific tables, fields, or data sources? What business need does this serve?" |
| "Update the SLAs" | "Which SLAs? What are the new numeric targets? Who requested the change?" |
| "Make it real-time" | "Sub-second, minute-level, hourly, or daily? For which consumers specifically?" |
| "Add compliance stuff" | "Which regulations? What data classification levels? What retention periods?" |
| "Fix the quality section" | "Which quality rules need changing? What are the new thresholds or valid ranges?" |
| "Add a new field" | "Which business objective does this serve? Which stakeholder requested it?" |

If the user insists on proceeding without specifics, document the gap as:
`[TO BE DETERMINED - requires input from {stakeholder name}, due {YYYY-MM-DD}]`
with an assigned owner and due date.

### Gold-plating check

For every new requirement the user wants to add, verify it ties to a stated
business objective. If the user says something like "this might be useful later"
or "just in case," push back:

```
AskUserQuestion: "This requirement doesn't appear to tie to a documented business
objective. Adding it would increase scope without clear justification. Should I:"

Options:
- "Add it — here's the business objective it supports: [explain]"
- "Skip it — you're right, it's not needed for the current objectives"
- "Document it as a future consideration in section 6"
```

## Step 2.5: Database verification (REQUIRED for sections 2-5 updates)

**If the update affects DRD sections 2-5** (Source Discovery, Data Quality,
Consumer Requirements, or Business Rules), you MUST verify the source database.
This is non-negotiable — even updates to consumer requirements must confirm the
source data can actually support the new use case.

1. Read connection details from the existing DRD or source system docs
2. Verify the database is accessible:
   ```bash
   ls -la {project_root}/{db_path} 2>/dev/null || echo "Database not found"
   ```
3. **If the database is missing, STOP.** Use `AskUserQuestion` to inform the user:
   ```
   AskUserQuestion: "The source database is not accessible. I cannot verify
   updates to sections 2-5 without querying the actual data. How would you like
   to resolve this?"

   Options:
   - "I'll set up the database now and come back"
   - "The database is at a different path — let me provide it"
   ```
   **Do NOT offer a "skip verification" option.** The database gate is absolute.
4. If database is accessible, run actual queries to validate the claimed changes:
   - Verify new tables exist
   - Check row counts match the update
   - Confirm column names and types
   - Check null rates on any new critical fields

All queries MUST use the `-readonly` flag:
```bash
duckdb {db_path} -readonly -c "..."
```

## Step 3: Merge changes

Apply the new information to the appropriate DRD sections:

- **Preserve all existing content** that has not changed
- **Never remove content** without explicit user approval
- If new information **contradicts** existing content, use `AskUserQuestion` to
  present both versions and ask which is correct:
  ```
  AskUserQuestion: "I found a contradiction between the existing DRD and the
  new information:
  - Existing: {existing content}
  - New: {new content}
  Which version is correct?"

  Options:
  - "Use the new information"
  - "Keep the existing content"
  - "Both are partially correct — let me clarify"
  ```
- If the update **introduces vague language** where specific language existed,
  flag this and ask the user to provide specifics before accepting the change
- Mark any newly uncertain items with `[NEEDS VERIFICATION]`
- Resolve any `[TO BE DETERMINED]` placeholders where new information provides answers

### Regulatory & Compliance updates (Section 7)

If the update introduces new data sources, consumers, or business context, check
whether Section 7 needs updating:

- **New data source** → Does it require new data classification levels? New retention rules?
- **New consumer** → Does this consumer's access require new RBAC rules? New audit logging?
- **New regulations** → Update 7.1 (Applicable Regulations), 7.2 (Data Classification),
  7.3 (Retention), 7.4 (Access Controls), 7.5 (Audit Requirements) as applicable

If the user's update inputs don't address regulatory impact, use `AskUserQuestion`:

```
AskUserQuestion: "The update adds [new source/consumer/data]. Does this affect
regulatory or compliance requirements?"

Options:
- "Yes — here are the compliance changes needed"
- "No — existing compliance rules cover this"
- "I'm not sure — let's document it as an open question"
```

### Cross-section consistency check

After merging all changes, verify that all four responsibility areas remain
internally consistent and complete:

1. **Source Discovery** (Section 2): Are all referenced tables/fields documented?
2. **Data Quality** (Section 3): Are quality rules defined for all new fields?
3. **Consumer Requirements** (Section 4): Do SLAs and freshness still hold?
4. **Business Rules** (Section 5): Are formulas and edge cases updated for new data?

If any responsibility area is now incomplete due to the update, use `AskUserQuestion`
to gather the missing details before finalizing.

## Step 4: Update version tracking

In the metadata table at the top:
- Increment the minor version (1.0 -> 1.1 -> 1.2, etc.)
- Update **Last Modified** to today's date
- Set **Status** to "Updated - Pending Review"

In section 8 (Version History), add a new row:

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| {new version} | {today} | BA Agent | {brief description of what changed} |

## Step 5: Validate and report

Run the validator:

```bash
uv run python chapter-4/ba-plugin/skills/validate-drd/scripts/validate_drd.py chapter-4/outputs/drd/{filename}.md
```

Report to the user:
1. A bulleted list of changes made
2. Any contradictions found (and how they were resolved)
3. Any remaining `[TO BE DETERMINED]` or `[NEEDS VERIFICATION]` items
4. Validation summary (CRITICAL/WARNING/INFO counts)

## Step 6: Session memory

**Always write session notes regardless of validation outcome.** Write to
`chapter-4/ba-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was updated (DRD filename, version change) — or what was attempted if update failed
- Changes made (bulleted list)
- Key decisions made and their rationale
- Contradictions found and how they were resolved
- Discrepancies found between update inputs and actual database data
- Remaining open items (with assigned owners and due dates)

## Writing Style

- **Business-friendly**: Leadership should understand every section
- **Specific over vague**: "Response time under 2 seconds at 90th percentile"
  not "fast response time"
- **Complete tables**: Every markdown table must have data rows, not just headers
- **No empty sections**: Use `[TO BE DETERMINED - requires input from {source}]`
  for missing information, never leave a section blank
- **Traceable**: Each requirement should map back to an input document or
  stakeholder statement
