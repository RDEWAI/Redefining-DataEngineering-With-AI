# Feature Specification: UV Package Manager Migration and Makefile Development Workflow

**Feature Branch**: `001-uv-makefile-migration`
**Created**: 2025-11-12
**Status**: Draft
**Input**: User description: "Migrate to UV package manager and create Makefile for development workflow"

## Clarifications

### Session 2025-11-12

- Q: What should be the range of Python versions supported? → A: Python 3.10-3.12
- Q: Superset local access configuration? → A: Web UI on localhost:8088
- Q: Error handling for missing prerequisites? → A: Check and display helpful error message
- Q: Makefile target naming convention? → A: Hyphen: dev-setup, raw-data-copy
- Q: Constitution.md content scope? → A: SpecKit + conventions + local development workflow

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initial Development Environment Setup (Priority: P1)

As a new developer joining the project, I need to set up my local development environment quickly and reliably so I can start contributing to the project without complex manual configuration steps.

**Why this priority**: This is the first interaction every developer has with the project. A smooth setup experience directly impacts developer productivity and onboarding time. Without this working, no development can occur.

**Independent Test**: Can be fully tested by cloning the repository on a fresh machine, running a single setup command, and verifying that the development environment is ready with all dependencies installed and accessible.

**Acceptance Scenarios**:

1. **Given** a fresh clone of the repository, **When** developer runs the setup command, **Then** a virtual environment is created, all dependencies are installed, and the environment is ready for development
2. **Given** an existing virtual environment, **When** developer runs the setup command again, **Then** the system detects the existing environment and updates dependencies without creating duplicates
3. **Given** a corrupted or incomplete virtual environment, **When** developer runs the setup command, **Then** the system recreates the environment from scratch

---

### User Story 2 - Raw Data Access for Development (Priority: P2)

As a data engineer working on the project, I need to access Synthea CSV raw data on my local filesystem so I can develop and test data pipelines without requiring constant Docker container access.

**Why this priority**: Essential for development workflows involving data transformation, but not required for initial environment setup. Developers working on non-data components may not need this immediately.

**Independent Test**: Can be fully tested by running the data copy command and verifying that Synthea CSV files appear in the local data/raw directory with correct permissions and complete content.

**Acceptance Scenarios**:

1. **Given** Docker is running and the raw-data image is available, **When** developer runs the raw data copy command, **Then** all Synthea CSV files are copied to the local data/raw directory
2. **Given** the local data/raw directory already contains files, **When** developer runs the raw data copy command, **Then** existing files are replaced with fresh copies from the Docker image
3. **Given** the data/raw directory does not exist, **When** developer runs the raw data copy command, **Then** the directory is created before copying files

---

### User Story 3 - Working with Modern Data Stack Tools (Priority: P3)

As a data engineer, I need access to DuckDB, SQLMesh, and Apache Superset in my development environment so I can build data transformations, manage data models, and visualize results.

**Why this priority**: Required for data-specific development tasks but not critical for general project setup. Most valuable after the basic environment is established and data is available locally.

**Independent Test**: Can be fully tested by importing each package in Python, executing basic operations (DuckDB query, SQLMesh model definition, Superset configuration check), and verifying that all dependencies resolve without conflicts.

**Acceptance Scenarios**:

1. **Given** the development environment is set up, **When** developer imports and uses DuckDB, **Then** queries execute successfully against local or in-memory databases
2. **Given** the development environment is set up, **When** developer initializes SQLMesh, **Then** data transformation models can be defined and executed
3. **Given** the development environment is set up, **When** developer accesses Superset, **Then** the BI platform is accessible for data visualization and dashboard creation
4. **Given** all three packages are installed, **When** developer runs dependency resolution, **Then** no conflicts exist between package requirements

---

### Edge Cases

- When the developer's system does not have UV installed, the setup command checks for UV and displays a helpful error message with installation instructions
- When the developer's system does not have Docker installed or running, the raw data copy command checks Docker availability and displays installation/startup instructions
- How does the system handle network failures during dependency installation?
- How does the system behave if the raw-data Docker image is not available or has been updated?
- What happens when dependency versions conflict between packages (especially with Superset's extensive dependencies)?
- How does the system handle insufficient disk space during environment creation or data copying?
- What happens when a developer switches between different Python versions?
- When a developer has an unsupported Python version (not 3.10-3.12), the setup command detects this and displays a clear error message indicating the required version range

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a single command that sets up the complete development environment including virtual environment creation and dependency installation
- **FR-002**: System MUST use UV package manager for all dependency management operations
- **FR-003**: System MUST detect and reuse existing virtual environments to avoid unnecessary recreation
- **FR-004**: System MUST provide a single command that copies Synthea CSV raw data from the Docker image to the local filesystem at data/raw
- **FR-005**: System MUST create necessary local directories if they do not exist before copying data
- **FR-006**: System MUST include DuckDB and its required dependencies in the project dependencies
- **FR-007**: System MUST include SQLMesh and its required dependencies in the project dependencies
- **FR-008**: System MUST include Apache Superset and all its required dependencies (database drivers, caching libraries, authentication libraries) in the project dependencies
- **FR-009**: System MUST configure Superset web UI to be accessible at localhost:8088 for local development
- **FR-010**: System MUST migrate all existing dependencies from requirements.txt to UV's pyproject.toml format
- **FR-011**: System MUST initialize proper UV project structure with pyproject.toml configuration
- **FR-012**: System MUST ensure all dependencies resolve correctly without version conflicts
- **FR-016**: System MUST support Python versions 3.10, 3.11, and 3.12
- **FR-017**: Setup command MUST check for UV installation and display helpful error message with installation instructions if missing
- **FR-018**: Setup command MUST check for supported Python version (3.10-3.12) and display clear error message if unsupported version detected
- **FR-019**: Raw data copy command MUST check for Docker installation and running daemon, displaying helpful error message with instructions if missing or not running
- **FR-013**: System MUST document UV as a prerequisite in project documentation
- **FR-014**: System MUST document the development workflow commands in project documentation
- **FR-015**: System MUST update constitution.md with SpecKit workflow information, project conventions, and local-first development model (replacing Docker-based development assumptions with local virtual environment, local data, and local test execution)

### Key Entities *(include if feature involves data)*

- **Virtual Environment**: Python isolated environment containing all project dependencies, managed by UV
- **Project Configuration**: pyproject.toml file defining project metadata, dependencies, and UV-specific settings
- **Makefile Targets**: Named commands (dev-setup, raw-data-copy) that automate development workflow tasks
- **Raw Data**: Synthea CSV files representing synthetic healthcare data used for development and testing
- **Dependency Stack**: Collection of Python packages including DuckDB (database), SQLMesh (transformation framework), and Superset (BI platform)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New developers can set up a complete development environment in under 5 minutes with a single command
- **SC-002**: Raw data copying completes in under 2 minutes for the complete dataset
- **SC-003**: All existing project functionality remains operational after migration with zero regression issues
- **SC-004**: Dependency installation completes successfully without manual intervention or conflict resolution
- **SC-005**: Documentation enables a developer unfamiliar with the new package manager to complete setup on their first attempt
- **SC-006**: All three data stack tools (database, transformation framework, BI platform) are accessible and functional after environment setup
- **SC-007**: BI visualization platform is accessible through localhost:8088 for dashboard creation
- **SC-008**: Package manager successfully resolves all dependencies without conflicts

## Assumptions *(optional)*

- Developers have Python 3.10, 3.11, or 3.12 installed on their systems
- Developers have Docker installed and running for the raw data copy functionality
- The raw-data Docker image (ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data) is publicly accessible
- Developers have sufficient disk space for virtual environment creation (approximately 1-2GB) and raw data (size varies)
- Network connectivity is available for downloading dependencies from package repositories
- The current requirements.txt contains compatible dependency versions that can be migrated to UV format
- Superset will be configured for local development mode (not production deployment)
- Developers are working on Linux, macOS, or Windows with WSL (standard Unix-like environments)

## Out of Scope *(optional)*

- Production deployment configuration for Superset
- Automated CI/CD pipeline updates (will be addressed separately if needed)
- Migration of existing developer environments (focus is on fresh setup)
- Custom Superset themes or advanced visualization configurations
- Performance optimization of data loading or transformation processes
- Integration testing infrastructure setup
- Database backup and restore procedures
- Multi-environment configuration (dev/staging/production)
- Docker-based development workflows (this migration explicitly moves away from Docker containers for local development, using Docker only for raw data extraction)
