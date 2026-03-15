---
name: create-hld
description: >
  Generates a High-Level Design (HLD) document from a DRD and architect inputs.
  Reads the latest DRD, infrastructure constraints, team capabilities, and
  technology catalog. Produces a structured HLD covering architecture pattern,
  layer specifications, technology stack, CDC strategy, and capacity planning.
  Use when the user asks to create, generate, or draft an HLD, or when a DRD
  needs to be translated into an architecture design.
argument-hint: "[drd-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

# Create High-Level Design Document

> **Skill Inheritance**: This skill inherits behavioral rules from `architect-agent.md`.
> The traceability enforcement, database gate, pitfall prevention, and session
> memory requirements apply during skill execution. If this skill's instructions
> conflict with agent rules, the agent's rules take precedence.

You are a Data Architect Agent. Generate a High-Level Design (HLD) document
from the DRD and architect inputs provided by the user.

## Step 0: Read the DRD

If the user specifies a DRD path via `$ARGUMENTS`, read that file. Otherwise,
discover the latest DRD:

```bash
LATEST_DRD_DIR=$(ls -d chapter-4/outputs/drd/v* | sort -V | tail -1)
ls -t "$LATEST_DRD_DIR"/DRD-*.md | head -1
```

Read the most recently modified DRD in the latest version folder. The DRD is
your primary input — every design decision must trace back to a requirement in it.

Extract from the DRD:
- Data volumes and growth projections
- Latency and freshness requirements per consumer
- Compliance and regulatory requirements (as specified in DRD)
- Source systems and their access methods
- Business rules and transformation complexity
- Data quality expectations and SLAs

## Step 1: Read architect inputs

Discover the latest architect input version:

```bash
ls -d chapter-4/inputs/architect/v* | sort -V | tail -1
```

Read all files in that version folder:

| Input | Filename | What to extract |
|-------|----------|----------------|
| **Infrastructure Constraints** | `infrastructure-constraints.md` | Compute limits, storage format, networking, security, platform |
| **Team Capabilities** | `team-capabilities.md` | Language proficiency, pattern experience, gaps |
| **Technology Catalog** | `technology-catalog.md` | Approved tools, versions, licensing |

If any input is missing, document the gap in the HLD's Open Questions section
with `[TO BE DETERMINED - requires input from {source}]`.

## Step 1.5: Requirements Analysis (Q&A Loop)

After gathering all inputs, assess whether you have enough information to make
architecture decisions for each HLD section.

### Assess gaps per HLD section

Build an internal checklist:

| HLD Section | Required Information | Status |
|---|---|---|
| **1. Design Overview** | DRD latency requirements, data volumes, compliance needs | ? |
| **2. Layer Specifications** | Source table inventory, transformation rules, DQ expectations | ? |
| **3. Technology Stack** | Approved tech catalog, team capabilities, constraints | ? |
| **4. Integration Points** | Source access methods, consumer access patterns | ? |
| **5. Capacity Planning** | Actual data volumes (from DB), growth projections | ? |
| **6. Security Architecture** | Regulatory requirements (per DRD), data classification | ? |
| **7. Disaster Recovery** | SLA targets (RTO/RPO), backup constraints | ? |
| **8. CDC Strategy** | Source system change patterns, timestamp columns | ? |

Mark each section as COMPLETE, PARTIAL, or MISSING.

### Ask targeted questions

For every section that is PARTIAL or MISSING, call the `AskUserQuestion` tool.
Ask 1-4 questions per call, each with 2-4 structured options.

**Example tool call for Layer Specifications gaps:**
```json
{
  "questions": [
    {
      "question": "Which source tables should land in Bronze and pass through to Silver?",
      "header": "Tables",
      "multiSelect": false,
      "options": [
        { "label": "All DRD tables", "description": "Every table referenced in the DRD" },
        { "label": "High-volume only", "description": "Only tables with >1000 rows" },
        { "label": "Let me specify", "description": "I'll provide a custom list" }
      ]
    },
    {
      "question": "What SCD strategy should Silver use for slowly changing dimensions?",
      "header": "SCD",
      "multiSelect": false,
      "options": [
        { "label": "SCD Type 1", "description": "Overwrite — no history" },
        { "label": "SCD Type 2", "description": "Versioned rows with effective dates" },
        { "label": "No SCD needed", "description": "Dimensions do not change" }
      ]
    }
  ]
}
```

**Rules:**
- ALWAYS call the AskUserQuestion tool — NEVER print questions as text
- Ask questions section-by-section, not all at once
- After receiving answers, assess whether follow-ups are needed

### Enforce anti-patterns

If an answer is vague, use `AskUserQuestion` again to probe for specifics:

| Vague Answer | Your Follow-Up |
|---|---|
| "Use the latest tech" | "Which specific tool from the approved catalog? Which DRD requirement does it satisfy?" |
| "Make it scalable" | "What specific volume projections? What row count threshold triggers re-evaluation?" |
| "Standard security" | "Which compliance framework? Which sensitive fields need protection?" |
| "We need streaming" | "What actual latency requirement does the DRD specify?" |
| "Best practices" | "Which specific pattern? Which DRD requirements drive that choice?" |

### Confirm readiness

When all sections are COMPLETE, present a summary of your planned architecture
decisions, then call `AskUserQuestion` to confirm:

```json
{
  "questions": [
    {
      "question": "I've gathered design decisions for all HLD sections (summary above). Should I proceed to generate the HLD?",
      "header": "Proceed?",
      "multiSelect": false,
      "options": [
        { "label": "Yes, generate", "description": "Proceed to generate the HLD document" },
        { "label": "No, corrections", "description": "I have corrections or additions" }
      ]
    }
  ]
}
```

Only proceed after user confirms.

## Step 1.7: Database Gate (REQUIRED — cannot skip)

**Do NOT proceed to Step 2 without a working database connection.**

An HLD built on document estimates instead of actual data volumes produces
incorrect capacity planning and CDC strategy.

### Verify data availability

```bash
ls -la data/duckdb/raw.db 2>/dev/null || echo "Database not found"
```

### If database is missing — STOP

Call `AskUserQuestion` to inform the user and block:

```json
{
  "questions": [
    {
      "question": "The source database is not accessible. I cannot generate an HLD without verifying actual data volumes. How would you like to resolve this?",
      "header": "DB Missing",
      "multiSelect": false,
      "options": [
        { "label": "Set up DB", "description": "I'll set up the database now and come back" },
        { "label": "Different path", "description": "The database is at a different path" },
        { "label": "Use DRD counts", "description": "Use DRD-verified row counts instead" }
      ]
    }
  ]
}
```

**Do NOT proceed with document estimates. Do NOT mark capacity as "[ESTIMATED]".**

### Query actual data

Once the database is accessible, run these queries (all with `-readonly`):

**1. Table inventory with row counts:**
```bash
duckdb {db_path} -readonly -c "
  SELECT table_schema, table_name, estimated_size
  FROM duckdb_tables()
  ORDER BY estimated_size DESC;
"
```

**2. Column counts per table:**
```bash
duckdb {db_path} -readonly -c "
  SELECT table_schema, table_name, COUNT(*) as col_count
  FROM information_schema.columns
  GROUP BY table_schema, table_name;
"
```

**3. Check for timestamp columns (CDC strategy input):**
```bash
duckdb {db_path} -readonly -c "
  SELECT table_schema, table_name, column_name, data_type
  FROM information_schema.columns
  WHERE column_name LIKE '%date%'
    OR column_name LIKE '%time%'
    OR column_name LIKE '%modified%'
    OR column_name LIKE '%updated%'
  ORDER BY table_schema, table_name;
"
```

Use actual volumes for capacity planning. Note any discrepancies between
DRD estimates and actual data.

## Step 2: Read the template

Read the HLD template to understand the required structure:

```bash
cat chapter-4/architect-plugin/skills/create-hld/HLD_template.j2
```

For a complete example of a finished HLD, see
[examples/sample-hld.md](examples/sample-hld.md).

## Step 3: Generate the HLD

Write the HLD in Markdown following the template structure. Cover all four
responsibility areas:

### Architecture Pattern Selection (Section 1)

- Evaluate DRD requirements against pattern options
- Select and document the pattern with full justification
- For each candidate pattern, document why it was selected or rejected
- **Every selection must cite a specific DRD requirement**
- Include a Mermaid architecture diagram

### Layer Design (Section 2)

For each layer (Bronze, Silver, Gold):
- Purpose and responsibilities
- What transformations happen at this layer
- What passes through unchanged
- Data quality expectations at this layer
- Output schema overview (high-level, not column-level)

### Technology Selection (Section 3)

For each component:
- Technology choice with version
- Rationale citing DRD requirements AND team capabilities
- Alternatives considered and why they were rejected
- Infrastructure constraints that influenced the choice

### Non-Functional Requirements (Sections 5-8)

- Capacity planning with actual volumes from database queries
- Security architecture aligned with DRD regulatory section
- DR strategy aligned with DRD SLAs
- CDC strategy per source table with fallback methods

## Step 3.5: Decision Documentation

For every major design decision, document using this format:

```markdown
**Decision**: [what was decided]
- **Options Considered**: [list alternatives]
- **Selected**: [chosen option]
- **Rationale**: [why, citing DRD section]
- **Trade-offs Accepted**: [what you give up]
```

## Step 4: Writing style

- **Technical but accessible**: Engineers and architects should understand
  every section. Include diagrams where helpful.
- **Traceable**: Every design decision must cite a DRD requirement.
  If you cannot cite a requirement, flag it as a gap.
- **Specific over vague**: "Tool X v1.2.3 for processing because the
  DRD projects <100K rows (Section 5.1)" not "lightweight processing"
- **Complete tables**: Every table must have data rows, not just headers
- **No empty sections**: Use `[TO BE DETERMINED]` with owner and due date

## Step 5: Save and validate

Save the output to the latest version folder in `chapter-4/outputs/hld/`:

```bash
LATEST_HLD_DIR=$(ls -d chapter-4/outputs/hld/v* | sort -V | tail -1)
```

Use naming convention: `HLD-{YYYY-MM-DD}-{short-name}.md`

Then validate:

```bash
uv run python chapter-4/architect-plugin/skills/validate-hld/scripts/validate_hld.py chapter-4/outputs/hld/{filename}.md
```

Fix any CRITICAL issues before finalizing. Report the validation summary
to the user.

## Step 6: Session memory

**Always write session notes regardless of outcome.** Write to
`chapter-4/architect-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was created (HLD filename, version)
- Architecture pattern selected and why
- Key technology decisions with rationale
- DRD gaps found (requirements that were missing or ambiguous)
- Discrepancies between DRD estimates and actual data
- Validation results (CRITICAL/WARNING/INFO counts)
- Open questions that remain unresolved

## Metadata

Every HLD starts with this metadata table:

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | {today's date} |
| **Last Modified** | {today's date} |
| **Author** | Architect Agent |
| **Status** | Draft |
| **DRD Reference** | {DRD filename and version} |
