---
name: pwi_conventions
type: repo
version: 2.0.0
agent: CodeActAgent
---

# Planning with Intent (PWI) Framework - ARTIFACT GENERATION

You are working in the PWI framework, a data engineering artifact generation system.

## CRITICAL: YOUR PRIMARY TASK IS ARTIFACT GENERATION

When asked to generate an artifact (DRD, PAD, DMD, DQS, Stories, Package), you MUST:

1. **Explore first** - Use 3-5 tool calls maximum to understand the data
2. **Generate the artifact** - Output the COMPLETE artifact content
3. **Call finish** - End with the full artifact as your final message

## FORBIDDEN BEHAVIORS

- ❌ DO NOT ask "would you like me to proceed?"
- ❌ DO NOT say "let me know how you want to continue"
- ❌ DO NOT create task lists or bullet point summaries
- ❌ DO NOT call the same tool more than twice
- ❌ DO NOT wrap output in code fences (```markdown)

## REQUIRED BEHAVIORS

- ✅ DO generate the COMPLETE artifact
- ✅ DO use the exact format specified for each artifact type
- ✅ DO call `finish` with the full artifact content
- ✅ DO limit tool calls to 3-5 maximum

## Data Source Discovery

**IMPORTANT: Always call `discover_data` FIRST before any other data exploration.**

The `discover_data` tool will:
1. Search for CSV files in common locations
2. Search for DuckDB databases in common locations
3. Tell you which tools to use based on what's available

Based on `discover_data` results:
- If **DuckDB found**: Use `duckdb_tables`, `duckdb_schema`, `duckdb_query`
- If **CSV files found**: Use `analyze_csv`, `csv_stats`, `csv_sample`
- If **both found**: Prefer DuckDB (data is pre-loaded and queryable)

Do NOT assume any specific data source, schema, or table names.

## Artifact Types (in sequence)

1. **DRD** (Data Requirements Document) - Markdown, starts with `# Data Requirements Document (DRD)`
2. **PAD** (Pipeline Architecture Document) - Markdown, starts with `# Pipeline Architecture Document (PAD)`
3. **DMD** (Data Mapping Document) - CSV format with header row
4. **DQS** (Data Quality Specification) - YAML format
5. **Stories** (User Stories/Epics) - Markdown, starts with `# User Stories`
6. **Package** (Consolidated Package) - Markdown, starts with `# Data Engineering Delivery Package`

## Tool Usage

- `discover_data`: **CALL FIRST** - discovers available data sources
- `duckdb_tables`: List tables (call ONCE, only if DuckDB found)
- `duckdb_schema`: Get table structure (call 2-3 times max)
- `duckdb_query`: Sample data (call sparingly, LIMIT 5)
- `analyze_csv`: Analyze CSV files (only if CSVs found, no DuckDB)
- `csv_stats`: Get CSV statistics
- `csv_sample`: Get sample CSV rows

## Example Correct Workflow

1. User requests DRD
2. You call `discover_data` → see what data sources exist
3. Based on recommendation, use appropriate tools:
   - If DuckDB: `duckdb_tables` → `duckdb_schema` (2-3 times)
   - If CSV only: `analyze_csv` for key files
4. You generate the COMPLETE DRD document
5. You call `finish` with the DRD content

## Example INCORRECT Workflow (DO NOT DO THIS)

1. User requests DRD
2. You say "I'll help you create a DRD. Let me start by exploring..."
3. You call `duckdb_tables` repeatedly
4. You say "Here's what I found. Would you like me to continue?"
← THIS IS WRONG. Generate the full artifact immediately!
