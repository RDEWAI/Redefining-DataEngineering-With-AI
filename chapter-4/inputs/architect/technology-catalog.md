# Technology Catalog

| Field | Value |
|---|---|
| **Project** | Patient 360 — Medallion Pipeline |
| **Version** | 1.0 |
| **Last Updated** | 2026-03-14 |
| **Owner** | Data Engineering Team |

---

## 1. Core Processing

| Tool | Version | Role | License |
|------|---------|------|---------|
| Apache Spark (PySpark) | 4.1.1+ | Distributed data processing — bronze ingestion, silver transforms, gold aggregations | Apache 2.0 |
| Delta Lake | 4.1.0 | ACID table format — all layers stored as Delta tables | Apache 2.0 |
| Spark Declarative Pipelines | Built into Spark 4.1 | Production pipeline orchestration via `spark-pipeline.yml` spec | Apache 2.0 |

**Scala binary**: Spark 4.1 uses Scala 2.13 (not 2.12 — affects all JAR coordinates).

---

## 2. Metastore

| Tool | Version | Role | License |
|------|---------|------|---------|
| Unity Catalog OSS | 0.4.0 | Table metadata store — catalogs, schemas, table registration | Apache 2.0 |
| PostgreSQL | 16 (Alpine) | Backend database for Marquez lineage store | PostgreSQL License |

**Catalog structure**:
- Catalog: `spark_catalog`
- Schemas: `bronze`, `silver`, `gold`
- REST API: `http://localhost:8080`
- Auth: none (local dev; token-based auth available for production)

**Replaces**: Derby embedded metastore (not suitable for multi-session or team use).

---

## 3. Lineage & Observability

| Tool | Version | Role | License |
|------|---------|------|---------|
| OpenLineage Spark Listener | 1.44.0 | Emits lineage events on every Spark job | Apache 2.0 |
| Marquez | latest | OpenLineage-compatible lineage backend — stores job + dataset lineage | Apache 2.0 |
| Marquez Web UI | latest | Lineage graph visualization — Bronze → Silver → Gold trace | Apache 2.0 |

**OpenLineage config**:
- Transport: HTTP
- Endpoint: `http://localhost:5001` (Marquez API)
- Namespace: `patient_360`
- UI: `http://localhost:3000`

---

## 4. Data Quality

| Tool | Version | Role | License |
|------|---------|------|---------|
| Nike Spark Expectations | 2.0.0+ | Rule-based DQ enforcement — not-null, valid ranges, valid enums | Apache 2.0 |

**Rule format**: JSON files per table in `expectations/bronze/` and `expectations/silver/`.

**Actions supported**: `fail` (halt pipeline), `drop` (remove bad rows), `warn` (log only).

**Current status**: Rule files defined for all 10 bronze tables. Integration into pipeline code is planned (silver expectations not yet populated).

**Example rule (patients)**:
```json
{ "rule": "patient_id_not_null",  "condition": "id IS NOT NULL",               "action": "fail"  }
{ "rule": "valid_birthdate",       "condition": "birthdate BETWEEN '1900-01-01' AND current_date()", "action": "drop" }
{ "rule": "valid_gender",          "condition": "gender IN ('M', 'F')",          "action": "warn"  }
```

---

## 5. Language & Runtime

| Tool | Version | Role |
|------|---------|------|
| Python | 3.10 – 3.12 | Primary language — PySpark, pytest, scripts |
| Java | 11 or 17 | Required by Spark (JVM runtime) |
| UV | latest | Python environment and dependency management |

**Python package manager**: UV (`uv sync --all-groups`) — replaces pip/poetry.

---

## 6. Testing

| Tool | Version | Role |
|------|---------|------|
| pytest | 8.0.0+ | Unit and integration test runner |
| pytest-mock | 3.12.0+ | Mocking support in unit tests |

**Test strategy**:
- Unit tests: in-process local SparkSession with `DeltaCatalog` — no UC server required
- Integration tests: marked `@pytest.mark.integration` — require real Synthea CSV data in `data/raw/`
- All 38 tests pass locally; test isolation via temp warehouse directory per session

---

## 7. Code Quality

| Tool | Version | Role |
|------|---------|------|
| Ruff | 0.1.0+ | Linter + import sorter |

**Ruff config**: line-length=100, target-version=py310, rules: E, F, I, N, W, UP.

---

## 8. Infrastructure & Containerization

| Tool | Version | Role |
|------|---------|------|
| Docker | 24+ | Container runtime for UC OSS + Marquez |
| Docker Compose | v2 | Multi-service orchestration (`docker-compose.yml`) |

---

## 9. Source Data

| Attribute | Value |
|-----------|-------|
| Dataset | Synthea — synthetic healthcare records |
| Format | CSV (10 files) |
| Volume | 5,767 patients; ~3.3 GB uncompressed (including observations) |
| Location | `data/raw/` (one level above MVP directory) |
| Tables | patients, encounters, conditions, medications, observations, allergies, claims, organizations, providers, payers |

---

## 10. JAR Dependency Coordinates

All JARs are resolved automatically via `spark.jars.packages` on first run and cached in `~/.ivy2/`.

| JAR | Coordinate |
|-----|-----------|
| Delta Lake | `io.delta:delta-spark_4.1_2.13:4.1.0` |
| Unity Catalog Spark Connector | `io.unitycatalog:unitycatalog-spark_2.13:0.4.0` |
| OpenLineage Spark Listener | `io.openlineage:openlineage-spark_2.13:1.44.0` |

First-run download size: ~200 MB. Subsequent runs use local cache.
