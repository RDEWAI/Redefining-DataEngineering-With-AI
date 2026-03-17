# Claude Code Instructions

Add project-specific instructions for Claude Code here.

## Active Technologies
- Python 3.10-3.12 (aligned with existing project) (003-chapter2-ai-engineering)
- DuckDB at `chapter-2/data/duckdb/chapter2.db` with `library` schema (003-chapter2-ai-engineering)

- **Python 3.10-3.12** with UV package manager for environment management
- **DuckDB 1.1.3** for embedded analytics database
- **Apache Superset 4.1.1** for data visualization
- **SQLMesh** for SQL-based data transformations

## Data Architecture

- Raw CSV data: `data/raw/` (18 Synthea healthcare CSV files)
- DuckDB database: `data/duckdb/raw.db` with `synthea` schema
- Tables accessed as `synthea.patients`, `synthea.encounters`, etc.

## Key Commands

```bash
make dev-setup      # Set up development environment
make raw-data-copy  # Extract Synthea CSV data from Docker
make load-raw-data  # Load CSV files into DuckDB tables
make superset-init  # Initialize Superset with DuckDB connection
make superset-run   # Start Superset web server
make test           # Run all tests
```

## Chapter 3: Business Analyst Agent

- **Skills**: `.claude/skills/` under `chapter-3/` — `create-drd`, `update-drd`, `validate-drd`
- **Inputs**: `chapter-3/inputs/drd/` (business requests, stakeholder notes, source docs, catalogs)
- **Outputs**: `chapter-3/outputs/drd/` (generated DRD markdown files)
- **Validator**: `chapter-3/.claude/skills/validate-drd/scripts/validate_drd.py`
- **Tests**: `cd chapter-3 && uv run pytest tests/ -v`

## Chapter 4: Multi-Agent Artifact Chain (continuation of Chapter 3)

- **Plugins**: BA (DRD) → Architect (HLD) → Data Modeler (DMS) → Mapping Analyst (STM)
- **Inputs**: `chapter-4/inputs/{role}/v{N}/` (folder-versioned per role)
- **Outputs**: `chapter-4/outputs/{artifact}/v{N}/` (DRD=markdown, HLD=markdown, DMS=markdown, STM=xlsx)
- **Dependencies**: jinja2, pyyaml, openpyxl (for STM Excel workbook generation)
- **Tests**: `cd chapter-4 && uv run pytest tests/ -v`

## Pre-commit Hooks

When adding a new chapter directory (e.g., `chapter-4/`), update `.pre-commit-config.yaml`:
1. Add the chapter to the ruff `files` regex: `^(chapter-2|chapter-3|chapter-4)/`
2. Add a new `pytest-unit-chN` hook scoped to the chapter with `files: ^chapter-N/`
3. If the chapter has typed Python source, consider adding a mypy entry for it

Pytest hooks are scoped per-chapter so pushes only run tests for chapters with changed files.

## Recent Changes
- Chapter 3: BA Agent with DRD skills (create-drd, update-drd, validate-drd) for Patient 360 use case
- 003-chapter2-ai-engineering: Added Python 3.10-3.12 (aligned with existing project)
- Feature 002: DuckDB CSV Data Loader - Load 18 Synthea CSV files into DuckDB tables under `synthea` schema
