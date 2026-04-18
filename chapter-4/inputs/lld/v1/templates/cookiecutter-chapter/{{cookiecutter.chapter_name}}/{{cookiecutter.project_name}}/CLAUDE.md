# Claude Code Instructions — {{cookiecutter.chapter_name}}

## Project
**{{cookiecutter.project_name}}** — Patient 360 medallion pipeline (Bronze → Silver → Gold)

## Active Technologies
- Python {{cookiecutter.python_version}} with UV package manager
- Apache Airflow (see `airflow/`)
- Liquibase for DDL migrations (see `ddl/liquibase/`)
- Contracts-driven DQ (see `contracts/` + `dq_rules/`)

## Directory Layout
- `inputs/` — approved artifacts from chapter-4 (DRD, HLD, DMS, LLD, etc.)
- `outputs/` — chapter-5 generated outputs
- `developer-plugin/` — AI developer agent plugin (DAG + CI/CD skills)
- `{{cookiecutter.project_name}}/` — main Python project
  - `src/{{cookiecutter.project_name}}/` — importable package (bronze / silver / gold / utils)
  - `tests/` — mirrors src/ structure
  - `airflow/dags/` — Airflow DAG files
  - `airflow/configs/` — DAG configuration YAML files
  - `contracts/` — table contracts (DDL + DQ pointers)
  - `dq_rules/` — DQ rule definitions
  - `ddl/liquibase/` — schema migration changelogs
  - `_infra/` — docker, CI, CD configuration
  - `scripts/` — one-off utility scripts

## Key Commands
```bash
make dev-setup    # Install dependencies via uv
make test         # Run pytest
make lint         # Run ruff
make validate     # Validate contracts and DQ rules
```

## Plugin
Install the developer plugin before starting:
```
/plugin install developer-plugin@{{cookiecutter.chapter_name}}
```

Skills available:
- `/developer-plugin:create-dag` — generate Airflow DAG from LLD
- `/developer-plugin:update-dag` — update existing DAG
- `/developer-plugin:validate-dag` — validate DAG file
- `/developer-plugin:create-pipeline` — generate CI/CD pipeline
- `/developer-plugin:update-pipeline` — update CI/CD pipeline
- `/developer-plugin:validate-pipeline` — validate pipeline config
