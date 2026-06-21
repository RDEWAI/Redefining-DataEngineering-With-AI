# {{cookiecutter.project_name}}

Medallion data pipeline (Bronze → Silver → Gold) generated from the
chapter-5 cookiecutter template by the `developer-plugin` skills.

## Prerequisites

- Python {{cookiecutter.python_version}}
- [uv](https://docs.astral.sh/uv/) (package + env manager)
- JDK 17+ (required by Spark 4.x)
- Docker + Docker Compose (for the local Airflow / Unity Catalog stack)

## Bootstrap

One command brings up Docker, creates the Unity Catalog catalog/schemas, and
runs the project-specific source loader:

```bash
make dev-up
```

This wraps:

1. `docker compose -f _infra/docker/docker-compose.yml up -d` (Airflow + UC OSS + Marquez + Postgres + Grafana)
2. Wait for UC OSS REST API to return `200` on `localhost:8080/api/2.1/unity-catalog`
3. `python scripts/uc_init.py` — creates `unity` catalog + `bronze`/`silver`/`gold` schemas
4. `make seed-source-data` — **project-specific**; you implement this against your source system (DuckDB / Postgres / S3 / etc.). The generated `runtime-bootstrap` story (typically `STORY-01-NNN`) tells you exactly what to populate.

After `make dev-up` completes, see **Verify** below.

## Run

The DAG id, schedule, and trigger semantics are defined by your LLD §4.2 and
materialized by `/developer-plugin:create-dag`. Once the DAG file lands in
`airflow/dags/`, trigger a run with:

```bash
airflow dags trigger <your-dag-id>          # see LLD §4.2 for the id
airflow dags list-runs -d <your-dag-id>     # poll until 'success'
```

The Airflow webserver is at <http://localhost:8081> (the host port maps to
the container's 8080 internally).

## Verify

```bash
# 1. Airflow webserver health
curl -fsS http://localhost:8081/health

# 2. Unity Catalog OSS API + catalogs
curl -fsS http://localhost:8080/api/2.1/unity-catalog/catalogs | jq '.catalogs[].name'

# 3. Bronze tables registered
curl -fsS 'http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze' | jq '.tables | length'

# 4. Marquez lineage UI
open http://localhost:5001
```

Expected:

- Airflow `/health` → `200 OK` with `metadatabase: healthy`.
- UC API returns `["unity"]`; schemas `["bronze","silver","gold"]` exist.
- Tables count > 0 once the DAG has run.

## Quick Start (without the docker stack)

```bash
make dev-setup    # uv sync --all-extras
make test         # pytest tests/ -v
make lint         # ruff check
make format       # ruff format
make validate     # contracts + DQ rules
```

## Project Layout

```
{{cookiecutter.project_name}}/
├── src/{{cookiecutter.project_name}}/
│   ├── bronze/           # raw → Bronze ingestion (config-driven)
│   ├── silver/           # Bronze → Silver transforms (SCD2 + conformed)
│   ├── gold/             # Silver → Gold marts
│   └── utils/            # cross-cutting helpers (config, logging, spark)
├── airflow/
│   ├── dags/             # Airflow DAG definitions
│   └── configs/          # per-table ingestion YAML configs
├── contracts/            # StructType schema contracts (one per table)
│   └── dq/               # per-table DQ rule pointers
├── dq_rules/             # Spark-Expectations rule YAMLs
├── ddl/liquibase/        # schema migration changelogs
├── tests/                # mirrors src/ layout
├── _infra/
│   ├── docker/           # local dev stack
│   ├── ci/               # CI workflow templates
│   └── cd/               # environment configs (dev/stage/prod)
└── scripts/              # one-off utilities (uc_init.py, etc.)
```

## Using the Developer Plugin

This project is generated and maintained by the chapter-5
`developer-plugin`. Re-run any of its skills to regenerate or refresh
specific layers:

| Skill                                      | What it does                                     |
|--------------------------------------------|--------------------------------------------------|
| `/developer-plugin:create-scaffold`        | Bootstrap a new project from the cookiecutter    |
| `/developer-plugin:update-scaffold`        | Patch scaffold after LLD/DMS changes             |
| `/developer-plugin:validate-scaffold`      | Static + smoke-test check of the foundation     |
| `/developer-plugin:create-dag`             | Generate the Airflow DAG from the LLD            |
| `/developer-plugin:create-ingestion`       | Generate Bronze runner + per-table configs       |
| `/developer-plugin:create-pipeline`        | Generate CI/CD workflow files                    |
| `/developer-plugin:implement-stories`      | Dispatch create/update skills for a story/epic   |
| `/developer-plugin:validate-stories`       | Verify code against story acceptance criteria    |
| `/developer-plugin:complete-stories`       | Mark stories Done once AC checks pass            |

See `CLAUDE.md` for the full skill catalogue and chapter conventions.

## Workflow

1. Planning plugins (BA → Architect → Data Modeler → Mapping Analyst →
   DQ Engineer → Technical Lead → Scrum Master) produce approved
   artifacts under `../outputs/{artifact}/v{N}/`.
2. `/developer-plugin:implement-stories <STORY-ID|EPIC-NN|Sprint-N>`
   dispatches the right generator for each story.
3. Each generator writes only the files it owns; nothing else is
   touched. Re-run `validate-*` skills before marking stories Done.

## Troubleshooting

- **`make dev-up` fails on UC health-check** — UC OSS startup can take
  ~30s. Check `docker compose logs unity-catalog`. If the port `8080` is
  already in use, stop the conflicting process or remap.
- **`java -version` shows JDK 8/11** — Spark 4.x requires JDK 17+. Set
  `JAVA_HOME` to a JDK 17 install (`brew install openjdk@17` on macOS).
- **`make seed-source-data` fails with "TODO"** — the template ships only a
  stub. The runtime-bootstrap story (`STORY-01-NNN`) defines what your source
  loader does; implement `scripts/seed_source_data.py` per its ACs.
- **Airflow DAG not loading** — check `airflow/configs/*.yml` exists and
  `AIRFLOW__CORE__DAGS_FOLDER` points at `airflow/dags/`.
- **Contracts out of sync with DMS** —
  `/developer-plugin:update-scaffold sync-contracts`.
- **Cookiecutter template bumped** —
  `/developer-plugin:update-scaffold sync-template`.

---
Generated by cookiecutter-chapter on first scaffold; safe to edit.
