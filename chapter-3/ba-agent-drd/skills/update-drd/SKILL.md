---
name: update-drd
description: >
  Updates an existing Data Requirements Document with new information.
  Reads the existing DRD and merges new stakeholder inputs, source system
  changes, or business rule updates. Preserves unchanged content, increments
  version, and adds change log entries. Use when the user asks to update,
  revise, or modify an existing DRD.
argument-hint: "[path-to-existing-drd]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
---

# Update Data Requirements Document

You are a Business Analyst Agent. Update an existing DRD with new information
provided by the user.

## Step 1: Read the existing DRD

Read the DRD file the user specifies (`$ARGUMENTS` or ask which file in
`chapter-3/outputs/drd/`).

## Step 2: Understand the changes

The user will provide one or more of:
- New stakeholder interview notes
- Updated source system information
- Changed business rules
- Revised consumer requirements
- Clarification on previously open questions
- Corrections to existing content

Ask the user to clarify if their intent is ambiguous.

## Step 3: Merge changes

Apply the new information to the appropriate DRD sections:

- **Preserve all existing content** that has not changed
- **Never remove content** without explicit user approval
- If new information **contradicts** existing content, present both versions
  and ask the user which is correct before proceeding
- Mark any newly uncertain items with `[NEEDS VERIFICATION]`
- Resolve any `[TO BE DETERMINED]` placeholders where new information provides answers

## Step 4: Update version tracking

In the metadata table at the top:
- Increment the minor version (1.0 -> 1.1 -> 1.2, etc.)
- Update **Last Modified** to today's date
- Set **Status** to "Updated - Pending Review"

In section 7 (Version History), add a new row:

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| {new version} | {today} | BA Agent | {brief description of what changed} |

## Step 5: Validate and report

Run the validator:

```bash
uv run python chapter-3/ba-agent-drd/skills/validate-drd/scripts/validate_drd.py chapter-3/outputs/drd/{filename}.md
```

Report to the user:
1. A bulleted list of changes made
2. Any contradictions found (and how they were resolved)
3. Any remaining `[TO BE DETERMINED]` or `[NEEDS VERIFICATION]` items
4. Validation summary (CRITICAL/WARNING/INFO counts)
