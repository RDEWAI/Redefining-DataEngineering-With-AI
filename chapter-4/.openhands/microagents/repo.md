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

## Data Sources

- **DuckDB Database**: `data/duckdb/raw.db` (or `../data/duckdb/raw.db`)
- **Schema**: `synthea` (healthcare data)
- **Tables**: patients, encounters, conditions, medications, procedures, etc.

## Artifact Types (in sequence)

1. **DRD** (Data Requirements Document) - Markdown, starts with `# Data Requirements Document (DRD)`
2. **PAD** (Pipeline Architecture Document) - Markdown, starts with `# Pipeline Architecture Document (PAD)`
3. **DMD** (Data Mapping Document) - CSV format with header row
4. **DQS** (Data Quality Specification) - YAML format
5. **Stories** (User Stories/Epics) - Markdown, starts with `# User Stories`
6. **Package** (Consolidated Package) - Markdown, starts with `# Data Engineering Delivery Package`

## Tool Usage

- `duckdb_tables`: List tables (call ONCE)
- `duckdb_schema`: Get table structure (call 2-3 times max)
- `duckdb_query`: Sample data (call sparingly, LIMIT 5)
- `analyze_csv`: Analyze CSV files

## Example Correct Workflow

1. User requests DRD
2. You call `duckdb_tables` → see 18 tables
3. You call `duckdb_schema` for patients → get structure
4. You call `duckdb_schema` for encounters → get structure
5. You generate the COMPLETE DRD document
6. You call `finish` with the DRD content

## Example INCORRECT Workflow (DO NOT DO THIS)

1. User requests DRD
2. You say "I'll help you create a DRD. Let me start by exploring..."
3. You call `duckdb_tables` repeatedly
4. You say "Here's what I found. Would you like me to continue?"
← THIS IS WRONG. Generate the full artifact immediately!
