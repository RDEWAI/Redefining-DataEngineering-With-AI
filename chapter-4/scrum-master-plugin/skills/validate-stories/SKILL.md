---
name: validate-stories
description: >
  Validates a Sprint Backlog against completeness and quality standards.
  Checks the backlog index, epic files, and story files for required sections,
  upstream traceability, dependency consistency, sprint allocation, and story
  quality. Reports issues as CRITICAL, WARNING, or INFO with suggested fixes.
  Also known as: backlog review, story quality check, sprint plan audit.
  Input formats: Stories output directory containing BACKLOG, EPIC, and STORY files.
  Output format: Validation report with severity-ranked findings.
  Use when the user asks to:
  - Validate, check, review, verify, or audit the backlog
  - Assess story completeness or sprint plan quality
  - Find issues or gaps in the stories
  - Run quality checks on stories before sprint planning
argument-hint: "[stories-directory-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
---

# Validate Sprint Backlog

> **Skill Inheritance**: This skill inherits behavioral rules from
> `scrum-master-agent.md`. The traceability enforcement, pitfall prevention,
> and session memory requirements apply during skill execution.

You are a Scrum Master responsible for decomposing technical designs into
implementable work items. You sit at the end of the artifact chain — consuming
the LLD (and all upstream artifacts) and producing a Sprint Backlog of Epics
and Stories.

## Step 1: Run the validator

Run the Python validator script on the stories directory:

```bash
# All files in the latest version folder
LATEST_STORIES_DIR=$(ls -d outputs/stories/v* | sort -V | tail -1)
uv run python scrum-master-plugin/skills/validate-stories/scripts/validate_stories.py --all "$LATEST_STORIES_DIR"
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks sprint execution)
- Backlog index file exists with all 7 required sections
- At least 1 epic directory exists
- At least 1 story file per epic
- Each story has: User Story, Acceptance Criteria, Dependencies sections
- Each epic has: Objective, Stories table sections
- Backlog metadata complete (version, date, author, status, LLD reference)

### WARNING (needs attention)
- Upstream traceability — stories reference LLD/DMS/DQS sections
- Dependency consistency — referenced STORY IDs actually exist
- Sprint allocation — all stories assigned to a sprint
- Story point estimates present for all stories
- No orphaned stories — every story belongs to an epic
- Dependency graph present in backlog (Mermaid diagram)

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- Estimation support tables populated
- Technical notes present in stories
- Traceability matrix populated in backlog

## Backlog Sections Reference

A complete backlog contains:

**BACKLOG index (7 sections)**:
- Executive Summary, Epic Overview, Dependency Graph, Sprint Plan,
  Traceability Matrix, Risks & Assumptions, Version History

**Each EPIC file**:
- Objective, Scope, Stories table, Acceptance Criteria, Risks

**Each STORY file**:
- User Story, Description, Acceptance Criteria, Technical Notes, Estimation Support

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
        { "label": "High-priority", "description": "Fix only traceability and dependency warnings" },
        { "label": "Report only", "description": "Leave warnings for later, just report them" }
      ]
    }
  ]
}
```

Format as a checklist:

```
Validation Results for outputs/stories/v1/

CRITICAL (must fix):
- [x] All critical issues have been auto-fixed

WARNING (should fix):
- [ ] STORY-02-003: Missing upstream traceability references
- [ ] Sprint 3: Over-allocated (45 pts vs 35 pt velocity)

INFO (nice to have):
- [ ] STORY-01-002: Estimation support table empty

Summary: 0 critical (fixed), 2 warnings, 1 info
```

## Step 4: Session memory

**Always write session notes.** Write to
`memory/stories/session-{YYYY-MM-DD}.md`:

- What was validated (backlog directory)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "validate-stories", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/stories/learnings-queue.jsonl
```

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
