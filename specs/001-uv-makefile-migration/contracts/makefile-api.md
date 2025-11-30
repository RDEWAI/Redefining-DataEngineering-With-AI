# Makefile API Contract

**Feature**: UV Package Manager Migration and Makefile Development Workflow
**Version**: 1.0.0
**Last Updated**: 2025-11-12

This document defines the interface contract for all Makefile targets in the project.

---

## Target: help (default)

**Purpose**: Display available Makefile targets and usage instructions

**Prerequisites**: None

**Inputs**: None

**Outputs**: Help text to stdout with color-coded target names and descriptions

**Side Effects**: None

**Exit Codes**:
- `0`: Success

**Idempotency**: Safe to run multiple times

**Usage**:
```bash
make
# or
make help
```

**Expected Output**:
```
Available targets:

  clean                Remove generated files and virtual environment
  dev-setup            Set up development environment with UV
  help                 Show this help message
  raw-data-copy        Extract Synthea CSV data from Docker image
  superset-init        Initialize Apache Superset database and admin user
  superset-run         Start Superset web server on localhost:8088
  test                 Run test suite

Usage: make <target>
```

---

## Target: dev-setup

**Purpose**: Set up local development environment with all dependencies using UV package manager

**Prerequisites**:
- UV package manager installed
- Python 3.10 or 3.11 available in PATH

**Inputs**:
- `pyproject.toml` (dependency specification)
- `uv.lock` (lock file, if exists)

**Outputs**:
- `.venv/` directory with virtual environment
- Installed Python packages (DuckDB, SQLMesh, Superset, pytest, etc.)

**Side Effects**:
- Creates/updates `.venv` directory
- Downloads and installs packages from PyPI
- Generates/updates `uv.lock` file

**Exit Codes**:
- `0`: Success - environment set up successfully
- `1`: UV not found - UV package manager not installed
- `2`: Wrong Python version - Python 3.12 or other unsupported version detected
- `3`: Dependency resolution failed - UV could not resolve dependencies

**Idempotency**: Safe to run multiple times. UV sync is idempotent - only installs missing packages.

**Error Messages**: See [prerequisite-errors.md](./prerequisite-errors.md)

**Usage**:
```bash
make dev-setup
```

**Validation**:
After successful execution, verify installation:
```bash
source .venv/bin/activate
python -c "import duckdb; import sqlmesh; print('All packages installed')"
```

**Performance**: Expected time < 5 minutes on first run, < 30 seconds on subsequent runs

---

## Target: raw-data-copy

**Purpose**: Extract Synthea CSV raw data from Docker image to local filesystem for development

**Prerequisites**:
- Docker installed
- Docker daemon running
- Network access to ghcr.io

**Inputs**:
- Docker image: `ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data`

**Outputs**:
- `data/raw/` directory populated with Synthea CSV files

**Side Effects**:
- Creates `data/raw/` directory if it doesn't exist
- Replaces existing files in `data/raw/` (intentional refresh)
- Pulls Docker image if not already cached locally

**Exit Codes**:
- `0`: Success - data copied successfully
- `1`: Docker not found - Docker not installed
- `2`: Docker not running - Docker daemon not started
- `3`: Image not found or copy failed - Network issue or image unavailable

**Idempotency**: Safe to run multiple times. Overwrites existing data with fresh copies from Docker image.

**Error Messages**: See [prerequisite-errors.md](./prerequisite-errors.md)

**Usage**:
```bash
make raw-data-copy
```

**Validation**:
After successful execution:
```bash
ls data/raw/*.csv
# Should see Synthea CSV files: patients.csv, observations.csv, etc.
```

**Performance**: Expected time < 2 minutes (depends on network speed and whether image is cached)

---

## Target: superset-init

**Purpose**: Initialize Apache Superset database and create admin user (one-time setup)

**Prerequisites**:
- Development environment set up (`make dev-setup` completed successfully)
- Superset installed in virtual environment

**Inputs**:
- User input during execution (admin username, password, email)

**Outputs**:
- Superset metadata database (SQLite file)
- Admin user account created

**Side Effects**:
- Creates Superset database file (`.superset/superset.db` or configured location)
- Initializes Superset schema and tables
- Creates admin user account (interactive prompts)

**Exit Codes**:
- `0`: Success - Superset initialized
- `1`: Development environment not set up
- `2`: Database already exists (warning, not error)
- `3`: Initialization failed

**Idempotency**: ⚠️ **NOT idempotent**. Should only be run once. Running again may prompt to overwrite existing database.

**Interactive Prompts**:
- Username
- First name
- Last name
- Email
- Password
- Password confirmation

**Usage**:
```bash
make superset-init
```

**Example Output**:
```
Initializing Superset database...
Running database migrations...
✅ Database initialized

Creating Superset admin user...
Username [admin]: myuser
User first name [admin]: John
User last name [user]: Doe
Email [admin@fab.org]: john.doe@example.com
Password: ********
Repeat for confirmation: ********
✅ Admin user created

Running Superset initialization...
✅ Superset initialized! Run 'make superset-run' to start the server.
```

---

## Target: superset-run

**Purpose**: Start Apache Superset web server on localhost:8088

**Prerequisites**:
- Superset initialized (`make superset-init` completed)

**Inputs**: None

**Outputs**:
- Superset web UI accessible at http://localhost:8088
- Server logs to stdout

**Side Effects**:
- Binds to port 8088 (blocks until server stopped)
- Creates log files (if configured)

**Exit Codes**:
- `0`: Success (on clean shutdown)
- `1`: Superset not initialized
- `2`: Port 8088 already in use
- `3`: Server startup failed

**Idempotency**: Safe to run multiple times (will fail if port already in use)

**Usage**:
```bash
make superset-run
```

**Expected Output**:
```
Starting Superset on http://localhost:8088
 * Serving Flask app 'superset'
 * Debug mode: on
 * Running on http://0.0.0.0:8088
Press CTRL+C to quit
```

**Access**: Open browser to http://localhost:8088

**Shutdown**: Press `Ctrl+C` to stop server

---

## Target: test

**Purpose**: Run test suite using pytest

**Prerequisites**:
- Development environment set up (`make dev-setup` completed)

**Inputs**:
- Test files in `tests/` directory

**Outputs**:
- Test results to stdout
- Coverage report (if configured)

**Side Effects**:
- May create `.coverage` file (coverage data)
- May create `__pycache__` directories

**Exit Codes**:
- `0`: All tests passed
- `1`: One or more tests failed

**Idempotency**: Safe to run multiple times

**Usage**:
```bash
make test
```

**Expected Output**:
```
Running tests...
============================= test session starts ==============================
collected 15 items

tests/test_makefile_targets.py ........                                  [ 53%]
tests/test_prerequisites.py .......                                      [100%]

============================== 15 passed in 2.50s ===============================
```

---

## Target: clean

**Purpose**: Remove generated files and virtual environment (reset to clean state)

**Prerequisites**: None

**Inputs**: None

**Outputs**: None

**Side Effects**:
- Deletes `.venv/` directory (virtual environment)
- Deletes `data/raw/` directory (local data)
- Deletes `__pycache__/` directories (Python cache)
- Deletes `*.pyc` files (compiled Python)

**Exit Codes**:
- `0`: Success (always succeeds, even if files don't exist)

**Idempotency**: Safe to run multiple times

**Usage**:
```bash
make clean
```

**Expected Output**:
```
Cleaning up...
Removed .venv
Removed data/raw
✅ Clean complete!
```

**Use Cases**:
- Troubleshooting dependency issues (clean slate)
- Freeing disk space
- Testing fresh installation flow

---

## Target Dependency Graph

```
help (no dependencies)

dev-setup (no dependencies, checks prerequisites internally)

raw-data-copy (no dependencies, checks Docker internally)

superset-init (requires dev-setup to be run first, but not enforced via Make dependencies)

superset-run (requires superset-init to be run first, but not enforced via Make dependencies)

test (requires dev-setup to be run first, but not enforced via Make dependencies)

clean (no dependencies)
```

**Note**: Targets do not declare Make dependencies (`target: dependency`) because:
1. Prerequisite checks are handled within each target
2. Allows independent execution and better error messages
3. Users control execution order based on their needs

---

## Naming Conventions

All targets follow these conventions:

1. **Lowercase with hyphens**: `dev-setup`, `raw-data-copy` (not underscores or camelCase)
2. **Verb-noun format**: Action + object (e.g., `copy-data`, `init-superset`)
3. **Descriptive names**: Clear purpose without looking at implementation
4. **Phony targets**: All targets are `.PHONY` (not file-based)

---

## Error Handling Contract

All targets must:

1. **Check prerequisites** before execution
2. **Provide actionable error messages** with:
   - Clear problem description
   - Installation/fix instructions
   - Links to documentation
3. **Use consistent exit codes**:
   - `0`: Success
   - `1`: Missing prerequisite
   - `2`: Wrong version/configuration
   - `3`: Operation failed
4. **Fail fast**: Stop on first error, don't continue
5. **Print progress**: Inform user of current step

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-12 | Initial contract definition |

