# Low-Level Design: Patient 360 Medallion Pipeline

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-04-17 |
| **Last Modified** | 2026-04-17 |
| **Author** | Data Engineering Team |
| **Status** | Draft |
| **DRD Reference** | outputs/drd/v1/DRD-2026-03-10-patient-360.md |
| **HLD Reference** | outputs/hld/v1/HLD-2026-03-12-patient-360.md |
| **DMS Reference** | outputs/dms/v1/DMS-2026-03-15-patient-360.md |
| **STM Reference** | outputs/stm/v1/STM-2026-03-18-patient-360.xlsx |
| **DQS Reference** | outputs/dqs/v1/DQS-2026-03-20-patient-360.md |
| **Target Scaffold** | cookiecutter-chapter (see `inputs/lld/v1/templates/cookiecutter-chapter/`) |
| **Project Name** | patient_360 |
| **Chapter** | chapter-5 |

---

## 1. Design Overview

This LLD specifies the implementation of the Patient 360 medallion pipeline. It
turns the DMS logical model, STM mappings, and DQS rules into concrete Python
modules, Airflow DAGs, table contracts, and Liquibase changelogs laid out
according to the `cookiecutter-chapter` scaffold. Downstream developers in
chapter-5 render the scaffold with cookiecutter and implement exactly the files
named in §2.1, §5, and §9.

## 2. Code Architecture

### 2.1 Project Layout

The project structure below is the cookiecutter scaffold at
`inputs/lld/v1/templates/cookiecutter-chapter/{{cookiecutter.chapter_name}}/{{cookiecutter.project_name}}/`.
Every file path in §3, §4, §5, §7, and §9 must resolve inside this tree.

```
patient_360/
├── src/patient_360/
│   ├── bronze/
│   │   ├── patients.py
│   │   ├── encounters.py
│   │   ├── observations.py
│   │   └── config/
│   ├── silver/
│   │   ├── patient_dim.py
│   │   ├── encounter_fact.py
│   │   └── observation_fact.py
│   ├── gold/
│   │   ├── patient_360.py
│   │   └── readmission_risk.py
│   └── utils/
│       ├── spark_session.py
│       ├── contracts.py
│       └── dq.py
├── tests/
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── airflow/
│   ├── dags/
│   │   ├── patient_360_bronze.py
│   │   ├── patient_360_silver.py
│   │   └── patient_360_gold.py
│   └── configs/
│       ├── patient_360_bronze.yaml
│       ├── patient_360_silver.yaml
│       └── patient_360_gold.yaml
├── contracts/
│   ├── patients.yml
│   ├── encounters.yml
│   ├── observations.yml
│   ├── patient_dim.yml
│   ├── encounter_fact.yml
│   ├── observation_fact.yml
│   ├── patient_360.yml
│   └── dq/
├── dq_rules/
│   ├── patients.yml
│   ├── encounters.yml
│   ├── observations.yml
│   ├── patient_dim.yml
│   ├── encounter_fact.yml
│   ├── observation_fact.yml
│   └── patient_360.yml
├── ddl/
│   └── liquibase/
│       ├── changelogs/
│       │   ├── patients.xml
│       │   ├── encounters.xml
│       │   └── observations.xml
│       └── master.xml
├── _infra/
│   ├── ci/
│   │   └── github-actions.yaml
│   ├── cd/
│   │   ├── config/
│   │   │   ├── dev.yaml
│   │   │   ├── stage.yaml
│   │   │   └── prod.yaml
│   │   └── deploy.yaml
│   └── docker/
│       ├── Dockerfile.bronze
│       ├── Dockerfile.silver
│       └── Dockerfile.gold
├── scripts/
├── pyproject.toml
├── Makefile
└── CLAUDE.md
```

### 2.2 Module Responsibilities

| Module Path | DMS Layer | Responsibility |
|---|---|---|
| `src/patient_360/bronze/` | Bronze | Raw CSV → parquet ingestion with schema inference; one module per source table. |
| `src/patient_360/silver/` | Silver | Cleansed + conformed dims/facts from bronze; applies STM transformations. |
| `src/patient_360/gold/` | Gold | Patient 360 marts + readmission risk mart; business-ready aggregates. |
| `src/patient_360/utils/` | Cross-cutting | Spark session factory, contract loader, DQ runner (Spark-Expectations). |
| `airflow/dags/` | Orchestration | One DAG per layer; tasks call modules under `src/patient_360/<layer>/`. |
| `contracts/` | Governance | One YAML per table: DDL pointer + DQ pointer + column metadata. |
| `dq_rules/` | Data Quality | Spark-Expectations rule sets referenced by each contract. |
| `ddl/liquibase/` | Schema | Liquibase changelogs, one XML per table + a master.xml. |

## 3. File Formats & Storage Layout

| Layer | Scaffold Path | Format | Partitioning | Retention |
|---|---|---|---|---|
| Bronze | `s3://p360/bronze/{table}/` (written by `src/patient_360/bronze/*.py`) | Parquet (snappy) | `ingest_date` | 90 days |
| Silver | `s3://p360/silver/{table}/` (written by `src/patient_360/silver/*.py`) | Delta | `event_date` | 2 years |
| Gold | `s3://p360/gold/{mart}/` (written by `src/patient_360/gold/*.py`) | Delta | `snapshot_date` | 5 years |

Table contracts under `contracts/*.yml` point at the DDL in
`ddl/liquibase/changelogs/<table>.xml` and the DQ rules in
`dq_rules/<table>.yml`.

## 4. DAG Specification

| DAG ID | DAG File | Config File | Trigger | Layer |
|---|---|---|---|---|
| `patient_360_bronze` | `airflow/dags/patient_360_bronze.py` | `airflow/configs/patient_360_bronze.yaml` | `@daily` | Bronze |
| `patient_360_silver` | `airflow/dags/patient_360_silver.py` | `airflow/configs/patient_360_silver.yaml` | Sensor on bronze | Silver |
| `patient_360_gold` | `airflow/dags/patient_360_gold.py` | `airflow/configs/patient_360_gold.yaml` | Sensor on silver | Gold |

## 5. Task Implementation Details

| Task ID | Layer | Module Path | Contract File | DQ Rules File | DAG Task Node | Inputs | Outputs | Transform Ref | DQ Check |
|---|---|---|---|---|---|---|---|---|---|
| T-B01 | Bronze | `src/patient_360/bronze/patients.py` | `contracts/patients.yml` | `dq_rules/patients.yml` | `ingest_patients` | `s3://raw/synthea/patients.csv` | `s3://p360/bronze/patients/` | STM §2.1 | DQS R-001..R-004 |
| T-B02 | Bronze | `src/patient_360/bronze/encounters.py` | `contracts/encounters.yml` | `dq_rules/encounters.yml` | `ingest_encounters` | `s3://raw/synthea/encounters.csv` | `s3://p360/bronze/encounters/` | STM §2.2 | DQS R-010..R-014 |
| T-B03 | Bronze | `src/patient_360/bronze/observations.py` | `contracts/observations.yml` | `dq_rules/observations.yml` | `ingest_observations` | `s3://raw/synthea/observations.csv` | `s3://p360/bronze/observations/` | STM §2.3 | DQS R-020..R-023 |
| T-S01 | Silver | `src/patient_360/silver/patient_dim.py` | `contracts/patient_dim.yml` | `dq_rules/patient_dim.yml` | `build_patient_dim` | `s3://p360/bronze/patients/` | `s3://p360/silver/patient_dim/` | STM §3.1 | DQS R-101..R-105 |
| T-S02 | Silver | `src/patient_360/silver/encounter_fact.py` | `contracts/encounter_fact.yml` | `dq_rules/encounter_fact.yml` | `build_encounter_fact` | `bronze/encounters`, `silver/patient_dim` | `s3://p360/silver/encounter_fact/` | STM §3.2 | DQS R-110..R-115 |
| T-S03 | Silver | `src/patient_360/silver/observation_fact.py` | `contracts/observation_fact.yml` | `dq_rules/observation_fact.yml` | `build_observation_fact` | `bronze/observations`, `silver/patient_dim` | `s3://p360/silver/observation_fact/` | STM §3.3 | DQS R-120..R-124 |
| T-G01 | Gold | `src/patient_360/gold/patient_360.py` | `contracts/patient_360.yml` | `dq_rules/patient_360.yml` | `build_patient_360` | `silver/patient_dim`, `silver/encounter_fact`, `silver/observation_fact` | `s3://p360/gold/patient_360/` | STM §4.1 | DQS R-200..R-206 |

## 6. Performance & Optimization

Bronze tasks use 4 Spark executors, 4 GB each; silver uses 8×8 GB; gold uses
6×6 GB. Wide joins in silver are broadcast-hinted on `patient_dim` (< 200 MB).
Parquet/Delta files are compacted weekly via a `scripts/compact_tables.py` job
in `scripts/`. All executor sizing is parameterized through the environment
YAML described in §7, not hard-coded in modules.

## 7. Configuration Schema

Config lives at `_infra/cd/config/<env>.yaml` (one file per env: `dev.yaml`,
`stage.yaml`, `prod.yaml`). The rendered template is checked in by the
scaffold; the generate-config-template skill emits a candidate file the
developer drops in at that path.

Top-level keys:
- `env` (string) — `dev | stage | prod`
- `spark` — `{ executors, executor_memory, driver_memory }`
- `io` — `{ bronze_root, silver_root, gold_root }`
- `dq` — `{ fail_fast: bool, rules_path: "dq_rules/" }`
- `airflow` — `{ schedule, retries, max_active_runs }`

## 8. Error Handling

All tasks wrap their Spark action in `utils/dq.py::run_with_contract(table)`,
which loads the contract from `contracts/<table>.yml`, invokes
Spark-Expectations against `dq_rules/<table>.yml`, and raises if
`error_drop_threshold` is exceeded. Airflow retries twice with exponential
backoff; a third failure pages the oncall.

## 9. Deployment

### 9.1 `_infra/ci/` — Continuous Integration

`_infra/ci/github-actions.yaml` runs `ruff check`, `pytest`, and contract/DQ
validation on every PR. The workflow calls `make lint` and `make test` from the
project root and `make validate` (contracts + DQ rules).

### 9.2 `_infra/cd/` — Continuous Deployment

`_infra/cd/deploy.yaml` promotes an image tag across environments using the
per-env YAML under `_infra/cd/config/`. DAG files under `airflow/dags/` and
configs under `airflow/configs/` are synced to the Airflow bucket in the same
deploy.

### 9.3 `_infra/docker/` — Container Images

One image per layer:
- `_infra/docker/Dockerfile.bronze`
- `_infra/docker/Dockerfile.silver`
- `_infra/docker/Dockerfile.gold`

Each image installs the `patient_360` wheel plus layer-specific Python extras.

### 9.4 `ddl/liquibase/` — Schema Migrations

`ddl/liquibase/master.xml` includes the per-table changelogs
(`changelogs/patients.xml`, `changelogs/encounters.xml`, etc.). CD applies
migrations against the env database before DAG unpause.

## 10. Monitoring

- Spark-Expectations emits run metrics to the `dq_stats` Delta table; gold DAG
  post-task publishes a Grafana-visible counter.
- Airflow SLA misses route to the `#data-oncall` Slack channel via the existing
  callback in `utils/spark_session.py`.

## 11. Upstream Artifact References

| Upstream | Path | Used In |
|---|---|---|
| DRD | `outputs/drd/v1/DRD-2026-03-10-patient-360.md` | §1, §8 |
| HLD | `outputs/hld/v1/HLD-2026-03-12-patient-360.md` | §2, §9 |
| DMS | `outputs/dms/v1/DMS-2026-03-15-patient-360.md` | §2.2, §5 |
| STM | `outputs/stm/v1/STM-2026-03-18-patient-360.xlsx` | §5 (Transform Ref) |
| DQS | `outputs/dqs/v1/DQS-2026-03-20-patient-360.md` | §5 (DQ Check), §8 |

## 12. Traceability Matrix

| DRD Req | DMS Entity | STM Row | DQS Rule | LLD Task | Module Path |
|---|---|---|---|---|---|
| DRD-R-001 | Patient | STM §2.1 | R-001..R-004 | T-B01 | `src/patient_360/bronze/patients.py` |
| DRD-R-002 | Encounter | STM §2.2 | R-010..R-014 | T-B02 | `src/patient_360/bronze/encounters.py` |
| DRD-R-010 | PatientDim | STM §3.1 | R-101..R-105 | T-S01 | `src/patient_360/silver/patient_dim.py` |
| DRD-R-020 | Patient360 | STM §4.1 | R-200..R-206 | T-G01 | `src/patient_360/gold/patient_360.py` |

## 13. Decision Log

| ID | Date | Decision | Rationale |
|---|---|---|---|
| D-001 | 2026-04-17 | Adopted cookiecutter-chapter scaffold at `inputs/lld/v1/templates/cookiecutter-chapter/` as the target project layout for chapter-5 implementation. | Keeps LLD paths in lock-step with what developers will scaffold; avoids drift between design and code. |
| D-002 | 2026-04-17 | Silver layer uses Delta instead of Parquet for `patient_dim` and `encounter_fact`. | Enables upserts from late-arriving source rows; no scaffold deviation needed. |

_No scaffold deviations recorded. Any future path outside the cookiecutter tree must be logged here with rationale._

## 14. Version History

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-04-17 | Data Engineering Team | Initial draft aligned to cookiecutter-chapter scaffold. |
