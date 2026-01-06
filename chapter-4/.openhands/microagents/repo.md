---
name: pwi_conventions
type: repo
version: 1.0.0
agent: CodeActAgent
---

# Planning with Intent (PWI) Framework Conventions

You are working within the PWI (Planning with Intent) framework, a data engineering artifact generation system.

## Project Structure

```
chapter-4/
├── pwi/                    # Main PWI module
│   ├── agents/             # Legacy agent implementations
│   ├── openhands/          # OpenHands SDK integration
│   ├── workflow/           # Workflow orchestration
│   ├── llm/                # LLM client utilities
│   ├── config/             # Configuration schemas
│   ├── cli/                # CLI commands
│   └── dashboard/          # NiceGUI web dashboard
├── data/                   # Data files
│   ├── raw/                # Raw CSV source files
│   └── duckdb/             # DuckDB database files
├── output/                 # Generated artifacts
└── requests/               # Business request files
```

## Data Sources

- **DuckDB Database**: `data/duckdb/raw.db`
- **Schema**: `synthea` (healthcare data)
- **Tables**: patients, encounters, conditions, medications, procedures, etc.
- **Raw CSV Files**: `data/raw/*.csv` (18 Synthea healthcare files)

## Artifact Types

PWI generates 6 types of artifacts in sequence:

1. **DRD** (Data Requirements Document) - Markdown
2. **PAD** (Pipeline Architecture Document) - Markdown
3. **DMD** (Data Mapping Document) - CSV
4. **DQS** (Data Quality Specification) - YAML
5. **Stories** (User Stories/Epics) - Markdown
6. **Package** (Consolidated Package) - Markdown

## Code Style

- Python 3.12+
- Use type hints consistently
- Follow PEP 8 with 100 character line limit
- Use Pydantic for data validation
- Async/await for I/O operations

## Tool Usage Guidelines

When working with data:
1. Use `duckdb_query` for SQL queries against the DuckDB database
2. Use `duckdb_schema` to inspect table structures
3. Use `analyze_csv` for CSV file analysis
4. Always validate SQL before execution

## Output Format Guidelines

- Markdown artifacts should NOT be wrapped in ```markdown code fences
- CSV artifacts should include headers
- YAML artifacts should be valid YAML
- Include proper section headings and formatting
