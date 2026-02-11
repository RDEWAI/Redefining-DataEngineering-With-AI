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

## Step 0: Read connection configuration

Read connection details from the source system documentation in the input folder.

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

### Verify data availability

Use the extracted `path` to check if the database exists:

```bash
ls -la {project_root}/{path} 2>/dev/null || echo "Database not found"
```

### If database is missing, load data from Docker

Run the Makefile targets from the project root:

```bash
make raw-data-copy   # Extract CSV from Docker (requires Docker running)
make load-raw-data   # Load into DuckDB
```

### Query actual volume and column counts

Use the extracted `path` and `schema` to query the database for accurate metadata
to use in Section 2 (Source Discovery). Report actual row counts and column counts
for each table in the schema.

## Step 1: Gather inputs

Read all documents from the input folder (`$ARGUMENTS` or `chapter-3/inputs/drd/`).
Look for these four input types:

**Tip**: Use the connection details from Source System Docs to query the live database.
Prefer actual row/column counts from Step 0 over static document estimates.

| Input | What to extract |
|-------|----------------|
| **Business Request** | Business problem, objectives, success criteria, target users |
| **Stakeholder Interviews** | Per-stakeholder needs, priorities, pain points |
| **Source System Docs** | System names, table schemas, access methods, data volumes, **connection details** |
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

## Step 5: Save and validate

Save the output to `chapter-3/outputs/drd/` with naming convention:
`DRD-{YYYY-MM-DD}-{short-name}-{version}.md`

Where `{version}` is extracted from the input folder path (e.g., `v1` from `inputs/drd/v1`).

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
