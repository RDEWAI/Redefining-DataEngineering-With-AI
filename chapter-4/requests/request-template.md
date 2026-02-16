# [Project Name] Data Pipeline

## Business Context
[Brief description of the project and business objectives]

## Data Sources

### Source Type
<!-- IMPORTANT: Specify EXACTLY ONE of the following -->

**Option A - CSV Files (Raw Data)**
```
type: csv
path: <relative_or_absolute_path_to_csv_directory>
files:
  - file1.csv - [description]
  - file2.csv - [description]
```

**Option B - DuckDB Database (Pre-loaded)**
```
type: duckdb
database: <path_to_database.db>
schema: <schema_name>
```

**Option C - Both (CSV to be loaded into DuckDB)**
```
type: csv_to_duckdb
csv_path: <path_to_csv_directory>
database: <path_to_database.db>
schema: <schema_name>
```

### Current Data Source Configuration
<!-- Fill in ONE of the above options here -->

type: [csv | duckdb | csv_to_duckdb]
path: [your path here]

### Data Files / Tables
<!-- List your data files or tables -->
- [file/table 1] - [description]
- [file/table 2] - [description]

## Requirements
[List your data pipeline requirements]
- Requirement 1
- Requirement 2

## Expected Outcomes
[What should the pipeline produce?]
- Outcome 1
- Outcome 2
