---
last_verified: 2026-04-24
verified_by: initial-seed
freshness_policy: warn-after-30-days
---

# Library & Runtime Version Catalog

Canonical pinned versions the **developer-plugin** uses when generating
`pyproject.toml`, `docker-compose.yml`, Spark session configuration,
Airflow DAGs, and CI/CD workflows. **Do not hand-edit this file** — run
`/developer-plugin:refresh-libraries` to regenerate.

The `last_verified` date above drives the freshness check in every
`create-*` / `update-*` / `implement-stories` skill: if the date is older
than the `freshness_policy` window, the skill pauses and prompts the user
(via `AskUserQuestion`) to refresh.

## Versions

| Library | Version | Docs URL | Breaking-change note since prior pin |
|---|---|---|---|
| PySpark `pyspark[pipelines]` | 4.1.1 | https://spark.apache.org/docs/4.1.1/api/python/index.html | — |
| Delta Lake `delta-spark` (PyPI) | 4.2.0 | https://docs.delta.io/latest/index.html | Minor bump from 4.0.0; API-compatible with 4.x line. |
| Delta Lake `delta-spark_2.13` (Maven jar) | 4.2.0 | https://central.sonatype.com/artifact/io.delta/delta-spark_2.13 | Use the `_2.13` coordinate — PySpark 4.x ships Scala 2.13 by default; `_2.12` variant lags at 3.3.2. |
| Unity Catalog OSS server | 0.4.1 | https://docs.unitycatalog.io/ | 0.4.1 adds credential-scoped FS + atomic RTAS/DPO — enable by pairing with Delta 4.2.0. |
| Unity Catalog OSS `unitycatalog-spark_2.13` (jar) | 0.4.1 | https://central.sonatype.com/artifact/io.unitycatalog/unitycatalog-spark_2.13 | Server and Spark jar are now aligned on the same release stream. |
| OpenLineage Spark Listener `openlineage-spark_2.13` | 1.46.0 | https://openlineage.io/docs/integrations/spark/ | Minor-version bumps from 1.44.x; no breaking listener-config changes. |
| Marquez (Docker image tag) | 0.51.1 | https://marquezproject.github.io/marquez/ | Pin the concrete Docker tag `0.51.1` (Docker Hub, 2025-03-27) — **do not use `latest`**. GitHub Releases page is stale at 0.50.0. |
| Nike Spark Expectations | 2.10.0 | https://engineering.nike.com/spark-expectations/ | 2.x family; adds rule types and reporting hooks since 2.0.0 with no documented breaking changes. |
| Apache Airflow | 3.2.1 | https://airflow.apache.org/docs/apache-airflow/3.2.1/ | 3.x is current stable; Airflow 2.x is maintenance-only. Generate DAGs against the 3.x DSL (`@task`, `TaskFlow`). |
| DuckDB (Python) | 1.5.2 | https://duckdb.org/docs/ | Minor bump from 1.4.4; SQL/API compatible. |
| UV | 0.11.7 | https://docs.astral.sh/uv/ | Still pre-1.0; pin exactly in CI. |
| pytest | 9.0.3 | https://docs.pytest.org/en/stable/ | **Major bump 8 → 9** drops Python 3.8 and removes some deprecated fixtures/APIs — run `pytest --deprecated-types` before bumping consumers. |
| pytest-mock | 3.15.1 | https://pytest-mock.readthedocs.io/en/latest/ | Minor bumps only from 3.12.0. |
| ruff | 0.15.11 | https://docs.astral.sh/ruff/ | Still 0.x — rule selectors shift frequently; pin exactly and review `ruff check --diff` on bump. |
| Python | >=3.11,<3.14 | https://devguide.python.org/versions/ | **Raised floor** from 3.10 (EOL 2026-10-31) to 3.11 (EOL 2027-10-31). Ceiling `<3.14` — PySpark 4.1.1 publishes wheels for 3.10–3.13 only. |

## Jars to download via `spark.jars.packages`

```
io.delta:delta-spark_2.13:4.2.0
io.unitycatalog:unitycatalog-spark_2.13:0.4.1
io.openlineage:openlineage-spark_2.13:1.46.0
```

First-run downloads are cached in `~/.ivy2/`.

## Python runtime matrix (generated `pyproject.toml`)

```toml
[project]
requires-python = ">=3.11,<3.14"
dependencies = [
    "pyspark[pipelines]>=4.1.1",
    "delta-spark>=4.2.0",
    "spark-expectations>=2.10.0",
    "duckdb>=1.5.2",
]

[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-mock>=3.15.1",
    "ruff>=0.15.11",
]
```

## Resolution sources (how each row was verified)

- **PySpark** — context7 (`/websites/spark_apache_api_python`) + PyPI `requires_dist` for the `pipelines` extra.
- **Delta Lake** — context7 (`/delta-io/delta`) + PyPI `delta-spark` + Maven Central `maven-metadata.xml`.
- **Unity Catalog OSS** — GitHub Releases API + Maven Central metadata.
- **OpenLineage** — GitHub Releases API + Maven Central metadata.
- **Marquez** — Docker Hub tags API + GitHub Tags (GH Releases page is stale).
- **Spark Expectations** — GitHub Releases API + PyPI.
- **Airflow** — context7 (`/apache/airflow`) + PyPI.
- **DuckDB / pytest / pytest-mock / ruff** — PyPI JSON API.
- **UV** — astral-sh/uv GitHub Releases.
- **Python** — endoflife.date API for lifecycle dates.

## Rotation policy

- `refresh-libraries` writes a new `last_verified` on every successful run.
- If a library's version changes by a **major** (e.g. pytest 8 → 9), the
  refresh skill surfaces the breaking-change note for explicit user
  acknowledgement before writing.
- Historical deltas are appended to `chapter-5/memory/developer/learnings-queue.jsonl`.
