# Implementation Plan: DuckDB CSV Data Loader

**Branch**: `002-duckdb-csv-loader` | **Date**: 2025-12-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-duckdb-csv-loader/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create a Makefile target and Python script to load 18 Synthea CSV files (~4.3GB total) from `data/raw/` into DuckDB tables at `data/duckdb/raw.db`. The solution uses DuckDB's native CSV reader for efficient loading of large files (up to 2.5GB), provides progress feedback, validates prerequisites, and is idempotent (safe to run multiple times). This enables data analysts to query Synthea healthcare data through Apache Superset dashboards.

## Technical Context

**Language/Version**: Python 3.10-3.12 (project requires-python = ">=3.10,<3.13")
**Primary Dependencies**: DuckDB 1.1.3 (Python package), UV package manager for environment
**Storage**: DuckDB file-based database at `data/duckdb/raw.db` with `synthea` schema
**Testing**: pytest 8.3.4 (already in dependencies)
**Target Platform**: Local development (macOS/Linux), UV-managed virtual environment
**Project Type**: Single project (data engineering scripts)
**Performance Goals**: Complete loading in under 10 minutes for 4.3GB dataset
**Constraints**: Handle 2.5GB CSV files without memory errors, idempotent execution
**Scale/Scope**: 18 tables, ~4.3GB data, largest single file 2.5GB

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Quality Gates Assessment

| Gate | Requirement | Status | Notes |
|------|-------------|--------|-------|
| **Linting & Type Checking** | pylint, flake8, mypy (zero errors) | ✅ PASS | Script will follow PEP 8, use type hints |
| **Unit Test Suite** | pytest unit tests (100% pass, ≥80% coverage) | ✅ PASS | Will test CSV discovery, table creation logic |
| **Integration Test Suite** | pytest integration tests (100% pass) | ✅ PASS | Will test actual CSV loading with sample data |
| **UV Dependency Resolution** | `uv sync` succeeds | ✅ PASS | DuckDB already in pyproject.toml |
| **Environment Validation** | `make dev-setup` passes | ✅ PASS | No new system dependencies required |
| **Documentation Updates** | User-facing changes documented | ✅ PASS | Will document new `make load-raw-data` target |

### Constitutional Compliance

**Code Quality & Maintainability (Section I)**:
- Script will use type hints for all functions
- Google-style docstrings for public functions
- PEP 8 compliance via linting
- Complexity kept low (simple loop over CSV files)

**Testing Standards (Section II)**:
- Unit tests: CSV file discovery, table name mapping, prerequisite checks
- Integration tests: Load sample CSV into DuckDB, verify table creation
- Data quality: Verify row counts match CSV files
- Tests runnable via `uv run pytest` and `make test`

**User Experience Consistency (Section III)**:
- Clear progress feedback (e.g., "Loading patients.csv... [1/18]")
- Actionable error messages (e.g., "Run 'make raw-data-copy' first")
- Summary output showing tables created and row counts
- Makefile target follows existing pattern (`make load-raw-data`)

**Performance & Scalability (Section IV)**:
- Use DuckDB's native `read_csv()` for efficient loading
- No premature optimization beyond DuckDB's defaults
- Memory-efficient streaming for 2.5GB files
- Progress tracking doesn't impact performance

**Reproducibility & Environment Consistency (Section V)**:
- No new dependencies (DuckDB already in pyproject.toml)
- UV lock file unchanged
- Script works in UV-managed virtual environment
- Idempotent execution (safe to re-run)

## Project Structure

### Documentation (this feature)

```text
specs/002-duckdb-csv-loader/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── csv-loader-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
scripts/
├── add_duckdb_connection.py      # Existing: Superset DuckDB setup
└── load_raw_csv_to_duckdb.py     # NEW: CSV loader script

tests/
├── integration/
│   ├── test_makefile_targets.py  # Existing: Makefile integration tests
│   └── test_csv_loader.py        # NEW: CSV loading integration tests
└── unit/
    ├── test_basic_setup.py       # Existing: Environment tests
    └── test_csv_loader_unit.py   # NEW: CSV loader unit tests

data/
├── raw/                          # Existing: Synthea CSV files (18 files)
└── duckdb/
    └── raw.db                    # NEW: DuckDB database with synthea schema

Makefile                          # Updated: Add load-raw-data target
```

**Structure Decision**: This is a single-project Python data engineering repository. The feature adds one new script in `scripts/` and corresponding tests in `tests/unit/` and `tests/integration/`. It follows the existing pattern where utility scripts live in `scripts/` and are invoked via Makefile targets.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All constitutional requirements can be met with this design.

---

## Phase 0: Research (Complete)

**Artifact**: `research.md`

**Key Decisions**:
1. Use DuckDB's SQL-based `CREATE TABLE AS SELECT * FROM read_csv()` for loading
2. Use `CREATE OR REPLACE TABLE` for idempotent execution
3. Simple progress tracking with print statements after each table
4. Validate three prerequisites: raw data directory, DuckDB directory, virtual environment
5. No special handling for large files - DuckDB streams efficiently by default

**Technology Stack Confirmed**:
- Python 3.10-3.12 (existing project requirement)
- DuckDB 1.1.3 Python package (already in dependencies)
- pytest 8.3.4 (already in dependencies)
- UV package manager (existing project standard)

---

## Phase 1: Design & Contracts (Complete)

**Artifacts**:
- `data-model.md` - 18 Synthea healthcare tables with entity relationships
- `contracts/csv-loader-api.md` - Script interface, Makefile contract, error handling
- `quickstart.md` - User guide with step-by-step instructions

**Data Model**:
- 18 tables matching Synthea CSV files
- Schema auto-inferred by DuckDB
- Estimated 15-20M rows, 4.3GB CSV compressed to ~2-3GB in DuckDB
- Entity relationships documented (patients → encounters → observations, etc.)

**API Contract**:
- Makefile target: `make load-raw-data`
- Python script: `scripts/load_raw_csv_to_duckdb.py`
- Exit codes: 0 (success), 1 (prerequisites), 2 (CSV format), 3 (DuckDB error)
- Idempotent execution guaranteed via `CREATE OR REPLACE TABLE`
- Progress output with row counts and timing

**Agent Context Updated**:
- CLAUDE.md updated with Python 3.10-3.12, DuckDB 1.1.3, UV package manager
- Technologies tracked for feature 002-duckdb-csv-loader

---

## Constitution Check (Post-Phase 1 Re-evaluation)

*GATE: Re-check after Phase 1 design completion*

### Quality Gates Assessment (Unchanged)

All quality gates remain ✅ PASS:
- Linting & Type Checking: Design follows PEP 8, will use type hints
- Unit Test Suite: 6 unit tests planned (CSV discovery, validation, table naming)
- Integration Test Suite: 6 integration tests planned (single CSV, all CSVs, idempotency, etc.)
- UV Dependency Resolution: No new dependencies added
- Environment Validation: No changes to dev-setup requirements
- Documentation Updates: quickstart.md created, README will be updated

### Constitutional Compliance (Unchanged)

**Code Quality & Maintainability (Section I)**: ✅ PASS
- Script design is simple (main loop over CSV files)
- Function signatures defined with type hints in contract
- Complexity will be low (<10 cyclomatic complexity per function)

**Testing Standards (Section II)**: ✅ PASS
- Unit tests: 6 planned for core logic
- Integration tests: 6 planned for end-to-end workflows
- Contract tests: CSV → DuckDB table schema validation
- Data quality: Row count verification tests

**User Experience Consistency (Section III)**: ✅ PASS
- Clear progress feedback designed (e.g., "[1/18] Loading patients...")
- Actionable error messages specified in contract
- Makefile target follows existing project pattern
- Quickstart guide provides step-by-step instructions

**Performance & Scalability (Section IV)**: ✅ PASS
- DuckDB's native CSV reader is optimized for large files
- No premature optimization - using DuckDB defaults
- Expected performance: 6-10 minutes for 4.3GB dataset
- Performance tested during integration tests

**Reproducibility & Environment Consistency (Section V)**: ✅ PASS
- No new dependencies (DuckDB already in pyproject.toml)
- UV lock file unchanged
- Script works in UV-managed virtual environment
- Idempotent execution design

**Final Result**: ✅ ALL GATES PASS - Ready for Phase 2 (Task Generation)

---

## Phase 2: Task Generation (Next Step)

**Not completed by this command** - Use `/speckit.tasks` to generate `tasks.md`

The `/speckit.tasks` command will:
1. Break down implementation into atomic tasks
2. Define task dependencies
3. Create acceptance criteria for each task
4. Generate task checklist for tracking

---

## Summary

**Planning Status**: ✅ Complete (Phase 0 + Phase 1)

**Artifacts Created**:
- ✅ `plan.md` - This implementation plan
- ✅ `research.md` - Technical decisions and patterns
- ✅ `data-model.md` - 18 Synthea tables with entity relationships
- ✅ `contracts/csv-loader-api.md` - Script and Makefile interface contract
- ✅ `quickstart.md` - User guide for loading CSV data
- ✅ `CLAUDE.md` - Updated agent context

**Next Steps**:
1. Run `/speckit.tasks` to generate actionable task list
2. Implement tasks following the plan
3. Run tests to verify compliance with constitution
4. Create pull request for review

**Key Implementation Files** (to be created during implementation):
- `scripts/load_raw_csv_to_duckdb.py` - CSV loader script
- `tests/unit/test_csv_loader_unit.py` - Unit tests
- `tests/integration/test_csv_loader.py` - Integration tests
- `Makefile` - Updated with `load-raw-data` target

**Constitutional Compliance**: ✅ All requirements met, no violations

**Estimated Implementation Time**: 4-6 hours
- Script implementation: 2-3 hours
- Test implementation: 1-2 hours
- Makefile integration: 30 minutes
- Documentation updates: 30 minutes
