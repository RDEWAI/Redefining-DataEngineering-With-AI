# STORY-01-001: Scaffold patient_360 project from cookiecutter template

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 1 |
| **Dependencies** | None |
| **Status** | To Do |

<!--
  Story Type vocabulary (required):
    - build                    → primary construction work
    - performance-optimization → layer-scoped perf tuning (LLD §6); runs BEFORE integration-test
    - integration-test         → triggers layer DAG on local Airflow against Unity Catalog OSS local; validates landed data in UC local
    - deploy-validation        → layer-scoped DDL/DAG/config deploy smoke (optional; only when LLD prescribes it)
    - observability            → layer-scoped lineage/metrics/dashboard wiring
    - release                  → cross-layer promotion/rollback (trailing epic only)
    - hardening                → cross-layer security/docs/maintenance (trailing epic only)
    - runtime-bootstrap        → JDK/Docker/UC catalog/source-data prerequisites (≥1 per backlog, typically EPIC-01)
-->


## User Story

As a data engineer, I want generate the patient_360 project scaffold from the cookiecutter template so that every downstream story has a known directory layout and Make targets.

## Description

Render the `inputs/lld/v1/templates/cookiecutter-chapter/` cookiecutter template into `patient_360/` with defaults `chapter_name=chapter-5`, `project_name=patient_360`, `python_version=3.12`. The rendered tree must contain `src/patient_360/{bronze,silver,gold,utils}/`, `airflow/dags/`, `airflow/configs/`, `contracts/`, `dq_rules/`, `ddl/liquibase/`, `_infra/{ci,cd,docker}/`, `tests/{bronze,silver,gold}/`, `pyproject.toml`, `Makefile`, and `CLAUDE.md`. `make dev-setup` must succeed and `pytest --collect-only` must report no errors.

## Acceptance Criteria


- [ ] Cookiecutter render produces `patient_360/` directory tree matching LLD §2.1 [LLD §2.1]

- [ ] `patient_360/pyproject.toml` declares hatchling build, ruff, pytest, and uv-managed deps [LLD §2.1]

- [ ] `patient_360/Makefile` exposes `dev-setup`, `lint`, `test`, `clean` targets [LLD §9.3]

- [ ] `make dev-setup` runs `uv sync --all-extras` and exits 0 [LLD §9.3]

- [ ] `pytest --collect-only` discovers `tests/{bronze,silver,gold}/` with no import errors [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §2.1, §9.3
- **Implementation hints**: Use the cookiecutter CLI (`cookiecutter inputs/lld/v1/templates/cookiecutter-chapter/ --no-input`). Verify the developer-plugin baseline in `_infra/docker/docker-compose.yml`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §2.1 Project Structure, §9.3 Promotion Process |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | Cookiecutter render produces expected paths | pytest tests/test_scaffold.py |

| Smoke | make dev-setup completes | make dev-setup |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/pyproject.toml"
  - file_exists: "patient_360/src/patient_360/__init__.py"
AC2:
  - grep: {file: "patient_360/pyproject.toml", pattern: "hatchling"}
AC3:
  - grep: {file: "patient_360/Makefile", pattern: "dev-setup"}
  - grep: {file: "patient_360/Makefile", pattern: "^test:"}
AC4:
  - manual: "requires uv installed on host"
AC5:
  - manual: "requires Python env present"
```


## How to Test (User)

### Prerequisites


- `uv` >= 0.4 installed on host

- Python 3.12 available


### Steps


1. `cd chapter-5 && cookiecutter inputs/lld/v1/templates/cookiecutter-chapter/ --no-input`

2. `cd patient_360 && make dev-setup`

3. `uv run pytest --collect-only`


### Expected outcome


- `patient_360/` directory created with the layout shown in LLD §2.1

- `make dev-setup` exits 0

- `pytest --collect-only` reports tests collected with no errors


## Documentation Updates


- [ ] Update patient_360/README.md § "Getting Started" with the cookiecutter render and `make dev-setup` commands

