# patient_360

Medallion data pipeline (Bronze → Silver → Gold) generated from the
chapter-5 cookiecutter template by the `developer-plugin` skills.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (package + env manager)
- JDK 17+ (required by Spark 4.x)
- Docker + Docker Compose (for the local Airflow / Unity Catalog stack)

## Bootstrap

Canonical local bring-up is two commands (LLD v1.17 §13 Decision 17 Revised
— keeps UC table registration separate from stack startup so contributors
can re-run table registration after editing `contracts/*.yml` without
bouncing the docker stack):

```bash
make dev-up && make bootstrap-uc
```

`make dev-up` wraps:

1. `docker compose -f _infra/docker/docker-compose.yml up -d` (Airflow + UC OSS + Marquez + Postgres + Grafana)
2. Wait for UC OSS REST API to return `200` on `localhost:8080/api/2.1/unity-catalog`
3. `python scripts/uc_init.py` — creates `unity` catalog + `bronze`/`silver`/`gold` schemas
4. `make seed-source-data` — **project-specific**; you implement this against your source system (DuckDB / Postgres / S3 / etc.). The generated `runtime-bootstrap` story (typically `STORY-01-NNN`) tells you exactly what to populate.

`make bootstrap-uc` then runs `scripts/bootstrap_uc_tables.py` — a
one-shot Spark application that boots a SparkSession with
`UCSingleCatalog` bound to `spark.sql.catalog.${UC_BOOTSTRAP_CATALOG_NAME}`
(DDL-only — runtime DAG tasks remain `DeltaCatalog` per LLD §13
Decision 12), reads every populated `contracts/*.yml` directly, and
issues `CREATE SCHEMA IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS …
USING DELTA LOCATION '<warehouse_root>/<env>/<layer>/<domain>/<table>/'`
per contract. Every statement is `IF NOT EXISTS`, so re-runs are
idempotent. No Liquibase invocation against UC — the v1.16
Liquibase-over-UC-JDBC path was abandoned because
`io.unitycatalog:unitycatalog-jdbc` is not published on Maven Central
(Decision 17 v1.17, 2026-05-23). Liquibase reverts to its pre-v1.16
Postgres-only audit-trail role.

Re-run `make bootstrap-uc` any time you edit a contract — no need to bounce
`make dev-up`. Runtime Spark writers are FORBIDDEN from calling `CREATE
TABLE`; UC visibility is a deploy-time invariant owned by `bootstrap-uc`.

After `make dev-up && make bootstrap-uc` completes, see **Verify** below.

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

### Run Bronze ingestion

The generic Bronze ingestion runner (`src/patient_360/bronze/ingestion_runner.py`)
drives all Bronze tasks from per-table YAML in `airflow/configs/`. It is
invoked by the DAG's `SparkSubmitOperator`, but can also be run directly:

```bash
# From the patient_360 project root
uv run python -m patient_360.bronze.ingestion_runner \
  --config-path airflow/configs/<table>.yml \
  --ds $(date -u +%Y-%m-%d) \
  --env DEV
```

Args:

- `--config-path` (required) — per-table YAML (e.g. `airflow/configs/patients.yml`)
- `--ds` (required) — logical date `YYYY-MM-DD`; partition value for the write
- `--env` (default `DEV`) — pipeline environment (`DEV` / `STAGING` / `PROD`); maps to the SE `dq_env`

The runner enforces the StructType from `contracts/{table}.yml` (no schema
inference, LLD §2.3), runs `se_runner.run_dq(...)` inline, and writes via
`saveAsTable('<catalog>.<schema>.{table}')` with `replaceWhere ds = '<ds>'`
for idempotent re-runs (LLD §13 Decision 15). The `UC_URI` env var points
the Spark session at the Unity Catalog OSS service (LLD §7.1).

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
patient_360/
├── src/patient_360/
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
