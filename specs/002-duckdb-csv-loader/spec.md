# Feature Specification: DuckDB CSV Data Loader

**Feature Branch**: `002-duckdb-csv-loader`
**Created**: 2025-12-01
**Status**: Draft
**Input**: User description: "Create DuckDB tables from raw Synthea CSV data"

## Clarifications

### Session 2025-12-01

- Q: Should the DuckDB database be named to reflect data stage (raw vs. analytics)? Should we use schema namespacing? → A: Use database name `raw.db` to reflect data stage, schema name `synthea` to reflect data source, and clean table names without prefixes. Structure: `data/duckdb/raw.db` → `synthea` schema → `patients`, `encounters`, etc. tables.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load Raw Data for Analysis (Priority: P1)

A data analyst needs to load the extracted Synthea healthcare CSV files into DuckDB so they can query the data through Apache Superset dashboards.

**Why this priority**: This is the foundational requirement - without data loaded into DuckDB, the entire analytics infrastructure is non-functional. This blocks all downstream analytics work.

**Independent Test**: Can be fully tested by running the data loading command and verifying all 18 CSV files are accessible as DuckDB tables through Superset queries.

**Acceptance Scenarios**:

1. **Given** raw Synthea CSV files exist in `data/raw/` directory, **When** analyst runs the data loading command, **Then** all 18 CSV files are imported as corresponding DuckDB tables
2. **Given** DuckDB tables have been created, **When** analyst queries any table through Superset, **Then** data is returned successfully with correct column types
3. **Given** data has already been loaded once, **When** analyst runs the loading command again, **Then** tables are refreshed without errors (idempotent operation)

---

### User Story 2 - Monitor Loading Progress (Priority: P2)

A data engineer needs visibility into the data loading process to track progress and identify issues, especially when loading large files.

**Why this priority**: Provides operational visibility and helps troubleshoot issues during loading, but the core functionality (data loading itself) can work without detailed progress reporting.

**Independent Test**: Can be tested by observing console output during the loading process and verifying progress indicators appear for each file being loaded.

**Acceptance Scenarios**:

1. **Given** loading command is executed, **When** each CSV file is being processed, **Then** progress feedback is displayed showing which table is being loaded
2. **Given** all files have been loaded, **When** loading completes, **Then** a summary is displayed showing count of tables created and total records loaded

---

### User Story 3 - Handle Missing Prerequisites (Priority: P3)

A developer needs clear error messages when prerequisites are missing, allowing them to take corrective action.

**Why this priority**: Error handling improves user experience but isn't critical for core functionality. Users can manually verify prerequisites.

**Independent Test**: Can be tested by attempting to run the loading command with missing prerequisites (no CSV files, no DuckDB database) and verifying appropriate error messages are displayed.

**Acceptance Scenarios**:

1. **Given** raw CSV files do not exist in `data/raw/`, **When** loading command is executed, **Then** clear error message indicates that raw data must be extracted first
2. **Given** virtual environment is not activated, **When** loading command is executed, **Then** error message indicates the environment setup requirement

---

### Edge Cases

- What happens when a CSV file is corrupted or has invalid data?
- How does system handle extremely large files (2.5GB claims_transactions.csv)?
- What happens when disk space is insufficient during loading?
- How does system handle schema changes in CSV files between runs?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a command to load all 18 Synthea CSV files into DuckDB tables
- **FR-002**: System MUST create tables with names matching the source CSV filenames (e.g., `patients.csv` → `patients` table)
- **FR-003**: System MUST infer column data types automatically from CSV content
- **FR-004**: System MUST replace existing tables when loading data (idempotent operation)
- **FR-005**: System MUST load all CSV files from the `data/raw/` directory
- **FR-006**: System MUST display progress feedback showing which table is currently being loaded
- **FR-007**: System MUST display a summary after loading showing the count of tables created
- **FR-008**: System MUST verify prerequisites before loading (CSV files exist, virtual environment is active)
- **FR-009**: System MUST handle large CSV files efficiently (files up to 2.5GB in size)
- **FR-010**: System MUST complete loading within reasonable time for the full dataset
- **FR-011**: System MUST create tables in the DuckDB database at `data/duckdb/raw.db` under the `synthea` schema (e.g., `synthea.patients`, `synthea.encounters`)
- **FR-012**: System MUST be safe to run multiple times without data corruption or errors

### Key Entities

- **DuckDB Tables**: 18 tables corresponding to Synthea CSV files, created in the `synthea` schema (synthea.patients, synthea.encounters, synthea.observations, synthea.claims_transactions, synthea.claims, synthea.procedures, synthea.medications, synthea.conditions, synthea.imaging_studies, synthea.careplans, synthea.payer_transitions, synthea.allergies, synthea.devices, synthea.immunizations, synthea.organizations, synthea.providers, synthea.payers, synthea.supplies)
- **CSV Files**: Raw Synthea data files in `data/raw/` directory, ranging from small files to 2.5GB
- **DuckDB Database**: Raw data database file at `data/duckdb/raw.db` containing the `synthea` schema with all imported tables

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 18 Synthea CSV files are successfully loaded into corresponding DuckDB tables
- **SC-002**: Data loading completes in under 10 minutes for the full dataset (~4.3GB total)
- **SC-003**: Analysts can query all tables through Superset without errors after data loading
- **SC-004**: Running the loading command multiple times completes successfully without data corruption
- **SC-005**: Large files (2.5GB claims_transactions.csv) load without memory errors or crashes
- **SC-006**: Users receive clear feedback during loading process showing progress and completion status

## Assumptions

- Raw Synthea CSV files have already been extracted using the existing `make raw-data-copy` command
- DuckDB database directory exists at `data/duckdb/` (database file `raw.db` will be created if it doesn't exist)
- Python virtual environment is set up with DuckDB Python package installed
- CSV files follow consistent Synthea format with headers in first row
- System has sufficient disk space (at least 10GB free) to accommodate database growth
- Default CSV parsing settings (comma-delimited, UTF-8 encoding) are appropriate for Synthea files
- Table replacement strategy is acceptable (no need to preserve historical data between loads)

## Dependencies

- Requires successful execution of `make raw-data-copy` (CSV files must exist in `data/raw/`)
- Requires DuckDB Python package (already in project dependencies)
- Requires virtual environment to be activated

## Out of Scope

- Data validation or quality checks on CSV content
- Incremental loading (only appending new records)
- Data transformations or enrichment during loading
- Schema migrations for existing tables with different structures
- Performance optimization beyond using DuckDB's native CSV reader
- Handling of CSV files in formats other than standard Synthea output
- Automated scheduling or orchestration of data loading
- Data backup before replacement
