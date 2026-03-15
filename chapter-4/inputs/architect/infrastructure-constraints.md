# Infrastructure Constraints

| Field | Value |
|---|---|
| **Project** | Patient 360 — Medallion Pipeline |
| **Environment** | Local Development (Docker) |
| **Version** | 1.0 |
| **Last Updated** | 2026-03-14 |

---

## 1. Compute Constraints

| Constraint | Value | Implication |
|-----------|-------|-------------|
| Spark driver memory | 4 GB | Set in `spark.driver.memory`; local mode only — no cluster |
| Spark executor memory | 4 GB | Set in `spark.executor.memory`; single executor in local mode |
| Shuffle partitions | 8 | `spark.sql.shuffle.partitions = 8`; tuned for ~5,700-row dataset |
| Execution mode | Local (`local[*]`) | All processing on a single machine; no YARN/K8s cluster |
| Adaptive Query Execution | Enabled | `spark.sql.adaptive.enabled = true` |
| Spark Web UI | Disabled | `spark.ui.enabled = false` (local dev only) |

**Minimum machine spec** (local dev):
- RAM: 16 GB recommended (4 GB driver + 4 GB executor + OS + Docker overhead)
- CPU: 4+ cores
- Disk: 20 GB free (Spark warehouse + JAR cache + source CSVs)
- Java: 11 or 17 (Spark 4.1 requirement; Java 21 is not yet supported)

---

## 2. Storage Constraints

| Constraint | Value | Implication |
|-----------|-------|-------------|
| Table format | Delta Lake only | All tables (bronze, silver, gold) must be Delta; no Parquet/ORC/Iceberg |
| Warehouse location | `warehouse/` (local) | Relative to MVP root; change `spark.sql.warehouse.dir` for cloud |
| Partition scheme | `ds` (YYYY-MM-DD string) | All tables partitioned by load date; required for idempotent re-runs |
| Write mode | `overwrite` with `replaceWhere=ds='{ds}'` | Idempotent: re-running same DS overwrites that partition only |
| Observations table | Excluded from delta testing | 4.4 M rows — too large for local delta load generation; delta testing skips observations |
| UC metadata storage | Named Docker volume (`unitycatalog_data`) | Persists across restarts; lost if volume is deleted |
| Lineage storage | Named Docker volume (`marquez_data`) via PostgreSQL | Persists across restarts |

---

## 3. Networking Constraints

| Service | Host Port | Container Port | Notes |
|---------|-----------|----------------|-------|
| Unity Catalog REST API | 8080 | 8080 | Required before any pipeline run; `make uc-start` |
| Marquez API (OpenLineage ingest) | 5001 | 5000 | Port 5000 remapped — macOS AirPlay occupies 5000 |
| Marquez Web UI | 3000 | 3000 | Lineage visualization |
| PostgreSQL (Marquez backend) | 5432 | 5432 | Internal; not exposed to host in production |

**Critical**: Port 5000 is remapped to 5001 on the host due to macOS AirPlay Receiver conflict. All Spark and OpenLineage configs reference `localhost:5001` — not `localhost:5000`.

---

## 4. Authentication & Security Constraints

| Area | Current State | Production Requirement |
|------|--------------|------------------------|
| Unity Catalog auth | Token = `""` (empty, no auth) | OAuth / PAT token required |
| Marquez | No auth | API key or mTLS |
| PostgreSQL (Marquez) | Local credentials (`marquez/marquez`) | Managed secrets (Vault, AWS Secrets Manager) |
| Delta table access | File-system level only | Unity Catalog ACLs / cloud IAM |
| Spark Declarative Pipelines | No auth | Service principal / workspace token |

---

## 5. Metastore Constraints

| Constraint | Detail |
|-----------|--------|
| Catalog name | Must be `spark_catalog` — Spark's default catalog; cannot use arbitrary names without additional config |
| UC version | 0.4.0 OSS — no built-in column-level lineage REST API |
| Lineage source | OpenLineage Spark Listener only — UC does not capture lineage directly |
| Schema bootstrap | `scripts/uc_init.py` must run once after `docker compose up` before the first pipeline execution |
| Retry logic | `uc_init.py` retries up to 18 times (90 s total) waiting for UC server to become healthy |
| Derby | Not used; UC OSS replaces Derby entirely — do not configure `javax.jdo` properties |

---

## 6. Platform Constraints

| Constraint | Detail |
|-----------|--------|
| OS (local dev) | macOS (Apple Silicon and Intel tested); Linux supported |
| Docker platform | `marquez` and `marquez-web` images are `linux/amd64` only — run via Rosetta on Apple Silicon |
| Unity Catalog image | Multi-arch (`linux/amd64` + `linux/arm64`) — no emulation needed |
| CI/CD | Pre-commit hooks scoped per chapter (ruff + pytest); chapter-4 not yet added to `.pre-commit-config.yaml` |

---

## 7. Pipeline Execution Constraints

| Constraint | Detail |
|-----------|--------|
| Layer ordering | Bronze must complete before Silver; Silver must complete before Gold |
| UC must be running | All layers require Unity Catalog at `localhost:8080` |
| Idempotency | Re-running for the same `ds` is safe — replaces that partition only |
| First pipeline run | Downloads ~200 MB of JARs to `~/.ivy2/`; subsequent runs use cache |
| Observations in tests | `gen_delta_load.py` skips observations (4.4 M rows); delta load test results exclude obs |
| Spark SQL shell | `make spark-sql` requires UC to be running and `uc_init.py` to have already run |

---

## 8. Data Volume Constraints (Local Dev)

| Table | Approx. Row Count | Notes |
|-------|------------------|-------|
| bronze.patients | 5,767 | First load |
| bronze.encounters | ~150,000 | Estimated from Synthea defaults |
| bronze.observations | ~4,400,000 | Largest table — skipped in delta load tests |
| bronze.conditions | ~80,000 | |
| bronze.medications | ~70,000 | |
| silver.dim_patients | 5,767 (v1) / 6,344 (v2) | After SCD2 delta: 577 changed → 2 versions each |
| gold.patient_summary | 5,767 | One row per current patient |

---

## 9. Known Limitations

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| Local mode only | No horizontal scaling | Move to cloud Spark cluster for production |
| UC OSS 0.4.0 has no column-level lineage | Cannot trace column-to-column lineage | Use Databricks Unity Catalog or DataHub for column lineage |
| No schema evolution handling | Adding columns to CSVs requires schema changes | Add `mergeSchema = true` option or version schemas |
| Marquez `latest` tag | Non-deterministic builds | Pin to specific Marquez version for reproducibility |
| Spark Expectations not yet active | DQ rules defined but not enforced | Wire `spark-expectations` library into ingest and transform steps |
| No retry/backfill mechanism | Failed pipeline for a given `ds` requires manual re-run | Add orchestrator (Airflow, Prefect) for production |
