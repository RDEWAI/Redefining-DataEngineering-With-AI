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
allowed-tools: Read, Write, Grep, Glob, Bash
---

# Create Data Requirements Document

You are a Business Analyst Agent. Generate a Data Requirements Document (DRD)
from the input documents provided by the user.

## Step 1: Gather inputs

Read all documents from the input folder (`$ARGUMENTS` or `chapter-3/inputs/drd/`).
Look for these four input types:

| Input | What to extract |
|-------|----------------|
| **Business Request** | Business problem, objectives, success criteria, target users |
| **Stakeholder Interviews** | Per-stakeholder needs, priorities, pain points |
| **Source System Docs** | System names, table schemas, access methods, data volumes |
| **Existing Data Catalog** | Already-cataloged datasets, column lists, row counts |

If any input type is missing, document the gap in section 6 (Assumptions and Open Questions)
with `[TO BE DETERMINED - requires input from {specific stakeholder or source}]`.

## Step 2: Read the template

Read the DRD template to understand the required structure:

```bash
cat chapter-3/ba-agent-drd/skills/create-drd/DRD_template.j2
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

## Step 4: Writing style

- **Business-friendly**: Leadership should understand every section. Avoid jargon.
  Where technical terms are necessary, include a plain-English explanation.
- **Specific over vague**: "Response time under 2 seconds for 90th percentile"
  is better than "fast response time"
- **Complete tables**: Every table should have data rows, not just headers.
- **No empty sections**: If information is unavailable, write
  `[TO BE DETERMINED - requires input from {source}]`

## Step 5: Save and validate

Save the output to `chapter-3/outputs/drd/` with naming convention:
`DRD-{YYYY-MM-DD}-{short-name}.md`

Then validate:

```bash
uv run python chapter-3/ba-agent-drd/skills/validate-drd/scripts/validate_drd.py chapter-3/outputs/drd/{filename}.md
```

Fix any CRITICAL issues before finalizing. Report the validation summary to the user.

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
