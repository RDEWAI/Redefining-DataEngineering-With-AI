# API Contract: CSV Loader Script

**Feature**: 002-duckdb-csv-loader
**Date**: 2025-12-01
**Purpose**: Define the interface contract for the CSV loader script and Makefile target

## Overview

This contract defines the interface between:
1. Users invoking the `make load-raw-data` command
2. The Makefile target implementation
3. The Python script `scripts/load_raw_csv_to_duckdb.py`
4. The DuckDB database and CSV files

## Makefile Target Contract

### make load-raw-data

**Purpose**: Load all Synthea CSV files from `data/raw/` into DuckDB tables

**Prerequisites**:
- Virtual environment exists at `.venv/`
- DuckDB Python package installed (via `make dev-setup`)
- Raw CSV files exist in `data/raw/` (via `make raw-data-copy`)
- DuckDB directory exists at `data/duckdb/`

**Invocation**:
```bash
make load-raw-data
```

**Exit Codes**:
- `0`: Success - all CSV files loaded successfully
- `1`: Prerequisites not met (missing files, environment not set up)
- `3`: Execution failure (DuckDB error, permission issue, disk full)

**Output Format**:

```text
=== Loading CSV data into DuckDB ===

[1/3] Checking prerequisites...
✓ Virtual environment exists
✓ Raw data directory contains 18 CSV files
✓ DuckDB database directory exists

[2/3] Loading CSV files into DuckDB tables...

[1/18] Loading patients...
  ✓ Loaded 124,000 rows in 2.3s

[2/18] Loading encounters...
  ✓ Loaded 515,000 rows in 8.1s

[3/18] Loading observations...
  ✓ Loaded 4,200,000 rows in 45.2s

[4/18] Loading claims_transactions...
  ✓ Loaded 8,500,000 rows in 180.5s

... [remaining tables]

[3/3] Validating loaded tables...
✓ All 18 tables created successfully

✅ Data loading complete!

Summary:
  Tables created: 18
  Total rows loaded: 15,234,567
  Total time: 8m 32s

DuckDB tables are now available in: data/duckdb/raw.db (synthea schema)
Query via Superset at: http://localhost:8088
```

**Error Output Examples**:

```text
ERROR: Prerequisites not met:
  - data/raw/ directory not found. Run 'make raw-data-copy' first.

Run 'make help' for available commands.
```

```text
ERROR: Failed to load claims_transactions.csv:
  DuckDB error: out of disk space

Free up disk space and try again.
```

**Idempotent Behavior**:
- Running `make load-raw-data` multiple times is safe
- Each run replaces existing tables with fresh data from CSV files
- No manual cleanup required between runs

---

## Python Script Contract

### scripts/load_raw_csv_to_duckdb.py

**Purpose**: Python script that performs the actual CSV loading logic

**Invocation**:
```bash
python scripts/load_raw_csv_to_duckdb.py
# OR
.venv/bin/python scripts/load_raw_csv_to_duckdb.py
```

**Command-Line Arguments**: None (uses fixed paths from project structure)

**Environment Variables**: None required

**Exit Codes**:
- `0`: Success
- `1`: Prerequisites not met
- `2`: Invalid CSV format or schema error
- `3`: DuckDB connection or execution error

### Function Signatures

#### validate_prerequisites()
```python
def validate_prerequisites() -> None:
    """
    Validate all prerequisites before loading.

    Checks:
    - data/raw/ directory exists and contains .csv files
    - data/duckdb/ directory exists
    - Virtual environment is active

    Raises:
        SystemExit: If any prerequisite is not met (exit code 1)
    """
```

#### discover_csv_files()
```python
def discover_csv_files(raw_dir: Path = Path('data/raw')) -> List[Path]:
    """
    Discover all CSV files in the raw data directory.

    Args:
        raw_dir: Path to directory containing CSV files (default: data/raw)

    Returns:
        List of Path objects for each CSV file, sorted alphabetically

    Raises:
        FileNotFoundError: If raw_dir does not exist
    """
```

#### get_table_name()
```python
def get_table_name(csv_path: Path) -> str:
    """
    Extract table name from CSV filename.

    Args:
        csv_path: Path to CSV file

    Returns:
        Table name (filename without .csv extension)

    Example:
        >>> get_table_name(Path('data/raw/patients.csv'))
        'patients'
    """
```

#### load_csv_to_table()
```python
def load_csv_to_table(
    conn: duckdb.DuckDBPyConnection,
    csv_path: Path,
    table_name: str
) -> int:
    """
    Load a single CSV file into a DuckDB table.

    Args:
        conn: DuckDB connection object
        csv_path: Path to CSV file
        table_name: Name of table to create

    Returns:
        Number of rows loaded

    Raises:
        duckdb.Error: If table creation or CSV loading fails
    """
```

#### main()
```python
def main() -> int:
    """
    Main entry point for CSV loading script.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
```

---

## DuckDB Database Contract

### Database Location
**Path**: `data/duckdb/raw.db`
**Schema**: `synthea`

### Connection String
```python
import duckdb
conn = duckdb.connect('data/duckdb/raw.db')
```

### Schema Creation
```sql
CREATE SCHEMA IF NOT EXISTS synthea;
```

### Table Creation Pattern

For each CSV file `{name}.csv`, create table `synthea.{name}`:

```sql
CREATE OR REPLACE TABLE synthea.{table_name} AS
SELECT * FROM read_csv('{csv_path}', auto_detect=true)
```

**Parameters**:
- `auto_detect=true`: Automatically infer schema from CSV
- Default settings: UTF-8 encoding, comma delimiter, header row

### Expected Tables

After successful loading, these 18 tables must exist in the `synthea` schema:

| Table Name | Full Path | Source CSV |
|------------|-----------|------------|
| patients | synthea.patients | patients.csv |
| encounters | synthea.encounters | encounters.csv |
| observations | synthea.observations | observations.csv |
| claims_transactions | synthea.claims_transactions | claims_transactions.csv |
| claims | synthea.claims | claims.csv |
| procedures | synthea.procedures | procedures.csv |
| medications | synthea.medications | medications.csv |
| conditions | synthea.conditions | conditions.csv |
| imaging_studies | synthea.imaging_studies | imaging_studies.csv |
| careplans | synthea.careplans | careplans.csv |
| payer_transitions | synthea.payer_transitions | payer_transitions.csv |
| allergies | synthea.allergies | allergies.csv |
| devices | synthea.devices | devices.csv |
| immunizations | synthea.immunizations | immunizations.csv |
| organizations | synthea.organizations | organizations.csv |
| providers | synthea.providers | providers.csv |
| payers | synthea.payers | payers.csv |
| supplies | synthea.supplies | supplies.csv |

### Table Schema

Each table's schema is inferred from CSV content. Common column types:

- **IDs**: `VARCHAR` (UUIDs from Synthea)
- **Names/Descriptions**: `VARCHAR`
- **Dates**: `DATE` or `TIMESTAMP`
- **Numeric Values**: `DOUBLE` or `BIGINT`
- **Codes**: `VARCHAR`

---

## CSV File Contract

### Input Location
**Directory**: `data/raw/`

### File Format
- **Encoding**: UTF-8
- **Delimiter**: Comma (`,`)
- **Quote Character**: Double quote (`"`)
- **Header Row**: First row contains column names
- **Escape Character**: Backslash (`\`)

### File Naming Convention
- Lowercase with underscores
- Extension: `.csv`
- Examples: `patients.csv`, `claims_transactions.csv`

### Expected Files (18 total)
All Synthea-generated CSV files should be present:
- Core patient data: `patients.csv`
- Encounter data: `encounters.csv`, `observations.csv`
- Clinical data: `conditions.csv`, `procedures.csv`, `medications.csv`, `allergies.csv`, `immunizations.csv`, `careplans.csv`, `devices.csv`, `imaging_studies.csv`, `supplies.csv`
- Financial data: `claims.csv`, `claims_transactions.csv`
- Reference data: `organizations.csv`, `providers.csv`, `payers.csv`, `payer_transitions.csv`

### File Size Ranges
- Small (<10MB): organizations, providers, payers, allergies, devices, immunizations, supplies, careplans, imaging_studies
- Medium (10-100MB): patients, payer_transitions
- Large (100MB-1GB): encounters, conditions, procedures, medications, claims
- Very Large (>1GB): observations (~772MB), claims_transactions (~2.5GB)

---

## Error Handling Contract

### Error Categories and Responses

#### Category 1: Prerequisites Not Met (Exit Code 1)

**Condition**: Required files or environment not ready

**Examples**:
- `data/raw/` directory missing or empty
- Virtual environment not activated
- `data/duckdb/` directory missing

**Response**:
- Print clear error message listing missing prerequisites
- Suggest corrective action (e.g., "Run 'make raw-data-copy'")
- Exit with code 1

#### Category 2: CSV Format Errors (Exit Code 2)

**Condition**: CSV file is malformed or unreadable

**Examples**:
- Corrupted file
- Encoding error
- Missing header row

**Response**:
- Print error message identifying problematic file
- Include DuckDB error details
- Exit with code 2

#### Category 3: DuckDB Execution Errors (Exit Code 3)

**Condition**: Database operation fails

**Examples**:
- Disk full during table creation
- Permission denied writing to database
- DuckDB internal error

**Response**:
- Print error message with table name
- Include DuckDB error message
- Suggest corrective action if known
- Exit with code 3

---

## Performance Contract

### Loading Time Expectations

**Target**: Complete loading in under 10 minutes for full 4.3GB dataset

**Per-File Time Estimates**:
- Small files (<10MB): <5 seconds each
- Medium files (10-100MB): 5-30 seconds each
- Large files (100MB-1GB): 30 seconds - 2 minutes each
- observations (772MB): ~1-2 minutes
- claims_transactions (2.5GB): ~3-5 minutes

**Total Expected Time**: 6-10 minutes

**Performance Characteristics**:
- Streaming: CSV data is streamed from disk (not fully loaded into memory)
- Parallel: DuckDB parallelizes CSV parsing across CPU cores
- Compression: Data is compressed in DuckDB's columnar storage

---

## Testing Contract

### Unit Test Coverage

Tests in `tests/unit/test_csv_loader_unit.py`:

1. `test_get_table_name()` - Verify table name extraction from CSV path
2. `test_discover_csv_files()` - Verify CSV file discovery logic
3. `test_validate_prerequisites_success()` - Verify prerequisite validation passes
4. `test_validate_prerequisites_missing_raw_dir()` - Verify error on missing data/raw/
5. `test_validate_prerequisites_no_csv_files()` - Verify error on empty data/raw/
6. `test_validate_prerequisites_no_venv()` - Verify error on missing virtual environment

### Integration Test Coverage

Tests in `tests/integration/test_csv_loader.py`:

1. `test_load_single_csv()` - Load one CSV file and verify table creation
2. `test_load_all_csvs()` - Load all 18 CSV files and verify all tables exist
3. `test_idempotent_loading()` - Load data twice and verify no errors
4. `test_row_counts_match()` - Verify row counts match CSV line counts
5. `test_table_schemas()` - Verify inferred schemas are reasonable
6. `test_makefile_target()` - Run `make load-raw-data` and verify success

---

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10-3.12 | Specified in pyproject.toml |
| DuckDB | 1.1.3 | Locked in dependencies |
| Synthea CSV Format | v3.x | Standard Synthea output format |
| Make | Any | Standard make, no special features required |

---

## Future Extensions (Out of Scope)

The following are explicitly out of scope for this feature but documented for future reference:

- Incremental loading (append new records only)
- Data validation and quality checks
- Schema migrations for existing tables
- Custom column type mappings
- Parallel loading of multiple files
- Progress percentage (vs. count)
- Retry logic on transient failures
- Data backup before replacement
