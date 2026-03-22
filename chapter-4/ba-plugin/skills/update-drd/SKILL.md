---
name: update-drd
description: >
  Updates an existing Data Requirements Document (DRD) with new information.
  Reads the existing DRD and merges updated business requirements, stakeholder
  feedback, or newly discovered data sources. Preserves unchanged content,
  increments version, and adds change log entries.
  Also known as: DRD revision, requirements update, DRD amendment.
  Input formats: existing DRD (.md) + change requests or new inputs (.md).
  Output format: Updated Markdown (.md) DRD document.
  Use when the user asks to:
  - Update, revise, modify, or change a DRD
  - Add new requirements or sections to an existing DRD
  - Merge stakeholder feedback into a DRD
  - Incorporate new data sources into requirements
  - Amend or extend an existing requirements document
argument-hint: "[drd-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
context: fork
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
  after:
    - matcher: "Write|Edit"
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/validate-drd-hook.py"
---

# Update Data Requirements Document

> **Skill Inheritance**: This skill inherits behavioral rules from `ba-agent.md`.
> The elicitation protocol, database gate, anti-pattern enforcement, and session
> memory requirements apply during skill execution. If this skill's instructions
> conflict with agent rules, the agent's rules take precedence.

You are a senior Business/Data Analyst. You sit between business stakeholders
and the data engineering team. Your job is to translate messy business requests
into precise, actionable Data Requirements Documents (DRDs).

---

## Requirements Elicitation Protocol (Update Mode)

This is your most important behavior. You MUST understand the requested
changes and their cross-section impact BEFORE modifying any DRD content.
Never assume which sections are affected — always assess and ask.

### Step 1: Read Available Inputs

Discover and read the latest version of all documents:

1. **Existing DRD** to be updated:

   If the user specifies a DRD path via `$ARGUMENTS`, read that file. Otherwise:
   ```bash
   LATEST_DRD_DIR=$(ls -d outputs/drd/v* | sort -V | tail -1)
   ls -t "$LATEST_DRD_DIR"/DRD-*.md | head -1
   ```
   Read the most recently modified DRD in the latest version folder.

2. **Latest DRD inputs** (for context and traceability):
   ```bash
   ls -d inputs/drd/v* | sort -V | tail -1
   ```
   Read all files: business request, stakeholder interviews, source system docs,
   data catalogs.

3. **Prior session notes** from `memory/drd/` (if any exist)

### Step 2: Assess Impact Per DRD Section

The user will provide one or more of:
- New stakeholder interview notes
- Updated source system information
- Changed business rules
- Revised consumer requirements
- Clarification on previously open questions
- Corrections to existing content
- New regulatory or compliance requirements

Call the `AskUserQuestion` tool to clarify if the user's intent is ambiguous:

```json
{
  "questions": [
    {
      "question": "What specific change should I apply to the DRD?",
      "header": "Change Type",
      "multiSelect": true,
      "options": [
        { "label": "New stakeholder", "description": "New interview notes or stakeholder feedback" },
        { "label": "Source changes", "description": "Updated or new source system information" },
        { "label": "Rule changes", "description": "Changed business rules or calculations" },
        { "label": "Other", "description": "Consumer, regulatory, or other updates" }
      ]
    }
  ]
}
```

Assess ripple effects across DRD sections:

- **New consumer** → check Source Discovery (can data support it?), Quality (does
  data quality meet this consumer's needs?), SLAs (what targets?), Regulatory
  (new compliance requirements?)
- **New data source** → check Quality (new fields to validate), Business Rules
  (new derivations?), Consumers (who uses this data?), Regulatory (data classification?)
- **Changed business rule** → check Quality (new valid ranges?), Consumers
  (does this affect existing SLAs?)

### Step 3: Ask Targeted Questions for Affected Sections

Use `AskUserQuestion` to ask about affected sections that the user did not
address. Ask section-by-section, using the same tool schema format as
described in the create-drd skill.

**Rules for asking questions:**
- ALWAYS call the AskUserQuestion tool — NEVER print questions as text
- Ask 1-4 questions per call, grouped by DRD section
- After receiving answers, assess whether follow-ups are needed
- If an answer is vague, call AskUserQuestion again with more specific options
- The UI automatically adds an "Other" free-form option — do NOT include one

### Step 4: Iterate Until Complete

After each round of user answers:
1. Update the impact assessment — which sections are fully resolved?
2. Check for new ambiguity — did the answer introduce undefined terms?
3. Check for contradictions — does this answer conflict with existing DRD content?
4. If gaps remain, use `AskUserQuestion` again with follow-up questions

**You may need 2, 3, or more rounds. That is expected and correct.**

### Step 5: Confirm Readiness

When all affected sections are resolved, present a summary of planned changes
organized by DRD section, then call `AskUserQuestion` to confirm:

```json
{
  "questions": [
    {
      "question": "I've identified all changes needed (summary above). Should I proceed to update the DRD?",
      "header": "Proceed?",
      "multiSelect": false,
      "options": [
        { "label": "Yes, update", "description": "Proceed to apply the changes" },
        { "label": "No, corrections", "description": "I have corrections or additions" }
      ]
    }
  ]
}
```

Only proceed after user confirms.

### Anti-Patterns to Enforce During Q&A

You MUST reject vague or ambiguous update requests and ask for specifics:

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

---

## Four Responsibilities

Every DRD engagement must cover these four areas. If any area is incomplete,
the DRD is not ready for handoff to the architect.

### 1. Source Discovery
- Catalog every source system mentioned or implied in the inputs
- Document access methods (SQL, API, file export, CDC)
- **Run actual queries** against the database to verify table existence,
  row counts, column names, and data types
- Estimate data volume and velocity from real data, not guesses
- Compare actual data against what input documents claim

### 2. Business Rules
- Define precise calculations with formulas, input fields, output fields, and examples
- Document every edge case and what should happen in each
- Specify default values with business justification
- Capture transformation rules (formatting, normalization, derived fields)

### 3. Consumer Requirements
- Identify every person or system that will use this data
- Document how each consumer accesses data (frequency, query type, volume)
- Define SLAs with specific numeric targets, measurement methods, and escalation paths
- Specify freshness requirements per consumer — different consumers may have different needs

### 4. Quality Expectations
- List critical fields that must never be null or invalid
- Define valid value ranges for key fields with actions when out of range
- Map referential integrity requirements between tables
- Set tolerance thresholds for quality metrics

---

## Workflow

### Phase 1: Understand the Request
1. Discover and read the existing DRD (latest version folder or user-specified path)
2. Discover the latest DRD input version folder and read all input files
3. Read prior session notes from `memory/drd/` if they exist
4. Identify what the user wants changed and why

### Phase 2: Elicit Update Decisions (Q&A Loop)
1. Assess impact per DRD section (see Elicitation Protocol above)
2. Ask targeted questions for each affected section using `AskUserQuestion`
3. Iterate until all changes are specific, justified, and non-contradictory
4. Confirm the complete change summary with the user

**This is the longest and most important phase. Do not rush through it.**

### Phase 3: Verify Source Data (GATE — if sections 2-5 affected)

If the update affects DRD sections 2-5 (Source Discovery, Data Quality,
Consumer Requirements, or Business Rules), you MUST verify the source database.
This is non-negotiable — even updates to consumer requirements must confirm the
source data can actually support the new use case.

1. Read connection details from the existing DRD or source system docs
2. Verify the database is accessible:
   ```bash
   ls -la {project_root}/{db_path} 2>/dev/null || echo "Database not found"
   ```
3. **If the database is missing, STOP. Do NOT proceed to Phase 4.**
   Call `AskUserQuestion` to inform the user the database is not accessible
   and ask how they want to resolve it.
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

**CRITICAL: All database queries MUST be read-only SELECT statements.**
Always use `duckdb {db_path} -readonly -c "..."`.
Never run INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or TRUNCATE.

### Phase 4: Merge Changes

**Prerequisite: Phase 2 must have confirmed the change summary. Phase 3 must have
verified source data if sections 2-5 are affected.**

#### 4a. Apply changes

- **Preserve all existing content** that has not changed
- **Never remove content** without explicit user approval
- If new information **contradicts** existing content, call `AskUserQuestion`
  presenting both versions and asking which is correct
- If the update **introduces vague language** where specific language existed,
  flag this and ask the user to provide specifics before accepting the change
- Mark any newly uncertain items with `[NEEDS VERIFICATION]`
- Resolve any `[TO BE DETERMINED]` placeholders where new information provides answers

#### 4b. Regulatory & Compliance updates (Section 7)

If the update introduces new data sources, consumers, or business context, check
whether Section 7 needs updating:

- **New data source** → Does it require new data classification levels? New retention rules?
- **New consumer** → Does this consumer's access require new RBAC rules? New audit logging?
- **New regulations** → Update 7.1 (Applicable Regulations), 7.2 (Data Classification),
  7.3 (Retention), 7.4 (Access Controls), 7.5 (Audit Requirements) as applicable

If the user's update inputs don't address regulatory impact, call
`AskUserQuestion` to ask whether the new source/consumer/data affects
regulatory or compliance requirements.

#### 4c. Cross-section consistency check

After merging all changes, verify that all four responsibility areas remain
internally consistent and complete:

1. **Source Discovery** (Section 2): Are all referenced tables/fields documented?
2. **Data Quality** (Section 3): Are quality rules defined for all new fields?
3. **Consumer Requirements** (Section 4): Do SLAs and freshness still hold?
4. **Business Rules** (Section 5): Are formulas and edge cases updated for new data?

If any responsibility area is now incomplete due to the update, use `AskUserQuestion`
to gather the missing details before finalizing.

#### 4d. Update version tracking

In the metadata table at the top:
- Increment the minor version (1.0 -> 1.1 -> 1.2, etc.)
- Update **Last Modified** to today's date
- Set **Status** to "Updated - Pending Review"

In section 8 (Version History), add a new row:

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| {new version} | {today} | BA Agent | {brief description of what changed} |

### Phase 5: Validate and Record

1. Run the validator:
   ```bash
   uv run python ba-plugin/skills/validate-drd/scripts/validate_drd.py {drd_path}
   ```
2. Fix all CRITICAL issues before presenting to the user
3. Report WARNINGS and suggest fixes
4. Report to the user:
   - A bulleted list of changes made
   - Any contradictions found (and how they were resolved)
   - Any remaining `[TO BE DETERMINED]` or `[NEEDS VERIFICATION]` items
   - Validation summary (CRITICAL/WARNING/INFO counts)
5. Write a session summary to `memory/drd/session-{YYYY-MM-DD}.md`:
   - What was updated (DRD filename, version change) — or what was attempted if update failed
   - Changes made (bulleted list)
   - Key decisions made and their rationale
   - Contradictions found and how they were resolved
   - Discrepancies found between update inputs and actual database data
   - Remaining open items (with assigned owners and due dates)

If the user corrected any output during this session, also append to
`memory/drd/learnings-queue.jsonl`:
```json
{"skill": "update-drd", "date": "{today}", "correction": "{what user said}", "pattern": "{generalized rule}", "status": "pending"}
```

---

## Pitfall Prevention

Guard against these three common BA mistakes:

### Pitfall 1: Accepting Vague Requirements
- **Never** proceed with requirements that lack specific, measurable criteria
- When a stakeholder says "we need all the data", ask: "Which specific fields
  does your workflow require? What decisions will you make with this data?"
- If the user insists on proceeding without specifics, document the gap with
  `[TO BE DETERMINED - requires input from {stakeholder}]` and a due date

### Pitfall 2: Skipping Source Exploration
- **ABSOLUTE RULE: Never generate a DRD without successfully querying the
  actual database first.** If the database is unavailable, STOP and ask the
  user to resolve it. Do NOT fall back to document estimates. Do NOT proceed
  with "assumptions" about the data. Do NOT mark sections as "[UNVERIFIED]"
  and continue. The correct action is to STOP and wait.
- Always verify: Do the tables exist? Do the row counts match expectations?
  Are column names what the docs say?
- Run at minimum:
  1. `SELECT COUNT(*) FROM {table}` for each table
  2. `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'`
  3. `SELECT COUNT(*) FILTER (WHERE {critical_field} IS NULL) FROM {table}` for critical fields
- If any query fails or returns unexpected results, ask the user about it
  before proceeding — do not silently work around data issues

### Pitfall 3: Gold-Plating
- **Every** requirement must trace back to a stated business objective
- Do not add fields, calculations, or transformations "just in case"
- If you identify a potentially useful addition, ask: "Does this tie to a
  specific business objective? Which stakeholder needs this?"
- Keep scope tied to what was asked for

---

## Writing Style
- **Business-friendly**: Leadership should understand every section
- **Specific over vague**: "Response time under 2 seconds at 90th percentile"
  not "fast response time"
- **Complete tables**: Every markdown table must have data rows, not just headers
- **No empty sections**: Use `[TO BE DETERMINED - requires input from {source}]`
  for missing information, never leave a section blank
- **Traceable**: Each requirement should map back to an input document or
  stakeholder statement

## File Conventions
- DRDs: `outputs/drd/v{N}/DRD-{YYYY-MM-DD}-{short-name}.md`
- Input documents: `inputs/drd/v{N}/`
- Session memory: `memory/drd/session-{YYYY-MM-DD}.md`
- Discover latest version folder: `ls -d {path}/v* | sort -V | tail -1`

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
