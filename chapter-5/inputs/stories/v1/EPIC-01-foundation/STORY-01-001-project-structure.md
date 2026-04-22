# STORY-01-001: Create Project Directory Structure

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 1 |
| **Dependencies** | None |
| **Status** | To Do |

## User Story

As a data engineer, I want the project directory structure created per the code architecture so that all team members have a consistent layout for module development.

## Description

Generate the project scaffold by running `cookiecutter inputs/lld/v1/templates/cookiecutter-chapter/` with defaults `chapter_name=chapter-5`, `project_name=patient_360`, `python_version=3.12`. This produces the canonical directory tree defined in LLD §2.1: `src/patient_360/{bronze,silver,gold,utils}/`, `airflow/{dags,configs}/`, `contracts/` (with `dq/` sub-dir), `dq_rules/`, `ddl/liquibase/changelogs/`, `_infra/{docker,ci,cd}/`, `tests/{bronze,silver,gold}/`, and the `developer-plugin/` with skills. Each Python directory must contain an `__init__.py`. Create placeholder `pyproject.toml`, `Makefile`, and `CLAUDE.md` from template outputs.

## Acceptance Criteria

- [ ] `src/patient_360/{bronze,silver,gold,utils}/` directories exist with `__init__.py` files [LLD §2.1]
- [ ] `airflow/dags/` and `airflow/configs/` directories exist [LLD §4.1]
- [ ] `contracts/` (with `dq/` sub-dir) and `dq_rules/` directories exist [LLD §2.3]
- [ ] `ddl/liquibase/changelogs/` directory exists for Liquibase XML changelogs [LLD §2.3]
- [ ] `tests/{bronze,silver,gold}/` directories exist (layer-mirrored layout) [LLD §2.4]
- [ ] `_infra/{docker,ci,cd}/` directories exist for infra config [LLD §9.1]
- [ ] `developer-plugin/` with skills scaffolded from template [LLD §1]
- [ ] `pyproject.toml` specifies Python >= 3.12 and correct build/test deps [LLD §2.1]
- [ ] `make dev-setup` runs without error (`uv sync --all-extras`) [LLD §9.3]

## Technical Notes

- **Upstream references**: LLD SS2.1 (Project Structure), LLD SS9.3 (Make targets), LLD SS13 Decision 13 (Cookiecutter)
- **Implementation hints**: Run `cookiecutter inputs/lld/v1/templates/cookiecutter-chapter/` at repo root. Verify rendered paths match the module-to-template mapping table in LLD §2.1. Include `.gitkeep` in empty directories for version control.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.1 (Project Structure), SS9.1 (Scaffold Infra Layout), SS9.3 (Make Targets), SS13 Decision 13 |
| DMS | -- |
| STM | -- |
| DQS | -- |
