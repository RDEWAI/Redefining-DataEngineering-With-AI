# Team Capabilities

| Field | Value |
|---|---|
| **Project** | Patient 360 — Medallion Pipeline |
| **Version** | 1.0 |
| **Last Updated** | 2026-03-14 |

---

## 1. Languages & Runtimes

| Capability | Proficiency | Evidence |
|-----------|------------|---------|
| Python 3.10–3.12 | High | Entire pipeline, scripts, and tests written in Python; type annotations, `__future__` imports, dataclass-style config dicts |
| PySpark (DataFrame API) | High | Bronze ingestion with schema enforcement, Silver SCD2 via DataFrame + Delta MERGE INTO, Gold aggregations — all using DataFrame API (no RDDs) |
| Spark SQL | Medium | Used in `make spark-sql` interactive shell and Spark Declarative Pipeline materialized views |
| SQL (general) | High | SCD2 merge logic, UC REST API queries, PostgreSQL backend |
| Java | Awareness only | Not written directly; required for Spark JVM — team knows to set `JAVA_HOME` and select Java 11/17 |

---

## 2. Data Engineering Patterns

| Pattern | Proficiency | Evidence |
|---------|------------|---------|
| Medallion Architecture (Bronze/Silver/Gold) | High | Full 3-layer implementation with clear separation of concerns |
| SCD Type 2 | High | Reusable `apply_scd2()` function using Delta `MERGE INTO`; SHA-256 change detection; surrogate keys; expire + insert pattern |
| Delta Lake | High | ACID tables, partitioned writes with `replaceWhere`, idempotent loads, `MERGE INTO` for upserts |
| Schema enforcement | High | All 10 source tables have explicit `StructType` schemas; schema-on-read with strict casting |
| Idempotent pipeline design | High | All layers are re-runnable for same `ds`; `replaceWhere` partition overwrite |
| Partitioning strategy | High | All tables partitioned by `ds` (load date); consistent across all layers |
| Data quality rule authoring | Medium | Spark Expectations JSON rules defined for bronze tables; DQ integration into pipeline code not yet complete |
| Declarative pipeline specs | Medium | `spark-pipeline.yml` written; `@dp.table` and `@dp.materialized_view` decorators used in `pipelines/` |

---

## 3. Infrastructure & DevOps

| Capability | Proficiency | Evidence |
|-----------|------------|---------|
| Docker / Docker Compose | High | Multi-service compose file (UC OSS + Marquez + PostgreSQL); named volumes; health checks; platform targeting |
| Unity Catalog OSS (setup & operation) | Medium | Bootstrap script (`uc_init.py`) with retry logic; REST API usage; catalog/schema creation |
| OpenLineage / Marquez | Medium | Listener configured in SparkSession; lineage events visible in Marquez UI; no custom facets |
| UV (Python package management) | High | Used for all environment setup; `uv sync --all-groups`; replaces pip/poetry |
| Make-based task automation | High | Comprehensive `Makefile` covering dev-setup, uc-start/stop, all pipeline layers, test, lint, clean |
| Pre-commit hooks | Medium | Repo-level ruff + pytest hooks per chapter; know how to scope hooks per directory |
| Git | High | Feature branches, PR workflow |

---

## 4. Testing

| Capability | Proficiency | Evidence |
|-----------|------------|---------|
| pytest | High | Session-scoped SparkSession fixture; parametrized tests; `@pytest.mark.integration` marker |
| Spark unit testing (local mode) | High | Tests use `DeltaCatalog` — fully isolated from UC server; temp warehouse per test session |
| SCD2 correctness testing | High | `verify_scd2.py` with 14 discrete checks; `test_scd2.py` with behavioral assertions |
| Integration testing | Medium | Integration tests marked but require real Synthea data; not in CI by default |
| Test data generation | High | `gen_delta_load.py` generates controlled mutations (10% patients changed, 5% providers changed) for SCD2 verification |

---

## 5. Code Quality & Standards

| Standard | Detail |
|---------|--------|
| Linter | Ruff — rules E, F, I, N, W, UP; line-length=100 |
| Import sorting | Ruff `I` rule (isort-compatible) |
| Target Python version | 3.10 (syntax baseline) |
| Reusability | Generic over repeated code — `apply_scd2()` handles all 4 dims via `SCD2_CONFIG` dict |
| Factory pattern | `get_spark()` factory in `utils/spark.py` — single source of SparkSession config |
| No magic strings | Table names, schema names, column lists defined in config dicts, not inline |

---

## 6. Domain Knowledge

| Domain | Proficiency | Evidence |
|--------|------------|---------|
| Healthcare data (Synthea) | High | Deep familiarity with Synthea schema — all 10 tables with correct field names, types, nullability |
| Patient 360 concept | High | Gold `patient_summary` aggregates encounters, conditions, medications, allergies, claims per patient |
| SNOMED CT (conditions) | Awareness | Code and description fields mapped in `fct_conditions` |
| RxNorm (medications) | Awareness | Code and description fields mapped in `fct_medications` |
| LOINC (observations) | Awareness | Code and description fields mapped in `fct_observations` |
| ICD-10 billing codes | Awareness | Claims table includes diagnosis codes |

---

## 7. Gaps & Upskilling Needed

| Gap | Impact | Suggested Path |
|-----|--------|----------------|
| Spark Expectations library integration | DQ rules exist but are not enforced in pipeline code | Activate `spark-expectations` in bronze ingest and silver transforms |
| Column-level lineage | UC OSS 0.4.0 does not provide column lineage | Evaluate DataHub or Databricks Unity Catalog for production |
| Cloud deployment | Pipeline runs only in local mode | Learn Spark on Databricks / EMR / Dataproc for scale-out |
| Schema evolution | No `mergeSchema` handling — new CSV columns would break ingest | Add schema evolution strategy (mergeSchema + versioned schemas) |
| Pipeline orchestration | No scheduler — manual `make pipeline` or `run_local.py` | Evaluate Airflow, Prefect, or Databricks Workflows for production |
| Streaming pipelines | All pipelines are batch (`ds`-partitioned) | Evaluate Spark Structured Streaming for near-real-time use cases |
| Production secret management | Local dev uses empty tokens and hardcoded credentials | Integrate Vault, AWS Secrets Manager, or environment-scoped secrets |
