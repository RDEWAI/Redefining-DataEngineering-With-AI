# Implementation Plan: UV Package Manager Migration and Makefile Development Workflow

**Branch**: `001-uv-makefile-migration` | **Date**: 2025-11-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-uv-makefile-migration/spec.md`

**User Requirements**: Makefile generation and README.md updates are critical deliverables for this feature.

## Summary

Migrate the project from traditional pip-based requirements.txt to UV package manager, create a comprehensive Makefile with development workflow automation, and transition from Docker-based development to a local-first development model. The feature includes environment setup automation (dev-setup target), raw data extraction from Docker (raw-data-copy target), integration of modern data stack tools (DuckDB, SQLMesh, Apache Superset), and comprehensive documentation updates including README.md and constitution.md to reflect the new local development paradigm.

## Technical Context

**Language/Version**: Python 3.10-3.12 (aligned with Apache Superset 4.1.1 compatibility)
**Primary Dependencies**: UV package manager, DuckDB, SQLMesh, Apache Superset 4.1.1, pytest 8.3.4
**Storage**: DuckDB (local columnar database), local filesystem for raw CSV data (Synthea synthetic healthcare data)
**Testing**: pytest (local execution, NOT Docker-based)
**Target Platform**: Local development environments (Linux, macOS, Windows WSL)
**Project Type**: Data engineering pipeline - single project with infrastructure tooling focus
**Performance Goals**:
- Environment setup < 5 minutes
- Raw data copy < 2 minutes
- Dependency resolution without conflicts
**Constraints**:
- Must support Python 3.10, 3.11, and 3.12 (no other versions)
- Superset web UI must be accessible at localhost:8088
- All tests run locally (NOT in Docker containers)
- UV-based dependency management (no pip/pip-tools)
**Scale/Scope**:
- Single repository migration
- 3 major package integrations (DuckDB, SQLMesh, Superset)
- 2 primary Makefile targets (dev-setup, raw-data-copy)
- Documentation updates (README.md, constitution.md)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Code Quality & Maintainability
**Status**: ⚠️ PARTIAL COMPLIANCE - Justification Required

**Assessment**:
- ✅ Makefile will follow standard GNU Make conventions
- ✅ Python version constraints enforced (3.10-3.12)
- ⚠️ **VIOLATION**: No source code to lint initially (infrastructure-only feature)
- ✅ Documentation requirements met (README.md, constitution.md, quickstart.md)

**Justification**: This is an infrastructure migration feature with no application source code. The Makefile and setup scripts will follow best practices, but traditional Python linting (pylint, flake8, mypy) doesn't apply. Shell scripts in Makefile will be validated for syntax and best practices.

### Principle II: Testing Standards
**Status**: ⚠️ CONSTITUTIONAL CONFLICT - Requires Amendment

**Assessment**:
- ❌ **MAJOR VIOLATION**: Constitution requires "All tests MUST be runnable in the Docker development environment" (Principle V, line 47)
- ❌ **MAJOR VIOLATION**: Constitution requires `docker compose exec rdewai-dev pytest` (Principle II, line 48)
- ✅ This feature explicitly moves testing FROM Docker TO local environments
- ✅ Integration tests will verify: Makefile targets, UV dependency resolution, tool accessibility

**Critical Issue**: **The constitution mandates Docker-based testing, but this feature eliminates Docker-based development. This is a fundamental architectural shift that requires constitutional amendment.**

**Resolution Strategy**:
1. **Phase 0**: Create research.md documenting the local-first vs Docker-first tradeoffs
2. **Phase 1**: Update constitution.md (FR-015) to reflect local-first development model
3. **Testing Approach**:
   - Integration tests validate Makefile targets execute successfully
   - Validation script tests prerequisite checks (UV, Python version, Docker availability)
   - Test that DuckDB, SQLMesh, Superset are importable and functional
   - Test raw data extraction from Docker image

### Principle III: User Experience Consistency
**Status**: ✅ COMPLIANT

**Assessment**:
- ✅ Makefile provides standard interface (`make dev-setup`, `make raw-data-copy`)
- ✅ Prerequisite checks display helpful error messages with installation instructions
- ✅ Comprehensive documentation (quickstart.md, README.md updates)
- ✅ Error messages are actionable (FR-017, FR-018, FR-019)

### Principle IV: Performance & Scalability
**Status**: ✅ COMPLIANT

**Assessment**:
- ✅ Environment setup target: < 5 minutes (SC-001)
- ✅ Raw data copy target: < 2 minutes (SC-002)
- ✅ Success criteria explicitly defined and measurable

### Principle V: Reproducibility & Environment Consistency
**Status**: ❌ FUNDAMENTAL VIOLATION - Requires Constitutional Amendment

**Assessment**:
- ❌ **CRITICAL VIOLATION**: Constitution mandates "Docker First: All development MUST occur in the standardized Docker environment" (line 89)
- ❌ **CRITICAL VIOLATION**: "No code may rely on 'works on my machine' - if it doesn't work in Docker, it's broken" (line 95)
- ✅ **FEATURE INTENT**: Explicitly moves to local development with UV-managed virtual environments
- ✅ Reproducibility maintained via: UV lock files, exact Python version constraints, pyproject.toml

**Constitutional Amendment Required**:
- Remove Docker-first mandate
- Update to "local-first with containerized data extraction"
- Modify reproducibility principle to emphasize UV lock files and version pinning
- This amendment MUST be completed as part of FR-015

### Quality Gates
**Status**: ⚠️ PARTIAL COMPLIANCE

**Applicable Gates**:
1. ❌ **Linting & Type Checking**: N/A (no application source code, only infrastructure)
2. ✅ **Unit Test Suite**: Validation scripts for prerequisite checks
3. ✅ **Integration Test Suite**: Makefile target execution tests
4. ❌ **Docker Build**: REMOVING Docker as development requirement
5. ✅ **Environment Validation**: NEW validation approach (UV-based, not Docker-based)
6. ✅ **Documentation Updates**: README.md, constitution.md, quickstart.md

**Gate Modifications Required**:
- Remove Docker build gate
- Add UV dependency resolution gate
- Add Makefile syntax validation gate
- Add Python version compatibility gate (3.10-3.12)

### Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Docker-first development (Principle V) | Superset and DuckDB work better in native environments; Docker adds complexity for local development; faster iteration cycles | Docker-only development creates friction for data engineers, slower dev cycles, harder debugging, resource overhead |
| Docker-based testing (Principle II) | Tests need to run in the same environment where development occurs (local); testing Docker setup when not using Docker for development is counterproductive | Maintaining parallel Docker and local environments doubles maintenance burden and creates environment drift |
| Constitution amendment during feature (Principle Governance) | The constitution currently mandates Docker-first, making this feature non-compliant by definition; must update constitution to reflect new architecture | Deferring constitution update would leave project in inconsistent state where feature and constitution conflict |

## Project Structure

### Documentation (this feature)

```text
specs/001-uv-makefile-migration/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output (UV best practices, Superset setup, constitution amendments)
├── data-model.md        # Phase 1 output (configuration entities: pyproject.toml, Makefile targets)
├── quickstart.md        # Phase 1 output (developer onboarding guide)
├── contracts/           # Phase 1 output (Makefile interface spec, UV commands)
│   ├── makefile-api.md  # Documented Makefile targets and usage
│   └── uv-commands.md   # UV command reference for this project
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Root-level configuration and tooling (this feature adds/modifies these files)
.
├── Makefile                    # NEW: Development workflow automation
├── pyproject.toml              # NEW: UV project configuration, dependencies
├── uv.lock                     # NEW: UV lock file for reproducibility (COMMIT TO GIT)
├── README.md                   # MODIFIED: Add UV setup instructions, Makefile usage
├── requirements.txt            # DEPRECATED: Will be removed after migration
├── .gitignore                  # MODIFIED: Add data/raw/, Superset files, uncomment uv.lock
├── .specify/
│   └── memory/
│       └── constitution.md     # MODIFIED: Update to local-first development model
│
├── data/
│   └── raw/                    # NEW: Local directory for Synthea CSV data (GITIGNORED)
│
├── scripts/
│   └── validate-environment.sh # NEW: Prerequisite validation script
│
├── tests/                      # Tests run locally (not in Docker)
│   ├── integration/            # Makefile target tests, tool accessibility tests
│   └── unit/                   # Prerequisite check validation
│
# Existing Docker files (retained only for data extraction)
├── Dockerfile                  # RETAINED: For raw-data Docker image only
├── docker-compose.yml          # RETAINED: For raw-data Docker image only
└── DOCKER.md                   # MODIFIED: Clarify Docker used only for data extraction
```

**Structure Decision**: Root-level tooling structure selected because this is an infrastructure migration feature, not application code. The project currently has no `src/` directory, focusing on data engineering workflows and tooling. Makefile, pyproject.toml, and validation scripts belong at the repository root for standard developer workflows. Docker files are retained but repurposed for data extraction only, not development environment.

## Phase 0: Research & Decisions

**Output**: `research.md`

### Research Tasks

1. **UV Package Manager Best Practices**
   - How to structure pyproject.toml for data engineering project
   - UV dependency groups (dev, prod, optional) for DuckDB/SQLMesh/Superset
   - UV lock file usage and maintenance
   - UV virtual environment creation and management
   - Migration path from requirements.txt to UV

2. **Apache Superset Configuration**
   - Superset 4.1.1 local development setup
   - Database driver requirements (SQLite, DuckDB, PostgreSQL)
   - Minimal configuration for localhost:8088 access
   - Superset initialization sequence (database init, admin user, etc.)
   - Dependencies conflicts and resolution strategies

3. **Makefile Patterns for Data Engineering**
   - GNU Make best practices for Python projects
   - Prerequisite checking in Makefile targets
   - Virtual environment management in Make
   - Error handling and helpful error messages in Makefiles
   - Idempotent Makefile targets (can run multiple times safely)

4. **Python Version Compatibility**
   - Python 3.10, 3.11, 3.12 feature differences relevant to this project
   - UV support across Python versions
   - Superset/DuckDB/SQLMesh compatibility matrix
   - Version detection in Makefile/shell scripts

5. **Constitution Amendment Strategy**
   - Document Docker-first → local-first transition rationale
   - Updated reproducibility guarantees (UV lock files vs Docker images)
   - Testing strategy updates (local pytest vs Docker-based)
   - Quality gate modifications
   - Migration guidance for existing team members

### Decision Points to Resolve

- **pyproject.toml structure**: Which metadata fields are required? How to organize dependencies (main, dev, optional)?
- **Makefile target dependencies**: Should `dev-setup` automatically check prerequisites, or should there be a separate `check-prerequisites` target?
- **Superset initialization**: Should Superset DB initialization be part of `dev-setup`, or a separate target (`superset-init`)?
- **Error message format**: What's the best format for prerequisite error messages? (e.g., "ERROR: UV not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
- **Virtual environment location**: Use UV default (`.venv`) or custom location?
- **Constitution versioning**: Increment to 2.0.0 (breaking change) or 1.1.0 (new guidance)?

## Phase 1: Design & Contracts

**Prerequisites**: `research.md` complete with all decisions documented

**Outputs**: `data-model.md`, `contracts/`, `quickstart.md`, updated agent context

### Data Model

**File**: `data-model.md`

**Entities**:

1. **Project Configuration (pyproject.toml)**
   - Fields: project name, version, Python version constraints, dependencies, optional dependencies
   - Relationships: References UV lock file, consumed by Makefile
   - Validation: Must satisfy Python 3.10-3.12 constraint, must include DuckDB/SQLMesh/Superset

2. **Makefile Target**
   - Fields: target name, dependencies (other targets), commands, help text
   - Relationships: May depend on other targets, uses Project Configuration
   - Validation: Must follow naming convention (hyphenated), must include error handling
   - State: ready (prerequisites met), blocked (prerequisites missing), running, completed, failed

3. **Virtual Environment**
   - Fields: Python version, location (.venv), installed packages, UV metadata
   - Relationships: Created by dev-setup target, managed by UV, contains Dependency Stack
   - Lifecycle: creation → population → validation → usage
   - Validation: Must match Python version constraint, must contain all required packages

4. **Dependency Stack**
   - Fields: package name, version, dependencies (transitive)
   - Relationships: Defined in pyproject.toml, resolved by UV, installed in Virtual Environment
   - Validation: No version conflicts, satisfies Python version constraints

5. **Raw Data Collection**
   - Fields: source (Docker image), destination (data/raw/), file list
   - Relationships: Extracted by raw-data-copy target, requires Docker daemon
   - Validation: All expected CSV files present, correct permissions

6. **Prerequisite Check**
   - Fields: prerequisite name (UV, Docker, Python), check command, error message
   - Relationships: Executed before relevant Makefile targets
   - State: present, missing, wrong_version
   - Validation: Actionable error messages, installation instructions included

### Contracts

**Directory**: `contracts/`

**Files**:

1. **`makefile-api.md`**: Makefile Target Interface Specification
   ```markdown
   # Makefile API Contract

   ## Target: dev-setup
   **Purpose**: Set up local development environment with all dependencies
   **Prerequisites**: UV installed, Python 3.10-3.12 available
   **Inputs**: None
   **Outputs**: .venv directory with all packages installed
   **Side Effects**: Creates/updates virtual environment
   **Exit Codes**: 0 (success), 1 (UV missing), 2 (wrong Python version), 3 (dependency resolution failed)
   **Idempotency**: Safe to run multiple times
   **Error Messages**: See prerequisite-errors.md

   ## Target: raw-data-copy
   **Purpose**: Extract Synthea CSV data from Docker image to local filesystem
   **Prerequisites**: Docker installed and running
   **Inputs**: ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data image
   **Outputs**: data/raw/*.csv files
   **Side Effects**: Creates data/raw directory, replaces existing files
   **Exit Codes**: 0 (success), 1 (Docker missing), 2 (Docker not running), 3 (image not found)
   **Idempotency**: Safe to run multiple times (overwrites existing data)
   **Error Messages**: See prerequisite-errors.md

   ## Target: help (default)
   **Purpose**: Display available Makefile targets and usage
   **Prerequisites**: None
   **Inputs**: None
   **Outputs**: Help text to stdout
   **Exit Codes**: 0

   ## Target: clean
   **Purpose**: Remove generated files (.venv, data/raw, __pycache__)
   **Prerequisites**: None
   **Inputs**: None
   **Outputs**: None
   **Side Effects**: Deletes .venv, data/raw
   **Exit Codes**: 0
   **Idempotency**: Safe to run multiple times
   ```

2. **`uv-commands.md`**: UV Command Reference
   ```markdown
   # UV Commands for This Project

   ## Initialize Project
   `uv init` - Create pyproject.toml (done during migration)

   ## Install Dependencies
   `uv sync` - Install all dependencies from pyproject.toml and update lock file

   ## Add New Dependency
   `uv add <package>` - Add to main dependencies
   `uv add --dev <package>` - Add to dev dependencies
   `uv add --optional <package>` - Add to optional dependencies

   ## Update Dependencies
   `uv lock` - Update lock file without installing
   `uv sync --upgrade` - Upgrade all packages to latest compatible versions

   ## Run Commands in Virtual Environment
   `uv run <command>` - Execute command in virtual environment
   `uv run pytest` - Run tests in virtual environment

   ## Python Version Management
   `uv python install 3.10` - Install specific Python version
   `uv python pin 3.10` - Pin project to Python 3.10
   ```

3. **`prerequisite-errors.md`**: Error Message Templates
   ```markdown
   # Prerequisite Error Messages

   ## UV Not Found
   ```
   ERROR: UV package manager not found.

   UV is required to manage Python dependencies for this project.

   Install UV:
     curl -LsSf https://astral.sh/uv/install.sh | sh

   After installation, restart your shell and run 'make dev-setup' again.

   For more information: https://docs.astral.sh/uv/
   ```

   ## Python Version Unsupported
   ```
   ERROR: Unsupported Python version detected.

   Current version: <detected_version>
   Required: Python 3.10, 3.11, or 3.12

   This project requires Python 3.10-3.12 due to Apache Superset compatibility.

   Install compatible Python version:
     uv python install 3.12

   Or visit https://www.python.org/downloads/
   ```

   ## Docker Not Found
   ```
   ERROR: Docker not found.

   Docker is required to extract raw Synthea data from the container image.

   Install Docker:
     macOS: https://docs.docker.com/desktop/install/mac-install/
     Linux: https://docs.docker.com/engine/install/
     Windows: https://docs.docker.com/desktop/install/windows-install/

   After installation, start Docker and run 'make raw-data-copy' again.
   ```

   ## Docker Not Running
   ```
   ERROR: Docker daemon is not running.

   Start Docker:
     macOS/Windows: Open Docker Desktop
     Linux: sudo systemctl start docker

   Then run 'make raw-data-copy' again.
   ```
   ```

### Quickstart Guide

**File**: `quickstart.md`

```markdown
# Quickstart: Local Development Setup

This guide helps you set up your local development environment for the Redefining Data Engineering with AI project.

## Prerequisites

Before you begin, ensure you have:

1. **Python 3.10, 3.11, or 3.12** installed
   - Check: `python3 --version`
   - Install: See [python.org](https://www.python.org/downloads/)

2. **UV package manager** installed
   - Check: `uv --version`
   - Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`

3. **Docker** (only needed for raw data extraction)
   - Check: `docker --version`
   - Install: [Docker installation guide](https://docs.docker.com/get-docker/)

## Quick Setup (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/RDEWAI/Redefining-DataEngineering-With-AI.git
cd Redefining-DataEngineering-With-AI
```

### 2. Set Up Development Environment

```bash
make dev-setup
```

This command:
- Checks for UV and Python version compatibility
- Creates a virtual environment (`.venv`)
- Installs all dependencies (DuckDB, SQLMesh, Superset, etc.)
- Validates the installation

**Expected time**: 3-5 minutes

### 3. Extract Raw Data (Optional)

If you need access to Synthea CSV data:

```bash
make raw-data-copy
```

This command:
- Checks for Docker availability
- Pulls the raw-data Docker image
- Copies CSV files to `data/raw/`

**Expected time**: 1-2 minutes

## Verify Installation

### Check Installed Tools

```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or .venv\Scripts\activate  # Windows

# Verify DuckDB
python -c "import duckdb; print(f'DuckDB {duckdb.__version__}')"

# Verify SQLMesh
python -c "import sqlmesh; print(f'SQLMesh {sqlmesh.__version__}')"

# Verify Superset
superset version
```

### Start Superset (Optional)

```bash
# Initialize Superset database
superset db upgrade
superset fab create-admin

# Start Superset web server
superset run -h 0.0.0.0 -p 8088 --with-threads --reload --debugger
```

Access Superset at: http://localhost:8088

## Common Tasks

### Update Dependencies

```bash
make dev-setup
```

Rerunning `dev-setup` is safe and will update dependencies if needed.

### Clean Environment

```bash
make clean
```

Removes virtual environment and downloaded data. Useful for troubleshooting.

### Run Tests

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run all tests
pytest

# Run specific test file
pytest tests/integration/test_makefile_targets.py
```

## Troubleshooting

### "UV not found" Error

**Solution**: Install UV package manager
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your shell after installation.

### "Unsupported Python version" Error

**Solution**: Install Python 3.10-3.12
```bash
# Using UV to install Python
uv python install 3.12

# Or download from python.org
```

### "Docker not found" or "Docker not running" Error

**Solution**: Install and start Docker
- macOS/Windows: Open Docker Desktop
- Linux: `sudo systemctl start docker`

### Dependency Conflicts

**Solution**: Clean and reinstall
```bash
make clean
make dev-setup
```

## Next Steps

- Read the [constitution.md](.specify/memory/constitution.md) for project standards
- Review [README.md](README.md) for project overview
- Check [DOCKER.md](DOCKER.md) for Docker image details (data extraction only)

## Getting Help

- GitHub Issues: [Report problems](https://github.com/RDEWAI/Redefining-DataEngineering-With-AI/issues)
- Documentation: See `docs/` directory
```

### Agent Context Update

**Action**: Run `.specify/scripts/bash/update-agent-context.sh claude`

**Updates to Add**:
- Technology: UV package manager
- Technology: DuckDB
- Technology: SQLMesh
- Technology: Apache Superset 4.1.1
- Development Model: Local-first with UV virtual environments
- Testing: pytest (local execution)
- Makefile targets: dev-setup, raw-data-copy

## Phase 2: Tasks

**Note**: Tasks will be generated by `/speckit.tasks` command (not created by `/speckit.plan`).

**Expected Task Categories**:

1. **Prerequisite Setup**
   - Create Makefile with help target
   - Create prerequisite validation script
   - Add error message templates

2. **UV Migration**
   - Initialize UV project structure
   - Migrate requirements.txt to pyproject.toml
   - Test dependency resolution across Python 3.10-3.12

3. **Makefile Targets**
   - Implement dev-setup target with prerequisite checks
   - Implement raw-data-copy target with Docker checks
   - Implement clean target
   - Add help documentation to Makefile

4. **Tool Integration**
   - Configure Superset for localhost:8088
   - Validate DuckDB installation
   - Validate SQLMesh installation
   - Integration tests for all three tools

5. **Documentation**
   - Update README.md with UV setup instructions
   - Update constitution.md (local-first development model)
   - Create quickstart.md
   - Update DOCKER.md (clarify data-only usage)
   - Update .gitignore (add data/raw/, Superset files, ensure uv.lock is tracked)

6. **Testing & Validation**
   - Create integration tests for Makefile targets
   - Create validation tests for prerequisite checks
   - Test on clean environment (CI-like)
   - Test on all supported Python versions (3.10, 3.11, 3.12)

## Success Criteria Validation

Each success criterion from the spec maps to validation:

- **SC-001** (Setup < 5 min): Benchmark `make dev-setup` on clean environment
- **SC-002** (Data copy < 2 min): Benchmark `make raw-data-copy`
- **SC-003** (Zero regressions): Run existing tests after migration
- **SC-004** (No manual intervention): Automated dependency resolution check
- **SC-005** (First-attempt success): Test with new developer (simulated clean env)
- **SC-006** (Tools functional): Import and basic operation tests for each tool
- **SC-007** (Superset at :8088): HTTP check on localhost:8088 after init
- **SC-008** (No conflicts): UV lock file generation succeeds without errors

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Superset dependency conflicts | High | Medium | Research Superset 4.1.1 exact dependency tree; use UV's resolver; test on fresh env |
| Python version incompatibilities | Medium | Low | Test on all three versions (3.10, 3.11, 3.12); CI matrix |
| Constitution conflicts | High | High | **Already identified**: Amendment to constitution is part of FR-015; must complete |
| Makefile portability (GNU vs BSD) | Medium | Medium | Use POSIX-compatible Make features; test on macOS (BSD) and Linux (GNU) |
| UV adoption curve | Low | Low | Comprehensive quickstart.md; UV is well-documented; error messages guide users |
| Docker image unavailability | Medium | Low | Document image location; consider fallback or manual download instructions |

## .gitignore Updates

**File**: `.gitignore` (repository root)

### Required Changes

**Status**: The current .gitignore already has UV-related entries but needs modifications for this feature.

**Current State Analysis**:
- ✅ `.venv` already ignored (line 141)
- ⚠️ `uv.lock` is commented out (line 102) - **MUST BE UNCOMMENTED**
- ❌ `data/raw/` not ignored - **MUST BE ADDED**
- ❌ Superset-specific files not ignored - **MUST BE ADDED**

### Changes to Implement

1. **Uncomment uv.lock tracking** (line 98-102):
   ```gitignore
   # UV
   #   Similar to Pipfile.lock, it is generally recommended to include uv.lock in version control.
   #   This is especially recommended for binary packages to ensure reproducibility, and is more
   #   commonly ignored for libraries.
   #uv.lock  # REMOVE THIS COMMENT - we want to track uv.lock
   ```

   **Decision**: Track `uv.lock` in version control for reproducibility (per research.md findings)

2. **Add data/raw/ directory** (after line 28 synthea/):
   ```gitignore
   # Data directories
   data/raw/
   data/processed/
   data/temp/
   ```

   **Rationale**: Raw Synthea CSV data is copied from Docker and can be large (~100MB+). Should not be committed.

3. **Add Superset-specific files** (new section after Marimo):
   ```gitignore
   # Apache Superset
   .superset/
   superset.db
   superset_config.py  # May contain secrets
   ```

   **Rationale**: Superset database and config may contain sensitive data (SECRET_KEY, admin credentials)

4. **Add Makefile touchfiles** (if used):
   ```gitignore
   # Makefile touchfiles for dependency tracking
   .venv/.installed
   ```

   **Rationale**: Touchfiles are build artifacts, not source code

### Complete .gitignore Addition

**Location**: Add after line 208 (`__marimo__/`), before logs section

```gitignore
# Apache Superset
# Superset is a BI platform - ignore database, config, and cache directories
.superset/
superset.db
superset.db-shm
superset.db-wal
superset_config.py  # May contain SECRET_KEY and other sensitive config

# Project-specific data directories
# Raw data copied from Docker image (can be regenerated with make raw-data-copy)
data/raw/
data/processed/
data/temp/
*.csv  # Large CSV files should not be committed
*.parquet  # Large Parquet files should not be committed

# Makefile build artifacts
.venv/.installed  # Touchfile for dependency tracking
```

### UV Lock File Handling

**Current .gitignore (lines 98-102)**:
```gitignore
# UV
#   Similar to Pipfile.lock, it is generally recommended to include uv.lock in version control.
#   This is especially recommended for binary packages to ensure reproducibility, and is more
#   commonly ignored for libraries.
#uv.lock
```

**Required Change**: Uncomment `#uv.lock` to ensure lock file is tracked

**Rationale**:
- This project is an application/pipeline (not a library)
- Lock file ensures reproducibility across environments
- UV documentation recommends tracking lock files for applications
- Research.md Section 1.3 confirms this best practice

### Validation

After updating .gitignore, verify:

```bash
# Ensure uv.lock is NOT ignored
git check-ignore uv.lock
# Should return nothing (file is tracked)

# Ensure data/raw is ignored
mkdir -p data/raw
touch data/raw/test.csv
git check-ignore data/raw/test.csv
# Should return: data/raw/test.csv (file is ignored)

# Ensure .superset is ignored
mkdir -p .superset
git check-ignore .superset/superset.db
# Should return: .superset/superset.db (file is ignored)
```

### Migration Notes

**For Existing Developers**:
- After pulling .gitignore changes, run `git status` to see newly-ignored files
- Files already tracked will remain tracked (git doesn't auto-remove them)
- Use `git rm --cached data/raw/*` if raw data was previously committed

## Notes

**Critical Constitutional Issue**: This feature fundamentally conflicts with Principles II (Docker-based testing) and V (Docker-first development). The constitution amendment (FR-015) is **not optional** - it must be completed as part of this feature or the project will be in an inconsistent state. The amendment justification is documented in the Complexity Tracking section above.

**User Requirement Emphasis**: Makefile generation, README.md updates, and .gitignore modifications are explicitly required deliverables per user input.
