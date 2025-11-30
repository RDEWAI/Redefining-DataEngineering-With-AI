<!--
SYNC IMPACT REPORT
==================
Version Change: 1.0.0 → 1.1.0 (Local-First UV Development Model)
Modified Principles:
  - Section V: Reproducibility - Changed from Docker-first to local-first UV development
  - Testing Standards: Updated to use local pytest execution instead of Docker
  - Quality Gates: Replaced Docker build gate with UV resolution gate
Added Sections: N/A
Removed Sections: N/A
Templates Requiring Updates:
  ✅ plan-template.md - Constitution Check section aligns with quality gates
  ✅ spec-template.md - Requirements section aligns with functional requirements principle
  ✅ tasks-template.md - Test tasks align with testing standards principle
Follow-up TODOs: None
-->

# Redefining Data Engineering with AI - Constitution

## Core Principles

### I. Code Quality & Maintainability (NON-NEGOTIABLE)

All code MUST adhere to professional engineering standards that ensure long-term maintainability and reliability.

**Requirements**:
- Python code MUST follow PEP 8 style guidelines with strict linting (pylint, flake8, or ruff)
- Type hints MUST be used for all function signatures and public APIs
- Docstrings MUST follow Google or NumPy style for all public modules, classes, and functions
- Code complexity MUST be monitored - functions exceeding cyclomatic complexity of 10 require refactoring justification
- Code reviews MUST verify readability, documentation, and adherence to project patterns
- No code with linting errors or failing type checks may be merged

**Rationale**: Data engineering pipelines are complex and long-lived. Poor code quality leads to production incidents, debugging nightmares, and technical debt that compounds over time. Enforcing quality standards upfront prevents these issues.

### II. Testing Standards (NON-NEGOTIABLE)

Comprehensive testing ensures data pipelines are reliable, reproducible, and safe to deploy.

**Requirements**:
- **Unit Tests**: MUST cover all business logic, transformations, and utility functions with minimum 80% coverage
- **Integration Tests**: MUST verify interactions between components (PySpark jobs, DuckDB queries, external services)
- **Contract Tests**: MUST validate data schemas and API contracts at pipeline boundaries
- **Data Quality Tests**: MUST include assertions for data integrity (null checks, range validation, referential integrity)
- All tests MUST be runnable in the local UV-managed virtual environment
- Tests MUST be automated via pytest and executable with `uv run pytest` or `make test`
- New features MUST NOT be merged without corresponding tests
- When TDD is requested: tests MUST be written first, verified to fail, then implemented (Red-Green-Refactor)

**Rationale**: Data engineering errors cascade silently through pipelines, corrupting downstream systems. Rigorous testing catches issues early and provides confidence during refactoring and deployments.

### III. User Experience Consistency

Data engineering tools and interfaces MUST be intuitive, consistent, and minimize cognitive load for users (data analysts, scientists, engineers).

**Requirements**:
- **CLI Tools**: MUST follow standard conventions (stdin/stdout, exit codes, --help flags, consistent option naming)
- **Documentation**: MUST include quickstart guides, example usage, and troubleshooting sections
- **Error Messages**: MUST be actionable, include context, and suggest next steps (not cryptic stack traces)
- **Configuration**: MUST use standardized formats (YAML, TOML, or .env) with validation and clear error reporting
- **Notebooks**: MUST be self-documenting with markdown explanations, clear cell outputs, and reproducible execution
- **Logging**: MUST use structured logging (JSON) with consistent levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- All user-facing features MUST be validated against real user workflows before release

**Rationale**: Poor UX in data tools leads to misuse, errors, and frustration. Consistent, well-documented interfaces reduce onboarding time and operational errors.

### IV. Performance & Scalability

Data pipelines MUST be designed for efficiency and scalability from the start.

**Requirements**:
- **Benchmarking**: Performance-critical code MUST include benchmarks and profiling results
- **PySpark Jobs**: MUST be optimized for partition size, shuffle operations, and memory usage
- **DuckDB Queries**: MUST leverage columnar execution and avoid unnecessary data scans
- **Memory Management**: Jobs MUST operate within defined memory limits (document max expected usage)
- **Data Volume Testing**: Pipelines MUST be tested with production-scale data samples
- **Resource Limits**: All containerized jobs MUST define CPU and memory limits
- Performance regressions MUST be identified via automated benchmarking before merge
- Optimizations MUST be justified with profiling data (no premature optimization)

**Rationale**: Data pipelines that work on small datasets often fail catastrophically at scale. Proactive performance design prevents production outages and costly rewrites.

### V. Reproducibility & Environment Consistency

All development, testing, and production environments MUST be reproducible and version-controlled.

**Requirements**:
- **Local-First with UV**: All development MUST use the UV package manager with `pyproject.toml` and `uv.lock` for dependency management
- **Dependency Pinning**: All Python dependencies MUST be locked in `uv.lock` with exact versions resolved by UV
- **Configuration as Code**: Environment settings MUST be codified (no manual setup steps)
- **Data Versioning**: Input data schemas and sample datasets MUST be version-controlled
- **Execution Reproducibility**: Pipeline runs MUST be reproducible given the same code version and input data
- **Environment Setup**: Development environment MUST be reproducible via `make dev-setup` in under 5 minutes
- Changes to dependencies MUST be tested across the full pipeline before merge
- No code may rely on "works on my machine" - if it doesn't work with `uv sync`, it's broken
- **Docker for Data Only**: Docker is used only for data extraction (`make raw-data-copy`), not for development

**Rationale**: Data engineering suffers from environment drift more than most disciplines. UV-based dependency locking with deterministic resolution eliminates "works on my machine" issues and ensures consistent behavior across dev/test/prod while maintaining fast iteration cycles.

## Quality Gates

All code changes MUST pass the following automated gates before merge:

1. **Linting & Type Checking**: `pylint`, `flake8`, `mypy` (zero errors)
2. **Unit Test Suite**: `uv run pytest tests/unit/` (100% pass rate, minimum 80% coverage)
3. **Integration Test Suite**: `uv run pytest tests/integration/` (100% pass rate)
4. **UV Dependency Resolution**: `uv sync` (successful dependency resolution with no conflicts)
5. **Environment Validation**: `make dev-setup` (all prerequisite checks pass)
6. **Documentation Updates**: User-facing changes MUST include updated README/docs

## Performance Standards

### Development Environment

- Container startup: < 60 seconds
- Test suite execution (unit): < 5 minutes
- Test suite execution (integration): < 15 minutes

### Production Pipelines

Performance targets are feature-specific but MUST be explicitly documented in each feature's implementation plan. Common targets:

- **Batch Processing**: Throughput goals (e.g., 1M records/minute)
- **Query Response**: Latency targets (e.g., p95 < 2 seconds)
- **Resource Usage**: Memory and CPU limits per job

## Governance

### Amendment Process

1. Proposed changes MUST be documented with rationale
2. Constitution changes require approval from project maintainers
3. Breaking changes require migration plan for existing code
4. Version number MUST be incremented per semantic versioning:
   - **MAJOR**: Backward-incompatible principle removals or redefinitions
   - **MINOR**: New principles or materially expanded guidance
   - **PATCH**: Clarifications, wording fixes, typo corrections

### Compliance Review

- All pull requests MUST verify compliance with applicable principles
- Non-compliance MUST be explicitly justified in PR description
- Violations requiring complexity justification MUST be documented in implementation plans
- Regular audits SHOULD review codebase adherence and identify technical debt

### Guidance Integration

- Development workflows MUST reference this constitution during planning and review
- Template files (spec, plan, tasks) MUST align with constitutional requirements
- Feature implementations MUST include constitution compliance checklist

**Version**: 1.1.0 | **Ratified**: 2025-11-10 | **Last Amended**: 2025-11-18
