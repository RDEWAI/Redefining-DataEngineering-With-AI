# Implementation Sequence: Patient 360 Medallion Pipeline

| Field | Value |
|-------|-------|
| **Derived From** | sample-lld.md |
| **Generated** | 2026-04-17 |
| **Generator** | generate_impl_sequence.py |
| **Target Scaffold** | cookiecutter-chapter (`inputs/lld/v1/templates/cookiecutter-chapter/`) |
| **Project Name** | patient_360 |

---

## 1. Build Phases

### Phase 1: Foundation
**Prerequisites**: Development environment setup; cookiecutter scaffold rendered.
**Modules**:
- `src/patient_360/utils/spark_session.py` — SparkSession factory
- `src/patient_360/utils/contracts.py` — Contract loader (reads `contracts/*.yml`)
- `src/patient_360/utils/dq.py` — Spark-Expectations wrapper (reads `dq_rules/*.yml`)
**Milestone**: Config loads, SparkSession creates in DEV, contract loader reads `contracts/patients.yml`.

### Phase 2: Schema Migrations
**Prerequisites**: Phase 1 complete.
**Modules**:
- `ddl/liquibase/master.xml`
- `ddl/liquibase/changelogs/patients.xml`
- `ddl/liquibase/changelogs/encounters.xml`
- `ddl/liquibase/changelogs/observations.xml`
**Milestone**: `liquibase update` succeeds against DEV; bronze tables exist with expected columns.

### Phase 3: Bronze Layer
**Prerequisites**: Phase 2 complete, DQ rule files in place.
**Modules**:
- `src/patient_360/bronze/patients.py`
- `src/patient_360/bronze/encounters.py`
- `src/patient_360/bronze/observations.py`
**Milestone**: All source tables land in Bronze; Spark-Expectations passes each contract.

### Phase 4: Silver Layer
**Prerequisites**: Phase 3 complete, bronze DQ gate passing.
**Modules**:
- `src/patient_360/silver/patient_dim.py` — SCD Type 2
- `src/patient_360/silver/encounter_fact.py`
- `src/patient_360/silver/observation_fact.py`
**Milestone**: Silver tables populated, referential integrity to `patient_dim` verified.

### Phase 5: Gold Layer
**Prerequisites**: Phase 4 complete, silver DQ gate passing.
**Modules**:
- `src/patient_360/gold/patient_360.py`
- `src/patient_360/gold/readmission_risk.py`
**Milestone**: Gold marts queryable, SLA targets met.

### Phase 6: Orchestration & Deployment
**Prerequisites**: Phase 5 complete.
**Modules**:
- `airflow/dags/patient_360_bronze.py`
- `airflow/dags/patient_360_silver.py`
- `airflow/dags/patient_360_gold.py`
- `airflow/configs/patient_360_{bronze,silver,gold}.yaml`
- `_infra/ci/github-actions.yaml`
- `_infra/cd/deploy.yaml`
- `_infra/cd/config/{dev,stage,prod}.yaml`
- `_infra/docker/Dockerfile.{bronze,silver,gold}`
**Milestone**: DAG runs end-to-end in DEV; CI/CD pipeline green on a trial PR.

---

## 2. Module Build Order

| # | Module | Layer | Description | LLD Section |
|---|--------|-------|-------------|-------------|
| 1 | `src/patient_360/utils/spark_session.py` | Foundation | SparkSession factory | §2.1 |
| 2 | `src/patient_360/utils/contracts.py` | Foundation | Contract loader | §2.1 |
| 3 | `src/patient_360/utils/dq.py` | Foundation | Spark-Expectations wrapper | §2.1 |
| 4 | `src/patient_360/bronze/patients.py` | Bronze | Raw → parquet ingestion | §2.1 |
| 5 | `src/patient_360/bronze/encounters.py` | Bronze | Raw → parquet ingestion | §2.1 |
| 6 | `src/patient_360/bronze/observations.py` | Bronze | Raw → parquet ingestion | §2.1 |
| 7 | `src/patient_360/silver/patient_dim.py` | Silver | SCD2 dimension | §2.1 |
| 8 | `src/patient_360/silver/encounter_fact.py` | Silver | Fact from bronze encounters | §2.1 |
| 9 | `src/patient_360/silver/observation_fact.py` | Silver | Fact from bronze observations | §2.1 |
| 10 | `src/patient_360/gold/patient_360.py` | Gold | Patient 360 mart | §2.1 |
| 11 | `src/patient_360/gold/readmission_risk.py` | Gold | Readmission risk mart | §2.1 |
| 12 | `airflow/dags/patient_360_bronze.py` | Orchestration | Bronze DAG | §4 |
| 13 | `airflow/dags/patient_360_silver.py` | Orchestration | Silver DAG | §4 |
| 14 | `airflow/dags/patient_360_gold.py` | Orchestration | Gold DAG | §4 |

---

## 3. Milestones & Checkpoints

| Milestone | Phase | Acceptance Criteria |
|-----------|-------|---------------------|
| Foundation complete | Phase 1 | Contract loader reads `contracts/patients.yml` in DEV |
| Schema migrations applied | Phase 2 | `liquibase update` succeeds; bronze tables exist |
| Bronze Layer complete | Phase 3 | All 3 bronze tables populated; DQ checks pass |
| Silver Layer complete | Phase 4 | Silver dims/facts populated; RI to patient_dim verified |
| Gold Layer complete | Phase 5 | Gold marts queryable under SLA |
| End-to-end in DEV | Phase 6 | 3 DAGs run, CI/CD pipeline green |
