# Infrastructure Specifications


| Field            | Value                     |
| ---------------- | ------------------------- |
| **Version**      | 1.0                       |
| **Last Updated** | 2026-03-22                |
| **Owner**        | Platform Engineering      |
| **Applies To**   | Patient 360 Data Pipeline |


---

## 1. Compute Resources

### 1.1 Spark Cluster


| Parameter           | DEV | STAGING | PROD |
| ------------------- | --- | ------- | ---- |
| Driver memory       | 2g  | 4g      | 8g   |
| Driver cores        | 1   | 2       | 4    |
| Executor memory     | 2g  | 4g      | 8g   |
| Executor cores      | 1   | 2       | 4    |
| Number of executors | 1   | 2       | 4    |
| Dynamic allocation  | Off | On      | On   |
| Max executors       | —   | 4       | 8    |


### 1.2 Resource Limits


| Resource                   | Limit                        | Notes                         |
| -------------------------- | ---------------------------- | ----------------------------- |
| Max concurrent pipelines   | 2 (DEV), 3 (PROD)            | Prevent cluster overload      |
| Pipeline timeout           | 60 min (DEV), 120 min (PROD) | Kill runaway jobs             |
| Max shuffle partition size | 200 MB                       | Prevent OOM                   |
| Temp storage quota         | 50 GB per pipeline run       | Auto-cleanup after completion |


---

## 2. Storage

### 2.1 Storage Layout


| Layer       | Path Pattern                                  | Format  | Retention |
| ----------- | --------------------------------------------- | ------- | --------- |
| Bronze      | `warehouse/{env}/bronze/{table}/ds={date}/`   | Delta   | 90 days   |
| Silver      | `warehouse/{env}/silver/{schema}/{table}/`    | Delta   | 1 year    |
| Gold        | `warehouse/{env}/gold/{table}/`               | Delta   | 7 years   |
| Dead Letter | `warehouse/{env}/dead-letter/{table}/{date}/` | Parquet | 30 days   |
| Checkpoints | `warehouse/{env}/checkpoints/{pipeline}/`     | JSON    | 7 days    |


### 2.2 Delta Lake Settings


| Setting          | Value                  | Reason                   |
| ---------------- | ---------------------- | ------------------------ |
| Table format     | Delta Lake 4.x         | ACID, time travel, MERGE |
| Compression      | Snappy (default)       | Fast decompression       |
| Target file size | 128 MB                 | Optimal for Spark read   |
| Auto-compact     | Enabled (PROD)         | Prevent small files      |
| Vacuum retention | 168 hours (7 days)     | Time travel window       |
| Z-order columns  | Per-table (see DMS §7) | Query optimization       |


---

## 3. CI/CD Pipeline

### 3.1 GitHub Actions Stages


| Stage            | Trigger                       | Actions                                              |
| ---------------- | ----------------------------- | ---------------------------------------------------- |
| Lint             | PR opened/updated             | `ruff check`, `ruff format --check`                  |
| Unit Test        | PR opened/updated             | `pytest tests/unit/`                                 |
| Integration Test | PR to `main`                  | `pytest tests/integration/` with Unity Catalog OSS   |

### 3.2 Local Make Targets


| Target                 | Command                        | Purpose                              |
| ---------------------- | ------------------------------ | ------------------------------------ |
| `make lint`            | `ruff check && ruff format --check` | Lint and format check           |
| `make test-unit`       | `pytest tests/unit/`           | Run unit tests                       |
| `make test-integration`| `pytest tests/integration/`    | Run integration tests with UC OSS   |
| `make test`            | `make test-unit test-integration` | Run all tests                     |
| `make run-pipeline`    | `python -m src.main`          | Run the full pipeline locally        |


---

## 4. Networking & Security


| Aspect                | Specification                                          |
| --------------------- | ------------------------------------------------------ |
| Database access       | Unity Catalog OSS (all environments, local)            |
| Encryption at rest    | AES-256 (Delta Lake native)                            |
| Encryption in transit | N/A (all local)                                        |
| Service accounts      | N/A (local execution)                                  |
| Secrets management    | Environment variables / `.env` files (all environments)|


---

## 5. Monitoring Infrastructure


| Component          | Tool                  | Purpose                                  |
| ------------------ | --------------------- | ---------------------------------------- |
| Metrics collection | OpenTelemetry SDK     | Pipeline metrics, task durations         |
| Metrics storage    | Prometheus            | Time-series metrics                      |
| Dashboards         | Grafana               | Pipeline health, DQ scores, SLA tracking |
| Alerting           | Grafana Alerting      | PagerDuty integration for CRITICAL       |
| Log aggregation    | Loki                  | Centralized log search                   |
| Data lineage       | OpenLineage + Marquez | Column-level lineage tracking            |


