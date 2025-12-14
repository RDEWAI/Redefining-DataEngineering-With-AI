# Claude Code Instructions

Add project-specific instructions for Claude Code here.

## Active Technologies
- Python 3.10-3.12 (aligned with existing project) (003-chapter3-ai-engineering)
- DuckDB at `chapter-3/data/duckdb/library.db` with `library` schema (003-chapter3-ai-engineering)

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

## Recent Changes
- 003-chapter3-ai-engineering: Added Python 3.10-3.12 (aligned with existing project)

- Feature 002: DuckDB CSV Data Loader - Load 18 Synthea CSV files into DuckDB tables under `synthea` schema
