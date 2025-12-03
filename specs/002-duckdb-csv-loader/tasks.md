# Tasks: DuckDB CSV Data Loader

**Input**: Design documents from `/specs/002-duckdb-csv-loader/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included (required by project constitution for quality gates compliance)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- **Scripts**: `scripts/` at repository root
- **Tests**: `tests/unit/`, `tests/integration/` at repository root
- **Data**: `data/raw/` (CSV input), `data/duckdb/raw.db` (DuckDB output)
- **Build**: `Makefile` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project structure validation and prerequisite files

- [x] T001 Verify project structure matches plan.md - `scripts/`, `tests/unit/`, `tests/integration/` directories exist
- [x] T002 [P] Create empty `scripts/load_raw_csv_to_duckdb.py` with module docstring and imports
- [x] T003 [P] Create empty `tests/unit/test_csv_loader_unit.py` with pytest imports and test class skeleton
- [x] T004 [P] Create empty `tests/integration/test_csv_loader.py` with pytest imports and test class skeleton

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Define constants and paths in `scripts/load_raw_csv_to_duckdb.py`: RAW_DIR=`data/raw`, DB_PATH=`data/duckdb/raw.db`, SCHEMA_NAME=`synthea`
- [x] T006 [P] Implement `get_table_name(csv_path: Path) -> str` function in `scripts/load_raw_csv_to_duckdb.py` - extracts table name from CSV filename
- [x] T007 [P] Implement `discover_csv_files(raw_dir: Path) -> List[Path]` function in `scripts/load_raw_csv_to_duckdb.py` - returns sorted list of CSV files
- [x] T008 Implement `create_schema_if_not_exists(conn: duckdb.DuckDBPyConnection, schema: str)` function in `scripts/load_raw_csv_to_duckdb.py` - creates synthea schema

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Load Raw Data for Analysis (Priority: P1) 🎯 MVP

**Goal**: Load all 18 Synthea CSV files from `data/raw/` into DuckDB tables at `data/duckdb/raw.db` under the `synthea` schema

**Independent Test**: Run `make load-raw-data`, then query `SELECT COUNT(*) FROM synthea.patients` in DuckDB - should return rows

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T009 [P] [US1] Unit test `test_get_table_name()` in `tests/unit/test_csv_loader_unit.py` - verify `patients.csv` → `patients`
- [x] T010 [P] [US1] Unit test `test_discover_csv_files()` in `tests/unit/test_csv_loader_unit.py` - verify CSV discovery with mock directory
- [x] T011 [P] [US1] Integration test `test_load_single_csv()` in `tests/integration/test_csv_loader.py` - load one CSV, verify table exists
- [x] T012 [P] [US1] Integration test `test_load_all_csvs()` in `tests/integration/test_csv_loader.py` - verify all 18 tables created in synthea schema

### Implementation for User Story 1

- [x] T013 [US1] Implement `load_csv_to_table(conn, csv_path, table_name, schema)` function in `scripts/load_raw_csv_to_duckdb.py` - uses `CREATE OR REPLACE TABLE {schema}.{table} AS SELECT * FROM read_csv()`
- [x] T014 [US1] Implement `load_all_csvs(conn, csv_files, schema) -> List[Tuple[str, int]]` function in `scripts/load_raw_csv_to_duckdb.py` - loops over CSV files, returns table names and row counts
- [x] T015 [US1] Implement `main()` function in `scripts/load_raw_csv_to_duckdb.py` - orchestrates connection, schema creation, loading, returns exit code
- [x] T016 [US1] Add `load-raw-data` target to `Makefile` - calls `.venv/bin/python scripts/load_raw_csv_to_duckdb.py`
- [x] T017 [US1] Integration test `test_idempotent_loading()` in `tests/integration/test_csv_loader.py` - run loader twice, verify no errors
- [x] T018 [US1] Integration test `test_row_counts_match()` in `tests/integration/test_csv_loader.py` - verify row counts > 0 for each table

**Checkpoint**: At this point, User Story 1 should be fully functional - `make load-raw-data` creates all 18 tables in `synthea` schema

---

## Phase 4: User Story 2 - Monitor Loading Progress (Priority: P2)

**Goal**: Display progress feedback during loading process showing which table is being loaded and summary at end

**Independent Test**: Run `make load-raw-data` and observe console output shows `[1/18] Loading patients...` format with row counts

### Tests for User Story 2

- [x] T019 [P] [US2] Unit test `test_progress_output_format()` in `tests/unit/test_csv_loader_unit.py` - verify progress message format with mock
- [x] T020 [P] [US2] Unit test `test_summary_output_format()` in `tests/unit/test_csv_loader_unit.py` - verify summary includes total tables and rows

### Implementation for User Story 2

- [x] T021 [US2] Add progress printing to `load_all_csvs()` in `scripts/load_raw_csv_to_duckdb.py` - print `[N/18] Loading {table}...` before each file
- [x] T022 [US2] Add row count feedback after each table in `scripts/load_raw_csv_to_duckdb.py` - print `  ✓ Loaded {count:,} rows`
- [x] T023 [US2] Implement `print_summary(results: List[Tuple[str, int]], elapsed: float)` in `scripts/load_raw_csv_to_duckdb.py` - shows total tables, total rows, time
- [x] T024 [US2] Add timing to `main()` in `scripts/load_raw_csv_to_duckdb.py` - track start/end time, pass to summary
- [x] T025 [US2] Update Makefile `load-raw-data` target with header `=== Loading CSV data into DuckDB ===`

**Checkpoint**: Loading now shows clear progress and summary - user can monitor loading of large files

---

## Phase 5: User Story 3 - Handle Missing Prerequisites (Priority: P3)

**Goal**: Validate prerequisites before loading and display actionable error messages when missing

**Independent Test**: Remove `data/raw/` directory, run `make load-raw-data`, verify error message says "Run 'make raw-data-copy' first"

### Tests for User Story 3

- [x] T026 [P] [US3] Unit test `test_validate_prerequisites_success()` in `tests/unit/test_csv_loader_unit.py` - verify passes with valid setup
- [x] T027 [P] [US3] Unit test `test_validate_prerequisites_missing_raw_dir()` in `tests/unit/test_csv_loader_unit.py` - verify error on missing data/raw/
- [x] T028 [P] [US3] Unit test `test_validate_prerequisites_no_csv_files()` in `tests/unit/test_csv_loader_unit.py` - verify error on empty data/raw/

### Implementation for User Story 3

- [x] T029 [US3] Implement `validate_prerequisites() -> None` function in `scripts/load_raw_csv_to_duckdb.py` - checks raw dir exists, has CSV files, duckdb dir exists
- [x] T030 [US3] Add prerequisite check call at start of `main()` in `scripts/load_raw_csv_to_duckdb.py` - calls `validate_prerequisites()` before connection
- [x] T031 [US3] Add actionable error messages in `validate_prerequisites()` - e.g., "Run 'make raw-data-copy' first"
- [x] T032 [US3] Add prerequisite check step to Makefile `load-raw-data` target - prints `[1/3] Checking prerequisites...`
- [x] T033 [US3] Integration test `test_missing_prerequisites_error()` in `tests/integration/test_csv_loader.py` - verify exit code 1 and error message format

**Checkpoint**: Script now fails gracefully with helpful messages when prerequisites are missing

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements that affect multiple user stories

- [x] T034 [P] Add type hints to all functions in `scripts/load_raw_csv_to_duckdb.py`
- [x] T035 [P] Add Google-style docstrings to all public functions in `scripts/load_raw_csv_to_duckdb.py`
- [x] T036 [P] Add `#!/usr/bin/env python3` shebang and `if __name__ == "__main__":` guard to `scripts/load_raw_csv_to_duckdb.py`
- [x] T037 Run `uv run pytest tests/` to verify all tests pass
- [x] T038 Run linting (ruff/flake8) on `scripts/load_raw_csv_to_duckdb.py` and fix any issues
- [x] T039 Update `scripts/add_duckdb_connection.py` to use new `data/duckdb/raw.db` path instead of `analytics.db`
- [x] T040 Validate quickstart.md steps work end-to-end: `make raw-data-copy` → `make load-raw-data` → query in Superset
- [x] T041 Update README.md with new `make load-raw-data` target documentation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories - **THIS IS THE MVP**
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Enhances US1 but is independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Enhances US1/US2 but is independently testable

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Core loading functions before orchestration
3. Main function before Makefile integration
4. Story complete before moving to next priority

### Parallel Opportunities

Within each phase, tasks marked [P] can run in parallel:

- **Phase 1**: T002, T003, T004 (different files)
- **Phase 2**: T006, T007 (independent functions)
- **Phase 3 Tests**: T009, T010, T011, T012 (different test files/functions)
- **Phase 4 Tests**: T019, T020 (independent test functions)
- **Phase 5 Tests**: T026, T027, T028 (independent test functions)
- **Phase 6**: T034, T035, T036 (different aspects of same file, no conflicts)

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test test_get_table_name() in tests/unit/test_csv_loader_unit.py"
Task: "Unit test test_discover_csv_files() in tests/unit/test_csv_loader_unit.py"
Task: "Integration test test_load_single_csv() in tests/integration/test_csv_loader.py"
Task: "Integration test test_load_all_csvs() in tests/integration/test_csv_loader.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (4 tasks)
2. Complete Phase 2: Foundational (4 tasks)
3. Complete Phase 3: User Story 1 (10 tasks)
4. **STOP and VALIDATE**: Run `make load-raw-data`, verify 18 tables exist in `synthea` schema
5. Deploy/demo if ready - **MVP complete with 18 tasks**

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (8 tasks)
2. Add User Story 1 → Test independently → **MVP!** (18 tasks total)
3. Add User Story 2 → Progress feedback visible (25 tasks total)
4. Add User Story 3 → Error handling complete (33 tasks total)
5. Add Polish → Production ready (41 tasks total)

### Single Developer Strategy (Recommended)

Execute in strict priority order:
1. Phase 1 → Phase 2 → Phase 3 (US1) → **Validate MVP works**
2. Phase 4 (US2) → **Validate progress output**
3. Phase 5 (US3) → **Validate error handling**
4. Phase 6 → **Final polish and validation**

---

## Summary

| Metric | Count |
|--------|-------|
| **Total Tasks** | 41 |
| **Setup Tasks** | 4 |
| **Foundational Tasks** | 4 |
| **User Story 1 Tasks** | 10 |
| **User Story 2 Tasks** | 7 |
| **User Story 3 Tasks** | 8 |
| **Polish Tasks** | 8 |
| **Parallelizable Tasks** | 18 |

### MVP Scope

**User Story 1 alone delivers the MVP**: Load all 18 CSV files into DuckDB tables in `synthea` schema.

- **Tasks to MVP**: 18 (Setup + Foundational + US1)
- **Estimated time**: 2-3 hours
- **Result**: `make load-raw-data` creates all tables, queryable via Superset

### Key Files Created

| File | Purpose |
|------|---------|
| `scripts/load_raw_csv_to_duckdb.py` | Main CSV loader script |
| `tests/unit/test_csv_loader_unit.py` | Unit tests for loader functions |
| `tests/integration/test_csv_loader.py` | Integration tests for end-to-end loading |
| `Makefile` (updated) | New `load-raw-data` target |

---

## Notes

- [P] tasks = different files or independent code, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Database path: `data/duckdb/raw.db` (not `analytics.db` per clarification)
- Schema: `synthea` (tables accessed as `synthea.patients`, `synthea.encounters`, etc.)
