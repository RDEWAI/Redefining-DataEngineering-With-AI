# Technology Catalog

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Last Updated** | 2026-03-15 |
| **Owner** | Data Engineering Team |

---

## 1. Core Processing

| Tool | Version | Role | License |
|------|---------|------|---------|
| Apache Spark (PySpark) | 4.1.1+ | Distributed data processing — bronze ingestion, silver transforms, gold aggregations | Apache 2.0 |
| Delta Lake | 4.1.0 | ACID table format — all layers stored as Delta tables | Apache 2.0 |
| Spark Declarative Pipelines | Built into Spark 4.1 | Production pipeline orchestration via `spark-pipeline.yml` spec | Apache 2.0 |

---

## 2. Metastore

| Tool | Version | Role | License |
|------|---------|------|---------|
| Unity Catalog OSS | 0.4.0 | Table metadata store — catalogs, schemas, table registration | Apache 2.0 |
| PostgreSQL | 16 (Alpine) | Backend database for Marquez lineage store | PostgreSQL License |

---

## 3. Lineage & Observability

| Tool | Version | Role | License |
|------|---------|------|---------|
| OpenLineage Spark Listener | 1.44.0 | Emits lineage events on every Spark job | Apache 2.0 |
| Marquez | latest | OpenLineage-compatible lineage backend — stores job + dataset lineage | Apache 2.0 |
| Marquez Web UI | latest | Lineage graph visualization — Bronze → Silver → Gold trace | Apache 2.0 |

---

## 4. Containerization

| Tool | Version | Role | License |
|------|---------|------|---------|
| Docker | 24+ | Container runtime — all services run inside Docker | Apache 2.0 |
| Docker Compose | v2 | Multi-service orchestration — single `docker-compose.yml` manages all containers | Apache 2.0 |

---

## 5. Data Quality

| Tool | Version | Role | License |
|------|---------|------|---------|
| Nike Spark Expectations | 2.0.0+ | Rule-based DQ enforcement — not-null, valid ranges, valid enums | Apache 2.0 |

**Rule format**: YAML files per table (JSON also supported). Files placed in `expectations/<layer>/`.

**Rule types**: `row_dq` (row-level), `agg_dq` (aggregate), `query_dq` (SQL query-based).

**Actions supported**: `fail` (halt pipeline), `drop` (remove bad rows), `ignore` (log only).

**Example rule definition** (YAML):
```yaml
rules:
  - rule: id_not_null
    rule_type: row_dq
    column_name: id
    expectation: "id IS NOT NULL"
    action_if_failed: drop
    tag: completeness
    description: "Primary key must not be null"
    priority: high
  - rule: date_in_valid_range
    rule_type: row_dq
    column_name: event_date
    expectation: "event_date BETWEEN '1900-01-01' AND current_date()"
    action_if_failed: drop
    tag: validity
    description: "Date must be within valid range"
  - rule: table_row_count
    rule_type: agg_dq
    expectation: "count(*) > 0"
    action_if_failed: fail
    tag: completeness
    description: "Table must contain at least one row"
```
