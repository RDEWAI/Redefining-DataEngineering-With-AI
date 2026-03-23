# Implementation Sequence: Patient 360 Medallion Pipeline

| Field | Value |
|-------|-------|
| **Derived From** | LLD-2026-03-23-patient-360.md |
| **Generated** | 2026-03-23 |
| **Generator** | generate_impl_sequence.py |

---

## 1. Build Phases

### Phase 1: Foundation
**Prerequisites**: Development environment setup
**Modules**:
- `src/config/settings.py` — Pydantic config model
- `src/config/spark_session.py` — SparkSession factory
- `src/utils/logging.py` — Structured JSON logging
- `src/utils/metrics.py` — OpenTelemetry metric emission
**Milestone**: Config loads successfully, SparkSession creates in DEV

### Phase 2: Shared Transforms & Quality
**Prerequisites**: Phase 1 (Foundation) complete
**Modules**:
- `src/transforms/scd2.py` — Delta MERGE INTO SCD2 logic
- `src/transforms/derived_fields.py` — Calculated fields
- `src/quality/se_runner.py` — Spark-Expectations wrapper
**Milestone**: Unit tests pass for all transform and quality functions

### Phase 3: Bronze Layer
**Prerequisites**: Phase 2 (Shared Transforms) complete
**Modules**:
- `src/pipelines/bronze/ingest_patients.py`
- `src/pipelines/bronze/ingest_encounters.py`
**Milestone**: All source tables land in Bronze Delta, SE DQ checks pass

### Phase 4: Silver Layer
**Prerequisites**: Phase 3 (Bronze Layer) complete, DQ gate passing
**Modules**:
- `src/pipelines/silver/transform_patients.py` — SCD Type 2
- `src/pipelines/silver/transform_encounters.py`
**Milestone**: All Silver tables populated, SCD2 applied

### Phase 5: Gold Layer
**Prerequisites**: Phase 4 (Silver Layer) complete, DQ gate passing
**Modules**:
- `src/pipelines/gold/build_patient_summary.py`
**Milestone**: Gold tables queryable, SLA targets met

### Phase 6: Orchestration & Deployment
**Prerequisites**: Phase 5 (Gold Layer) complete
**Modules**:
- `dags/patient360_daily_v1.py` — Airflow DAG
**Milestone**: DAG runs end-to-end in DEV

---

## 2. Module Build Order

| # | Module | Layer | Description | LLD Section |
|---|--------|-------|-------------|-------------|
| 1 | `src/config/settings.py` | Foundation | Pydantic config model | §2.1 |
| 2 | `src/config/spark_session.py` | Foundation | SparkSession factory | §2.1 |
| 3 | `src/transforms/scd2.py` | Shared | Delta MERGE INTO SCD2 | §2.1 |
| 4 | `src/pipelines/bronze/ingest_patients.py` | Bronze | | §2.1 |
| 5 | `src/pipelines/silver/transform_patients.py` | Silver | SCD Type 2 | §2.1 |
| 6 | `src/pipelines/gold/build_patient_summary.py` | Gold | | §2.1 |

---

## 3. Milestones & Checkpoints

| Milestone | Phase | Acceptance Criteria |
|-----------|-------|---------------------|
| Foundation complete | Phase 1 | Config loads, SparkSession creates |
| Bronze Layer complete | Phase 3 | All 13 tables in Delta |
| Gold Layer complete | Phase 5 | Gold tables queryable |
| End-to-end in DEV | Phase 6 | DAG completes successfully |
