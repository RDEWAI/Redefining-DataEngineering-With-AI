---
name: create-drd
description: >
  Generates a Data Requirements Document (DRD) from business inputs.
  Reads business requests, stakeholder interviews, source system docs,
  and data catalogs from an input folder. Produces a business-friendly
  DRD following a standard Jinja2 template. Use when the user asks to
  create, generate, or draft a DRD, or when input documents need to be
  analyzed into structured data requirements.
argument-hint: "[input-folder-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

# Create Data Requirements Document

You are a Business Analyst Agent. Generate a Data Requirements Document (DRD)
from the input documents provided by the user.

## Step 0: Read connection configuration

Read connection details from the source system documentation in the input folder.
**Do NOT block on the database yet** — gather inputs and elicit requirements first
(Steps 1-1.5). The database gate is enforced in Step 1.7.

### Extract connection details

Look for a `## Connection Details` section in `source_system_docs.md` with a YAML code block:

```yaml
connection:
  type: duckdb
  path: data/duckdb/raw.db
  schema: synthea
  read_only: true
```

Extract these fields:
- `type`: Database type (e.g., duckdb)
- `path`: Database file path relative to project root
- `schema`: Schema name to query

## Step 1: Gather inputs

Read all documents from the input folder (`$ARGUMENTS` or `chapter-3/inputs/drd/`).
Look for these four input types:

**Tip**: Use the connection details from Source System Docs to query the live database
in Step 1.7. Always use actual row/column counts from the database, never static
document estimates.

| Input | What to extract |
|-------|----------------|
| **Business Request** | Business problem, objectives, success criteria, target users |
| **Stakeholder Interviews** | Per-stakeholder needs, priorities, pain points |
| **Source System Docs** | System names, table schemas, access methods, data volumes, **connection details** |
| **Existing Data Catalog** | Already-cataloged datasets, column lists, row counts |

If any input type is missing, document the gap in section 6 (Assumptions and Open Questions)
with `[TO BE DETERMINED - requires input from {specific stakeholder or source}]`.

## Step 1.5: Requirements Elicitation (Q&A Loop)

After gathering inputs, assess completeness for each DRD section before generating
any content. This step ensures you have specific, measurable requirements — not vague
placeholders.

### Assess gaps per DRD section

Build an internal checklist:

| DRD Section | Required Information | Status |
|---|---|---|
| **Executive Summary** | One-sentence objective, data products, success metrics | ? |
| **1. Business Context** | Business problem, objectives with measurable targets, success criteria with numbers, stakeholder table | ? |
| **2. Source Discovery** | Source systems with access methods, table inventory with row counts, volume estimates, security requirements | ? |
| **3. Data Quality** | Critical fields list, valid value ranges, referential integrity rules, tolerance thresholds | ? |
| **4. Consumer Requirements** | Named consumers with departments, access patterns per consumer, SLAs with numeric targets, freshness per consumer | ? |
| **5. Business Rules** | Default values with justification, calculations with formulas AND examples, transformation rules, edge cases | ? |
| **6. Assumptions & Questions** | Documented assumptions, open questions with owners and due dates | ? |
| **7. Regulatory & Compliance** | Applicable regulations, data classification levels, retention periods, access controls, audit requirements | ? |

Mark each section as COMPLETE, PARTIAL, or MISSING.

### Ask targeted questions

For every section that is PARTIAL or MISSING, use the `AskUserQuestion` tool to ask
the user structured questions with concrete options.

**Rules:**
- ALWAYS use the AskUserQuestion tool — do not just print questions as text
- Ask questions section-by-section, not all at once
- After receiving answers, assess whether follow-ups are needed before moving on
- If an answer is vague, ask a follow-up immediately with more specific options

### Enforce anti-patterns

You MUST reject vague or ambiguous answers and ask for specifics:

| Vague Answer | Your Follow-Up |
|---|---|
| "We need all the data" | "Which specific tables and fields? What is the minimum viable dataset?" |
| "Real-time" | "Sub-second latency, minute-level, hourly refresh, or daily batch?" |
| "Fast response" | "What is the acceptable 90th percentile response time? 1s? 5s? 30s?" |
| "Comprehensive view" | "Which specific data domains? (demographics, encounters, conditions, medications, allergies, labs, billing — which subset?)" |
| "Up-to-date" | "What is the maximum acceptable data staleness per consumer?" |
| "All users" | "Name the specific user groups, departments, and headcount per group." |
| "Standard compliance" | "Which specific regulations? HIPAA? GDPR? State laws?" |

### Confirm readiness

When all sections are COMPLETE, present a summary of gathered requirements organized
by DRD section, then use `AskUserQuestion` to confirm:

```
AskUserQuestion: "I've gathered requirements for all DRD sections (summary above).
Is this complete and accurate? Should I proceed to generate the DRD?"

Options:
- "Yes, proceed to generate the DRD"
- "No, I have corrections or additions"
```

Only proceed to Step 1.7 after user confirms.

## Step 1.7: Database Gate (REQUIRED — cannot skip)

**Do NOT proceed to Step 2 without a working database connection and successful queries.**

A DRD built on document estimates instead of real data is unreliable — wrong row
counts, missing columns, broken joins, incorrect null rates. You MUST verify the
actual data before generating any DRD content.

### Verify data availability

Use the connection details extracted in Step 0 to check if the database exists:

```bash
ls -la {project_root}/{path} 2>/dev/null || echo "Database not found"
```

### If database is missing — STOP

Use the `AskUserQuestion` tool to inform the user and block:

```
AskUserQuestion: "The source database is not accessible at the expected path.
I cannot generate a DRD without verifying the actual data — relying on document
estimates alone would produce unreliable requirements. How would you like to
resolve this?"

Options:
- "I'll set up the database now (run make raw-data-copy && make load-raw-data) and come back"
- "The database is at a different path — let me provide it"
- "I'll provide a direct database connection or export"
```

**Keep asking until the database is accessible. Do NOT generate a DRD with unverified data.**
**Do NOT fall back to document estimates. Do NOT proceed with assumptions.
Do NOT mark sections as "[UNVERIFIED]" and continue. The correct action is
to STOP, tell the user, and wait for them to resolve the data access issue.**

### Query actual data (minimum 3 query types)

Once the database is confirmed accessible, run **all three** of these query types
to verify the data matches input documents. All queries MUST use the `-readonly` flag.

**1. List all tables and row counts:**
```bash
duckdb {project_root}/{path} -readonly -c "SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}';"
duckdb {project_root}/{path} -readonly -c "SELECT COUNT(*) FROM {schema}.{table};"
```

**2. Get column names and types for key tables:**
```bash
duckdb {project_root}/{path} -readonly -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = '{schema}' AND table_name = '{table}';"
```

**3. Check nulls in critical fields (identified during Q&A in Step 1.5):**
```bash
duckdb {project_root}/{path} -readonly -c "SELECT COUNT(*) FILTER (WHERE {critical_field} IS NULL) FROM {schema}.{table};"
```

Compare actual data against what input documents claim. Note any discrepancies —
wrong row counts, missing columns, unexpected nulls — and document them in the DRD.

If any query fails or returns unexpected results, use `AskUserQuestion` to ask the
user about it before proceeding. Do not silently work around data issues.

## Step 2: Read the template

Read the DRD template to understand the required structure:

```bash
cat chapter-3/ba-plugin/skills/create-drd/DRD_template.j2
```

For a complete example of a finished DRD, see [examples/sample-drd.md](examples/sample-drd.md).

## Step 3: Generate the DRD

Write the DRD in Markdown following the template structure. Cover all four
responsibility areas:

### Source Discovery (Section 2)
- Identify every source system mentioned in inputs
- Catalog tables and datasets with row count estimates
- Document access methods (SQL, API, file export, etc.)
- Estimate data volumes

### Data Quality Expectations (Section 3)
- List critical fields that must never be null or invalid
- Define valid value ranges for key fields
- Map referential integrity requirements between tables
- Set tolerance thresholds for quality metrics

### Consumer Requirements (Section 4)
- Name every data consumer and their department
- Document how each consumer accesses data (frequency, query type, volume)
- Define SLAs with targets, measurement methods, and escalation paths
- Specify freshness requirements per consumer

### Business Rules (Section 5)
- Document default values with business justification
- Define calculations and derivations with formulas, inputs, outputs, and examples
- List transformation rules (formatting, normalization)
- Capture edge cases with expected behavior and rationale

### Regulatory and Compliance (Section 7)
- Identify applicable regulations from stakeholder inputs and business context (e.g., HIPAA, GDPR)
- Classify data elements by sensitivity level (e.g., PHI, PII, Internal)
- Document retention periods with legal basis for each data category
- Map role-based access controls per consumer group
- Specify audit logging requirements (access events, modifications, breach detection)

## Step 4: Writing style

- **Business-friendly**: Leadership should understand every section. Avoid jargon.
  Where technical terms are necessary, include a plain-English explanation.
- **Specific over vague**: "Response time under 2 seconds for 90th percentile"
  is better than "fast response time"
- **Complete tables**: Every table should have data rows, not just headers.
- **No empty sections**: If information is unavailable, write
  `[TO BE DETERMINED - requires input from {source}]`
- **Traceable**: Each requirement should map back to an input document or
  stakeholder statement

## Step 5: Save and validate

Save the output to `chapter-3/outputs/drd/` with naming convention:
`DRD-{YYYY-MM-DD}-{short-name}-{version}.md`

Where `{version}` is extracted from the input folder path (e.g., `v1` from `inputs/drd/v1`).

Then validate:

```bash
uv run python chapter-3/ba-plugin/skills/validate-drd/scripts/validate_drd.py chapter-3/outputs/drd/{filename}.md
```

Fix any CRITICAL issues before finalizing. Report the validation summary to the user.

## Step 6: Session memory

**Always write session notes regardless of validation outcome.** Write to
`chapter-3/ba-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was created (DRD filename, version) — or what was attempted if generation failed
- Key decisions made and their rationale
- Open questions that remain unresolved (with assigned owners and due dates)
- Discrepancies found between input documents and actual database data
- Validation results (CRITICAL/WARNING/INFO counts, fixes applied, remaining issues)

## Metadata

Every DRD starts with this metadata table:

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | {today's date} |
| **Last Modified** | {today's date} |
| **Author** | BA Agent |
| **Status** | Draft |
| **Business Sponsor** | {from business request or ask user} |
