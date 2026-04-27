# STORY-01-001: Render cookiecutter scaffold and pyproject/Makefile

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Runtime Bootstrap |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 1 |
| **Dependencies** | — |
| **Status** | To Do |

## User Story

As a Data Engineer, I want the `patient_360/` project scaffold rendered from the cookiecutter template so that all downstream stories have a canonical layout, build, and dev tooling to work against.

## Description

Render `inputs/lld/v1/templates/cookiecutter-chapter/` with defaults `chapter_name=chapter-5`, `project_name=patient_360`, `python_version=3.12` to produce `patient_360/` containing the full directory tree of LLD §2.1 — `src/patient_360/{bronze,silver,gold,utils}/`, `airflow/{dags,configs}/`, `contracts/`, `dq_rules/`, `ddl/liquibase/`, `_infra/{docker,ci,cd}/`, and `tests/{bronze,silver,gold}/`. The rendered `pyproject.toml` (hatchling, `src/patient_360` package, runtime + dev extras) and `Makefile` (`dev-setup`, `lint`, `test`, `clean`) must allow `make dev-setup && uv run pytest --collect-only` to succeed cleanly on a fresh checkout.

## Acceptance Criteria

- [ ] `patient_360/` directory exists at chapter-5 root with full layout per LLD §2.1 [LLD §2.1]
- [ ] `patient_360/pyproject.toml` declares `hatchling` build-backend with `src/patient_360` package [LLD §2.1]
- [ ] `patient_360/Makefile` provides `dev-setup`, `lint`, `test`, `clean` targets [LLD §9.3]
- [ ] `cd patient_360 && make dev-setup` exits 0 [LLD §2.1]
- [ ] `cd patient_360 && uv run pytest --collect-only` exits 0 [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD §2.1 (Project Structure), §9.3 (Make targets)
- **Implementation hints**: Use `cookiecutter inputs/lld/v1/templates/cookiecutter-chapter --no-input chapter_name=chapter-5 project_name=patient_360 python_version=3.12 --output-dir .`. Verify the Module-to-Template mapping table in LLD §2.1.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.1 Project Structure, §9.3 Promotion |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Smoke | Scaffold renders and pytest collects | `cd patient_360 && uv run pytest --collect-only` |
| Unit | `pyproject.toml` parseable | `python -c 'import tomllib; tomllib.load(open("patient_360/pyproject.toml","rb"))'` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/pyproject.toml"
  - file_exists: "patient_360/Makefile"
  - file_exists: "patient_360/src/patient_360/__init__.py"
AC2:
  - grep: {file: "patient_360/pyproject.toml", pattern: 'hatchling'}
AC3:
  - grep: {file: "patient_360/Makefile", pattern: 'dev-setup'}
AC4:
  - manual: "run `cd patient_360 && make dev-setup` and verify exit 0"
AC5:
  - manual: "run `cd patient_360 && uv run pytest --collect-only` and verify exit 0"
```

## How to Test (User)

### Prerequisites

- UV installed (`pip install uv`)
- Cookiecutter installed (`pipx install cookiecutter`)
- Python 3.12 available

### Steps

1. `cookiecutter inputs/lld/v1/templates/cookiecutter-chapter --no-input chapter_name=chapter-5 project_name=patient_360 python_version=3.12 --output-dir .`
2. `cd patient_360 && make dev-setup`
3. `uv run pytest --collect-only`

### Expected outcome

- `patient_360/` exists with src/, airflow/, contracts/, dq_rules/, _infra/ subtrees
- `make dev-setup` exits 0
- `uv run pytest --collect-only` exits 0 with no errors

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Project Layout" with the rendered directory tree
- [ ] Update `patient_360/README.md` § "Quick Start" with `make dev-setup` instructions
