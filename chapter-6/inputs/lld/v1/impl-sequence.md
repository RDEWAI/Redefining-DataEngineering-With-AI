# Implementation Sequence: Low-Level Design: Patient 360 Medallion Pipeline

| Field | Value |
|-------|-------|
| **Derived From** | LLD-2026-04-17-patient-360.md |
| **Generated** | 2026-04-17 |
| **Generator** | generate_impl_sequence.py |

---

## 1. Build Phases

### Phase 1: Foundation
**Prerequisites**: Development environment setup
**Modules**:
- `chapter-5/src/utils/__init__.py` — cross-layer utilities (logging, metrics, delta_helpers)
**Milestone**: Config loads successfully, SparkSession creates in DEV

### Phase 3: Bronze Layer
**Prerequisites**: Phase 2 (Shared Transforms) complete
**Modules**:
- `chapter-5/tests/bronze/__init__.py`
**Milestone**: All source tables land in Bronze Delta, SE DQ checks pass

### Phase 4: Silver Layer
**Prerequisites**: Phase 3 (Bronze Layer) complete, DQ gate passing
**Modules**:
- `chapter-5/src/silver/__init__.py` — 1 module per target Silver table (13)
- `chapter-5/tests/silver/__init__.py`
**Milestone**: All Silver tables populated, SCD2 applied, referential integrity verified

### Phase 5: Gold Layer
**Prerequisites**: Phase 4 (Silver Layer) complete, DQ gate passing
**Modules**:
- `chapter-5/src/gold/__init__.py` — 1 module per Gold consumer table (3)
- `chapter-5/tests/gold/__init__.py`
**Milestone**: Gold tables queryable, SLA targets met

### Phase 6: Orchestration & Deployment
**Prerequisites**: Phase 5 (Gold Layer) complete
**Modules**:
- `chapter-5/airflow/dags/__init__.py` — patient360_hourly_v1.py lives here
**Milestone**: DAG runs end-to-end in DEV, CI/CD pipeline functional

---

## 2. Module Build Order

| # | Module | Layer | Description | LLD Section |
|---|--------|-------|-------------|-------------|
| 1 | `chapter-5/src/silver/__init__.py` | Silver | 1 module per target Silver table (13) | §2.1 |
| 2 | `chapter-5/src/gold/__init__.py` | Gold | 1 module per Gold consumer table (3) | §2.1 |
| 3 | `chapter-5/src/utils/__init__.py` | Foundation | cross-layer utilities (logging, metrics, delta_helpers) | §2.1 |
| 4 | `chapter-5/tests/conftest.py` | Other |  | §2.1 |
| 5 | `chapter-5/tests/bronze/__init__.py` | Bronze |  | §2.1 |
| 6 | `chapter-5/tests/silver/__init__.py` | Silver |  | §2.1 |
| 7 | `chapter-5/tests/gold/__init__.py` | Gold |  | §2.1 |
| 8 | `chapter-5/airflow/dags/__init__.py` | Orchestration | patient360_hourly_v1.py lives here | §2.1 |

---

## 3. Milestones & Checkpoints

| Milestone | Phase | Acceptance Criteria |
|-----------|-------|---------------------|
| Foundation complete | Phase 1 | Config loads successfully, SparkSession creates in DEV |
| Bronze Layer complete | Phase 3 | All source tables land in Bronze Delta, SE DQ checks pass |
| Silver Layer complete | Phase 4 | All Silver tables populated, SCD2 applied, referential integrity verified |
| Gold Layer complete | Phase 5 | Gold tables queryable, SLA targets met |
| Orchestration & Deployment complete | Phase 6 | DAG runs end-to-end in DEV, CI/CD pipeline functional |

---

## 4. Traceability

Requirements mapped to build phases (from LLD §12):

| Requirement | Source | Implementation | LLD Section |
|-------------|--------|----------------|-------------|
| FR-1: Unified patient search | DRD §1.1 | `build_patient_summary_gold` task; Gold `patient_summary` table | §5.3 |
| FR-2: Full encounter/clinical history | DRD §4.2 | `build_clinical_history_gold` task; Gold `patient_clinical_history` table | §5.3 |
| FR-3: Billing summary (isolated) | DRD §5.5 | `build_billing_summary_gold` task; Gold `patient_billing_summary` table (separate from clinical) | §5.3 |
| FR-4: Ingest 13 Phase 1 tables | DRD §2.2 | 13 Bronze ingestion tasks running in parallel | §5.1 |
| FR-5: Track demographic changes (SCD2) | DRD §1.2 | `transform_patients_silver` with SCD Type 2 via Delta MERGE INTO | §5.2 |
| FR-6: Derived fields | DRD §5.2 | `src/patient_360/utils/derived_fields.py` in Silver tasks | §2.1 |
| FR-7: Referential integrity | DRD §3.3 | `dq_gate_silver` with FK checks from DQS §3 | §5.4 |
| FR-8: Allergy never suppressed | DRD §5.4 | Gold DQ assertion DQ-FLD-138 (cross-field), allergy elevated alerting | §5.3, §8.3 |
| FR-9: Default values (NULL costs=0) | DRD §5.1 | Silver transformations per STM Tab:Null Handling | §5.2 |
| FR-10: Data lineage | DRD §7.5 | `emit_lineage` task; OpenLineage events to Marquez | §4.2 |
| NFR-1: < 2s query response |  | Gold denormalization with ARRAY<STRUCT>; Delta columnar reads | §5.3, §6.2 |
| NFR-2: <= 1 hour data freshness |  | Hourly Airflow schedule `0 * * * *`; ~33 min critical path | §4.1, §4.4 |
| NFR-3: <= 24 hour billing freshness |  | Hourly schedule exceeds daily SLA | §4.1 |
| NFR-4: 100% patient completeness |  | DQ assertion DQ-FLD-106 + reconciliation check | §5.4 |
| NFR-5: Pipeline idempotency |  | `replaceWhere ds` for Bronze/Silver facts; MERGE INTO for SCD2; full overwrite for Gold | §4.5 |
| NFR-6: §N masking |  | PHI columns (SSN, DRIVERS, PASSPORT) dropped at Silver boundary per DMS §3 | §5.2 |
| NFR-7: HIPAA audit trail |  | OpenLineage job-level lineage to Marquez | §4.2 |
| NFR-8: 6-year patient retention |  | Gold retention = 7 years | §3.4 |
| NFR-9: 7-year claims retention |  | Gold retention = 7 years | §3.4 |
| NFR-10: RTO <= 4 hours |  | Delta RESTORE (instant) + pipeline re-run | §9.3 |
