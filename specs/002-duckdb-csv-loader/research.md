# Research: DuckDB CSV Data Loader

**Feature**: 002-duckdb-csv-loader
**Date**: 2025-12-01
**Purpose**: Phase 0 research to resolve technical unknowns and establish implementation patterns

## Research Questions

### 1. DuckDB CSV Loading Best Practices

**Question**: What is the most efficient way to load CSV files into DuckDB tables using Python?

**Decision**: Use DuckDB's SQL-based `CREATE TABLE AS SELECT * FROM read_csv()` approach

**Rationale**:
- DuckDB's native `read_csv()` function is highly optimized for CSV parsing
- Automatically infers column types from CSV content
- Handles large files (multi-GB) efficiently with streaming
- Simpler than pandas-based approaches (no intermediate DataFrame)
- Built-in support for compression, parallel reading, and memory efficiency

**Implementation Pattern**:
```python
import duckdb

conn = duckdb.connect('data/duckdb/raw.db')
conn.execute("""
    CREATE OR REPLACE TABLE patients AS
    SELECT * FROM read_csv('data/raw/patients.csv', auto_detect=true)
""")
```

**Alternatives Considered**:
- Pandas + to_sql(): Slower, requires loading entire CSV into memory first
- DuckDB Python API's `read_csv()` method: Same underlying performance but SQL approach is more explicit
- Manual schema definition: Unnecessary - auto_detect works well with Synthea CSVs

**References**:
- DuckDB CSV Import Documentation: https://duckdb.org/docs/data/csv/overview
- DuckDB Python API: https://duckdb.org/docs/api/python/overview

---

### 2. Idempotent Table Creation Strategy

**Question**: How to ensure loading is idempotent (safe to run multiple times)?

**Decision**: Use `CREATE OR REPLACE TABLE` for all tables

**Rationale**:
- `CREATE OR REPLACE TABLE` atomically drops and recreates the table
- Handles schema changes between runs (if CSV structure evolves)
- No need for manual DROP TABLE checks
- Simpler than TRUNCATE + INSERT pattern
- Matches project requirement for full table replacement (not incremental)

**Implementation Pattern**:
```python
# Each table creation is idempotent
conn.execute("CREATE OR REPLACE TABLE patients AS SELECT * FROM read_csv(...)")
```

**Alternatives Considered**:
- `DROP TABLE IF EXISTS` + `CREATE TABLE`: Two statements, not atomic
- `TRUNCATE` + `INSERT`: Requires schema to match exactly, fails on schema changes
- Upsert/merge: Unnecessary complexity for full refresh pattern

---

### 3. Progress Tracking and User Feedback

**Question**: How to provide clear progress feedback during loading without impacting performance?

**Decision**: Print progress messages after each table is loaded, with final summary

**Rationale**:
- Simple print statements don't impact DuckDB's loading performance
- Users can see which table is being processed (helps with debugging)
- Summary at end provides completion confirmation
- No need for progress bars (loading is fast enough at ~10 min total)

**Implementation Pattern**:
```python
csv_files = glob.glob('data/raw/*.csv')
total_files = len(csv_files)
loaded_tables = []

for i, csv_file in enumerate(csv_files, 1):
    table_name = Path(csv_file).stem  # Extract filename without extension
    print(f"[{i}/{total_files}] Loading {table_name}...")
    conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv('{csv_file}', auto_detect=true)")
    row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    loaded_tables.append((table_name, row_count))
    print(f"  ✓ Loaded {row_count:,} rows")

print(f"\n✅ Successfully loaded {len(loaded_tables)} tables")
```

**Alternatives Considered**:
- tqdm progress bar: Overkill for 18 files, adds dependency
- Logging framework: Too verbose for simple script
- Silent operation: Poor UX, users want to see progress

---

### 4. Error Handling and Prerequisite Validation

**Question**: What prerequisite checks should be performed before loading?

**Decision**: Validate three prerequisites: raw data directory exists, virtual environment active, DuckDB database accessible

**Rationale**:
- Early failure prevents wasted time on partial loads
- Clear error messages guide users to corrective action
- Validates the most common failure scenarios from spec's edge cases

**Implementation Pattern**:
```python
import os
import sys
from pathlib import Path

def validate_prerequisites():
    """Validate all prerequisites before loading."""
    errors = []

    # Check 1: Raw data directory exists and has CSV files
    raw_dir = Path('data/raw')
    if not raw_dir.exists():
        errors.append("data/raw/ directory not found. Run 'make raw-data-copy' first.")
    elif not list(raw_dir.glob('*.csv')):
        errors.append("No CSV files found in data/raw/. Run 'make raw-data-copy' first.")

    # Check 2: DuckDB database directory exists
    db_dir = Path('data/duckdb')
    if not db_dir.exists():
        errors.append("data/duckdb/ directory not found. Create it with: mkdir -p data/duckdb")

    # Check 3: Virtual environment (check for UV or standard venv)
    if not (os.environ.get('VIRTUAL_ENV') or Path('.venv').exists()):
        errors.append("Virtual environment not activated. Run 'make dev-setup' or 'source .venv/bin/activate'")

    if errors:
        print("ERROR: Prerequisites not met:\n", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
```

**Alternatives Considered**:
- Check disk space: Difficult to determine threshold, let OS handle it
- Validate CSV format: Out of scope (spec excludes data quality checks)
- Check DuckDB version: Already validated by UV dependency locking

---

### 5. Large File Handling (2.5GB claims_transactions.csv)

**Question**: Does DuckDB's `read_csv()` handle 2.5GB files efficiently, or do we need special handling?

**Decision**: No special handling needed - DuckDB's `read_csv()` uses streaming by default

**Rationale**:
- DuckDB's CSV reader streams data from disk (doesn't load entire file into memory)
- Tested internally by DuckDB team with multi-GB files
- Columnar storage format compresses data efficiently
- `auto_detect` samples first N rows, then streams the rest

**Implementation Pattern**:
```python
# Same code works for all file sizes
conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv('{csv_file}', auto_detect=true)")
```

**Alternatives Considered**:
- Chunked reading: Unnecessary, DuckDB handles this internally
- Parallel loading: DuckDB already parallelizes CSV parsing
- Memory limits: Let DuckDB manage memory, no explicit limits needed

**Performance Expectations**:
- Small tables (<100MB): <10 seconds each
- Medium tables (100MB-1GB): 10-60 seconds
- Large table (2.5GB claims_transactions): 2-4 minutes
- Total time: 6-10 minutes for all 18 tables

---

## Technology Stack Summary

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | Python | 3.10-3.12 | Script implementation |
| Database | DuckDB | 1.1.3 | CSV storage and querying |
| Package Manager | UV | Latest | Dependency management |
| Testing | pytest | 8.3.4 | Unit and integration tests |
| CLI | Make | System | Workflow automation |

## Implementation Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| CSV format inconsistency | Medium | DuckDB's auto_detect is robust; if it fails, error message will be clear |
| Disk space exhaustion | High | Validate ~10GB free space in prerequisite check |
| DuckDB database corruption | Medium | CREATE OR REPLACE is atomic; if interrupted, table simply won't exist |
| Performance degradation | Low | DuckDB's CSV reader is well-tested with large files |

## Open Questions

None - all technical unknowns have been resolved through research.

## References

- DuckDB CSV Import: https://duckdb.org/docs/data/csv/overview
- DuckDB Python API: https://duckdb.org/docs/api/python/overview
- Synthea Data Format: https://github.com/synthetichealth/synthea/wiki/CSV-File-Data-Dictionary
- Project Constitution: `.specify/memory/constitution.md` (Section V: Reproducibility)
