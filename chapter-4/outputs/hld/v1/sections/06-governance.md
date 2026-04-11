## 6. Governance

### 6.1 Data Sensitivity & Classification

| Classification | Examples | Handling Strategy |
|---------------|----------|-------------------|
| PHI - Confidential | Patient name, DOB, SSN, address [DRD SS7.2] | SSN masked to last 4 digits in all layers [DRD SS3.5]; encryption at rest deferred to Phase 2; role-based access at application layer |
| PHI - Clinical | Conditions, medications, allergies, observations [DRD SS7.2] | Clinical role access only [DRD SS5.5]; allergy severity never suppressed -- NULL displayed as "Unknown" [DRD SS5.1, SS5.4] |
| PHI - Safety Critical | Allergies [DRD SS7.2] | Prominent display in all clinical views; zero tolerance for missed alerts [DRD SS1.3]; not suppressible regardless of NULL severity |
| Financial | Claims, encounter costs, total_visit_cost [DRD SS7.2] | Billing role only [DRD SS5.5]; hidden from clinical and administrative Gold tables |
| Internal | Reference data (organizations, providers, payers) | Standard access controls; no PHI restrictions |

### 6.2 Access Strategy (IAM)

| Role Group | Layer Access | Restrictions | Phase |
|-----------|-------------|-------------|-------|
| Physicians (120) | Gold READ | Full clinical; masked SSN; full address [DRD SS3.5]; no cost columns [DRD SS5.5] | Phase 1 (app-layer masking) |
| Nurses (200) | Gold READ | Full clinical; masked SSN; city/state only [DRD SS3.5]; no cost columns [DRD SS5.5] | Phase 1 (app-layer masking) |
| Care Coordinators (30) | Gold READ | Panel patients; masked SSN; city/state only [DRD SS3.5]; no cost columns [DRD SS5.5] | Phase 1 (app-layer masking) |
| Billing Staff (50) | Gold READ | Demographics + financial only; no clinical notes [DRD SS5.5, SS7.4] | Phase 1 (app-layer masking) |
| Department Heads (15) | Gold READ | Aggregates only; no individual PHI in reports [DRD SS7.4] | Phase 1 (app-layer masking) |
| Data Engineers | All layers READ/WRITE | Pipeline operations via service account | Phase 1 |
| Full RBAC + SSO + MFA | All layers | Column-level enforcement via UC ACLs [DRD SS7.4] | Phase 2 |

### 6.3 Data Quality Strategy

Data quality uses a **dual-layer approach**: SDP built-in `@dp.expect*` decorators for inline checks, plus Spark Expectations [technology-catalog.md SS5] YAML rules for complex validations. This avoids duplicating DQ config in the ingestion YAML -- SE rules are already generated from the DQS as separate per-table YAML files.

#### DQ Responsibility Split

| Check Type | Tool | Rationale |
|-----------|------|-----------|
| Schema validation (column presence, data types) | SDP `@dp.expect` | Inline within pipeline definition; zero external dependency; immediate feedback |
| Not-null checks on identity fields | SDP `@dp.expect` | Simple row-level assertions natural in SDP decorators |
| Valid range checks (dates, numeric bounds) | SDP `@dp.expect` | Row-level assertions; SDP captures violations in event log |
| Referential integrity (FK checks) | Spark Expectations | Cross-table validation requires SQL query-based rules (`query_dq`); not expressible as inline SDP expectations |
| Null tolerance thresholds (e.g., 60% ceiling for allergy severity) | Spark Expectations | Aggregate rules (`agg_dq`) with threshold logic; requires SE's action framework (fail/drop/ignore) |
| Business rule validation (calculated_age >= 0, total_visit_cost >= 0) | Spark Expectations | Complex business rules benefit from YAML-defined, version-controlled rule definitions with rejection reasons |
| Gold completeness assertions (all 5,767 patients present) | Spark Expectations | Aggregate assertion (`agg_dq`) with `action_if_failed: fail` |

#### Gate Definitions

**Bronze gate**: SDP `@dp.expect` decorators enforce schema validation (all expected columns present, data types match StructType definition) and not-null checks on identity fields (patient `id`). SE YAML rules enforce valid range checks on dates (no future dates for birthdate, encounter start/stop) [DRD SS3.2]. Actions: `fail` for identity fields, `drop` for invalid date ranges, `ignore` (log only) for optional fields [DRD SS3.1].

**Silver gate**: Spark Expectations YAML rules enforce referential integrity (FK checks per DRD [SS3.3] -- encounters.patient must exist in patients.id, conditions.encounter must exist in encounters.id, etc.). Null tolerance enforcement per DRD [SS3.4]: 0% for patient name/DOB, 0% for allergy description, 60% ceiling for allergy severity. Business rule validation on derived fields (calculated_age >= 0, total_visit_cost >= 0). Actions: `drop` for RI violations, `fail` if null tolerance thresholds exceeded.

**Gold gate**: Column-level assertions on consumer-facing fields: `patient_id NOT NULL`, `full_name NOT NULL`, allergy arrays never suppressed (allergies with NULL severity displayed as "Unknown") [DRD SS5.4]. Aggregate assertion: all 5,767 patients present in patient_summary [DRD SS4.3 -- 100% data completeness SLA].

### 6.4 Compliance Requirements

HIPAA compliance architecture is a separate workstream per DRD [SS6.1 Assumptions]. Phase 1 focuses on data consolidation with application-layer masking [DRD SS3.5 Note]. The following HIPAA technical safeguards are planned:

- **Access logging**: Log all patient record access with user ID, timestamp, patient ID, and action type [DRD SS7.5] -- implemented via OpenLineage events in Phase 1, extended to application-layer audit logs in Phase 2
- **Encryption at rest**: AES-256 for Delta tables -- deferred to Phase 2 when production environment is selected
- **Encryption in transit**: TLS 1.3 for all service communication -- deferred to Phase 2
- **Retention**: 6-year minimum for patient records [DRD SS7.3]; 7-year for billing/claims; audit logs archived to cold storage after 6 years
- **Breach detection**: Anomalous access pattern alerting -- deferred to Phase 2 [DRD SS7.5]

> Column-level masking rules, specific authentication methods, and encryption key management details belong in the **Low-Level Design (LLD)** document.

---
