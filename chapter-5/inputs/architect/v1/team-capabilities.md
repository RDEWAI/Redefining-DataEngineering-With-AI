# Team Capabilities

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Last Updated** | 2026-03-15 |

### Proficiency Levels

| Level | Meaning |
|-------|---------|
| **Proficient** | Team can design, build, and troubleshoot independently |
| **Familiar** | Team has working knowledge; can contribute with some ramp-up |
| **Not Experienced** | Team has no practical experience; would need training or external support |

---

## 1. Languages & Runtimes

| Capability | Level |
|-----------|-------|
| Python 3.10–3.12 | Proficient |
| PySpark (DataFrame API) | Proficient |
| SQL (general) | Proficient |
| Spark SQL | Proficient |
| Java | Familiar — JVM configuration only, not application code |
| Scala | Not Experienced |
| Rust | Not Experienced |

---

## 2. Data Engineering Patterns

| Pattern | Level |
|---------|-------|
| Medallion Architecture (Bronze / Silver / Gold) | Proficient |
| SCD Type 2 (Delta MERGE INTO) | Proficient |
| Delta Lake (ACID, partitioned writes, upserts) | Proficient |
| Schema enforcement (StructType, schema-on-read) | Proficient |
| Idempotent / re-runnable pipelines | Proficient |
| Partitioning strategies | Proficient |
| Spark Expectations (YAML rule authoring) | Familiar |
| Spark Declarative Pipelines | Familiar |
| Schema evolution (mergeSchema) | Familiar |
| Streaming (Structured Streaming) | Not Experienced |

---

## 3. Infrastructure & DevOps

| Capability | Level |
|-----------|-------|
| Docker / Docker Compose | Proficient |
| Make-based task automation | Proficient |
| Git (feature branches, PR workflow) | Proficient |
| UV (Python package management) | Proficient |
| Airflow | Proficient |
| Pre-commit hooks (ruff, pytest) | Familiar |
| Unity Catalog OSS (REST API, catalog bootstrap) | Familiar |
| OpenLineage / Marquez | Familiar |
| Cloud deployment (Databricks, EMR, Dataproc) | Not Experienced |
| Production secret management (Vault, etc.) | Not Experienced |

---

## 4. Testing

| Capability | Level |
|-----------|-------|
| pytest (fixtures, parametrize, markers) | Proficient |
| Spark unit testing (local mode, DeltaCatalog) | Proficient |
| Test data generation (controlled mutations) | Proficient |
| Integration testing (real data, marked tests) | Familiar |
