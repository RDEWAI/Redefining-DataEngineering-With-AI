"""Shared fixtures for DRD and HLD validator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

VALID_DRD = """\
# Data Requirements Document: Patient 360 Search

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-01-29 |
| **Last Modified** | 2026-01-29 |
| **Author** | BA Agent |
| **Status** | Draft |
| **Business Sponsor** | Dr. Sarah Chen |

---

## Executive Summary

The Patient 360 initiative provides clinicians with a unified patient search.

---

## 1. Business Context

### 1.1 Business Request

Hospital leadership wants a single patient lookup interface.

### 1.2 Business Objectives

- Reduce lookup time to under 30 seconds

### 1.3 Success Criteria

- 90% of searches complete within 2 seconds

### 1.4 Stakeholders

| Name | Role | Interest | Contact |
|------|------|----------|---------|
| Dr. Sarah Chen | CMO | Clinical quality | s.chen@hospital.org |

---

## 2. Source Discovery

### 2.1 Source Systems

#### Synthea EHR

- **System Type**: DuckDB
- **Owner**: Health IT
- **Access Method**: SQL
- **Connection Details**: data/duckdb/raw.db

### 2.2 Available Tables and Datasets

| Source System | Table/Dataset | Description | Estimated Row Count | Update Frequency |
|---------------|---------------|-------------|---------------------|------------------|
| Synthea EHR | patients | Demographics | 1,000 | Daily |
| Synthea EHR | encounters | Visit records | 50,000 | Real-time |

### 2.3 Data Volume Estimates

| Metric | Estimate | Notes |
|--------|----------|-------|
| Total patients | 1,000 | Synthea population |

### 2.4 Access and Security

- **Synthea EHR**: Read-only SQL access via DuckDB.

---

## 3. Data Quality Expectations

### 3.1 Critical Fields

| Field Name | Source Table | Why Critical | Allowed Null? | Expected Format |
|------------|-------------|--------------|---------------|-----------------|
| patient_id | patients | Primary key | No | UUID |
| last_name | patients | Search field | No | Text |

### 3.2 Valid Value Ranges

| Field Name | Valid Range / Allowed Values | Action if Out of Range |
|------------|------------------------------|------------------------|
| birthdate | 1900-01-01 to today | Reject record |

### 3.3 Referential Integrity Requirements

| Child Table | Child Field | Parent Table | Parent Field | Required? |
|-------------|-------------|--------------|--------------|-----------|
| encounters | patient_id | patients | id | Yes |

### 3.4 Tolerance Thresholds

| Quality Metric | Acceptable Threshold | Measurement Method |
|----------------|----------------------|--------------------|
| Missing patient_id | 0% | Count nulls |
| Duplicate patients | < 0.1% | Name+DOB match |

---

## 4. Consumer Requirements

### 4.1 Data Consumers

| Consumer | Department | Use Case | Access Pattern |
|----------|------------|----------|----------------|
| Physicians | Clinical | Patient lookup | Real-time, 50-100/day |
| Nurses | Clinical | Med verification | Real-time, 30-50/day |

### 4.2 Access Patterns

#### Physicians

- **Query Type**: Single patient by name
- **Frequency**: 50-100 per day
- **Typical Data Volume Requested**: 1 patient, 12 months history
- **Peak Usage Times**: 7-9 AM

### 4.3 Service Level Agreements (SLAs)

| SLA Metric | Target | Measurement | Escalation |
|------------|--------|-------------|------------|
| Response time | < 2 seconds | APM | Page on-call |
| Availability | 99.5% | Uptime monitor | Notify CIO |

### 4.4 Data Freshness Requirements

| Consumer / Use Case | Maximum Acceptable Latency | Refresh Cadence |
|---------------------|----------------------------|-----------------|
| Physician lookup | 1 hour | Near real-time |
| Allergy alerts | 15 minutes | Near real-time |

---

## 5. Business Rules

### 5.1 Default Values

| Field | Default Value | When Applied | Business Justification |
|-------|---------------|--------------|------------------------|
| encounter_status | Active | New encounter | Active until discharged |

### 5.2 Calculations and Derivations

#### Patient Age

- **Formula / Logic**: FLOOR(DATEDIFF('year', birthdate, CURRENT_DATE))
- **Input Fields**: patients.birthdate
- **Output Field**: patient_age (derived)
- **Business Purpose**: Display age on search results
- **Example**: Born 1985-03-15, today = 40 years old

### 5.3 Transformation Rules

- **Name standardization**: Convert to title case

### 5.4 Edge Cases and Exceptions

- **Scenario**: Patient has no encounters
  - **Expected Behavior**: Show "No encounter history found"
  - **Rationale**: New patients may have no local history

---

## 6. Assumptions and Open Questions

### 6.1 Assumptions

- All Synthea data tables are loaded in DuckDB

### 6.2 Open Questions

| # | Question | Assigned To | Due Date | Status |
|---|----------|-------------|----------|--------|
| 1 | Should lab results show full history? | Dr. Chen | 2026-02-15 | Open |

---

## 7. Regulatory and Compliance

### 7.1 Applicable Regulations

| Regulation | Scope | Key Requirements | Impact on Data Design |
|------------|-------|------------------|-----------------------|
| HIPAA | All patient data | PHI protection, minimum necessary | Encrypt at rest; RBAC |

### 7.2 Data Classification

| Data Element | Classification Level | Handling Requirements |
|-------------|---------------------|----------------------|
| Patient demographics | PHI - Confidential | Encrypted storage, access logging |
| Clinical records | PHI - Confidential | Encrypted, clinician-only access |

### 7.3 Retention Requirements

| Data Category | Retention Period | Deletion Method | Legal Basis |
|--------------|-----------------|-----------------|-------------|
| Medical records | 7 years minimum | Secure deletion with audit trail | State law |

### 7.4 Access Controls

| Role / Group | Data Access Level | Restrictions | Authentication |
|-------------|-------------------|--------------|----------------|
| Physicians | Full clinical read | No billing detail | SSO + MFA |
| Billing Staff | Financial + demographics | No clinical notes | SSO + MFA |

### 7.5 Audit Requirements

- **Access logging**: Log every patient data access with user ID, timestamp, and data accessed
- **Modification tracking**: Track all data changes with before/after values

---

## 8. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | BA Agent | Initial creation |

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Business Sponsor | Dr. Sarah Chen | _Pending_ | |
"""

MINIMAL_INVALID_DRD = """\
# Data Requirements Document: Incomplete

## Executive Summary

This DRD is intentionally incomplete for testing.

## 1. Business Context

Some context here.
"""

EMPTY_SECTIONS_DRD = """\
# Data Requirements Document: Empty Sections

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-01-29 |
| **Author** | Test |
| **Status** | Draft |

## Executive Summary

Test summary.

## 1. Business Context

### 1.1 Business Request

Test request.

## 2. Source Discovery

### 2.1 Source Systems

## 3. Data Quality Expectations

## 4. Consumer Requirements

## 5. Business Rules

## 6. Assumptions and Open Questions

## 7. Regulatory and Compliance

## 8. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-01-29 | Test | Initial |
"""

PLACEHOLDER_DRD = """\
# Data Requirements Document: Placeholder Test

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-01-29 |
| **Author** | Test |
| **Status** | Draft |

## Executive Summary

[TO BE DETERMINED - requires input from stakeholders]

## 1. Business Context

### 1.1 Business Request

[TBD]

### 1.4 Stakeholders

[NEEDS VERIFICATION]

## 2. Source Discovery

### 2.1 Source Systems

#### Test System

- **System Type**: Database
- **Owner**: IT
- **Access Method**: SQL
- **Connection Details**: localhost

### 2.2 Available Tables and Datasets

| Source | Table | Description | Rows | Frequency |
|-------|-------|-------------|------|-----------|
| Test | users | User data | 100 | Daily |

### 2.3 Data Volume Estimates

| Metric | Estimate | Notes |
|--------|----------|-------|
| Total | 100 | Test |

### 2.4 Access and Security

- **Test System**: SQL access

## 3. Data Quality Expectations

### 3.1 Critical Fields

| Field | Source | Why Critical | Nullable | Format |
|-------|--------|--------------|----------|--------|
| id | users | Primary key | No | INT |

### 3.2 Valid Value Ranges

| Field | Range | Action |
|-------|-------|--------|
| age | 0-150 | Reject |

### 3.3 Referential Integrity Requirements

| Child | Child Field | Parent | Parent Field | Required |
|-------|-------------|--------|--------------|----------|
| orders | user_id | users | id | Yes |

### 3.4 Tolerance Thresholds

| Metric | Threshold | Method |
|--------|-----------|--------|
| Nulls | 0% | Count |

## 4. Consumer Requirements

### 4.1 Data Consumers

| Consumer | Dept | Use Case | Access |
|----------|------|----------|--------|
| Analysts | BI | Reports | Daily |

### 4.2 Access Patterns

Content here.

### 4.3 Service Level Agreements (SLAs)

| Metric | Target | Measurement | Escalation |
|--------|--------|-------------|------------|
| Uptime | 99% | Monitor | Alert |

### 4.4 Data Freshness Requirements

| Consumer | Latency | Cadence |
|----------|---------|---------|
| Analysts | 24h | Daily |

## 5. Business Rules

### 5.1 Default Values

| Field | Default | When | Justification |
|-------|---------|------|---------------|
| status | active | New record | Default state |

### 5.2 Calculations and Derivations

#### User tenure

- **Formula / Logic**: DATEDIFF(created_at, CURRENT_DATE)
- **Input Fields**: users.created_at
- **Output Field**: tenure_days
- **Business Purpose**: Track user age
- **Example**: Created Jan 1, today Jan 29 = 28 days

### 5.3 Transformation Rules

- **Lowercase emails**: Normalize to lowercase

### 5.4 Edge Cases and Exceptions

- **Scenario**: User has no orders
  - **Expected Behavior**: Show empty state
  - **Rationale**: New users may not have ordered

## 6. Assumptions and Open Questions

### 6.1 Assumptions

- Database is available

### 6.2 Open Questions

| # | Question | Assigned To | Due Date | Status |
|---|----------|-------------|----------|--------|
| 1 | Retention policy? | Legal | 2026-03-01 | Open |

## 7. Regulatory and Compliance

### 7.1 Applicable Regulations

| Regulation | Scope | Key Requirements | Impact on Data Design |
|------------|-------|------------------|-----------------------|
| HIPAA | All patient data | PHI protection | Encrypt at rest and in transit |

### 7.2 Data Classification

| Data Element | Classification Level | Handling Requirements |
|-------------|---------------------|----------------------|
| Patient data | PHI | Encrypted storage |

### 7.3 Retention Requirements

| Data Category | Retention Period | Deletion Method | Legal Basis |
|--------------|-----------------|-----------------|-------------|
| Medical records | 7 years | Secure deletion | State law |

### 7.4 Access Controls

| Role / Group | Data Access Level | Restrictions | Authentication |
|-------------|-------------------|--------------|----------------|
| Physicians | Full clinical | No billing | SSO |

### 7.5 Audit Requirements

- **Access logging**: Log all data access events

## 8. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-01-29 | Test | Initial |

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
"""


VALID_HLD = """\
# High-Level Design: Patient 360 Medallion Pipeline

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-03-14 |
| **Last Modified** | 2026-03-14 |
| **Author** | Architect Agent |
| **Status** | Draft |
| **DRD Reference** | DRD-2026-02-11-patient-360-v1.md |

---

## 1. Executive Summary

The Patient 360 pipeline consolidates 18 Synthea healthcare source tables into
a unified patient view serving 400+ clinical and billing users. The architecture
uses a Medallion pattern (Bronze/Silver/Gold) with Delta Lake for ACID guarantees
and SCD Type 2 tracking on patient dimensions. This design satisfies the DRD's
1-hour clinical latency SLA while keeping implementation within the team's
demonstrated proficiency in batch Spark pipelines.

---

## 2. Architecture Overview

### Selected Pattern

**Pattern**: Medallion (Lakehouse) Architecture

**Justification**: The DRD specifies mixed latency requirements
(sub-hour for clinical data per DRD Section 4.4, daily for analytics).
The source data is structured and batch-accessible (DRD Section 2.1).
HIPAA compliance requires immutable audit trail (DRD Section 7.1),
which the bronze layer provides because raw data is never modified.

**Options Considered**:
- Medallion: Selected (rationale above)
- Lambda: Rejected — no genuine dual-path need
- Kappa: Rejected — source is batch, not streaming
- Data Vault: Rejected — single source system

**Trade-off**: Medallion batch cannot achieve sub-minute data freshness.
Hourly batch is the Phase 1 compromise for medications and allergies.

```mermaid
flowchart TB
    subgraph Consumers["Consumer Groups"]
        clinical["Clinical Users\\n350 users"]
    end
    subgraph Platform["Patient 360 Data Platform"]
        pipeline["Medallion Pipeline\\nBronze/Silver/Gold"]
    end
    subgraph External["External Systems"]
        ehr["Healthcare EHR\\n18 CSV tables"]
    end
    ehr -->|"Full Snapshot CDC"| pipeline
    pipeline -->|"Gold tables"| clinical
```

```mermaid
flowchart TB
    EHR["EHR"] --> BRZ["Bronze"] --> SLV["Silver"] --> GLD["Gold"]
    GLD --> CLIN["Clinical"] & BILL["Billing"]
```

```mermaid
sequenceDiagram
  participant EHR as Healthcare EHR
  participant BRZ as Bronze Layer
  participant SLV as Silver Layer
  EHR->>BRZ: Full snapshot CSV extract
  BRZ->>SLV: Type casting, SCD2 merge
```

### Key Design Principles

- **Idempotency**: All layers partition by `ds`; re-running replaces that partition only
- **Schema enforcement**: Explicit schemas at ingestion; no schema inference
- **Traceability**: OpenLineage events emitted at every layer transition
- **Separation of concerns**: Bronze = raw; Silver = conformed; Gold = consumer-ready

---

## 3. Data Architecture

### Layer Strategy

**Bronze Layer**: Preserves source data exactly as received. No transformations
beyond type casting, schema enforcement, and partition tagging. Serves as the
immutable audit record.

**Silver Layer**: Applies SCD Type 2 to dimension tables for historical tracking.
Normalizes data types, enforces referential integrity, and computes derived fields
(calculated_age, medication_status, is_30_day_readmission). Fact tables use
insert-only pattern.

**Gold Layer**: Produces denormalized, consumer-specific aggregations. One row per
current patient for patient_summary. Optimized for sub-2-second query response
per DRD Section 4.3 SLA.

> Detailed table inventories, column schemas, and row-level write strategies are
> documented in the **Data Model Specification (DMS)**.

### Data Domain Map

Clinical domain (patients, encounters, conditions, medications, observations,
allergies, immunizations, procedures, careplans) flows through all three layers.
Reference domain (organizations, providers, payers) lands in Bronze and becomes
SCD2 dimensions in Silver. Financial domain (claims) flows Bronze → Silver →
Gold billing summary.

### SCD Strategy

| Dimension Type | SCD Approach | Rationale |
|----------------|-------------|-----------|
| Patient demographics | SCD Type 2 | Track address/name changes over time for clinical accuracy |
| Provider attributes | SCD Type 2 | Track specialty and organization changes |
| Payer information | SCD Type 2 | Track plan changes for billing accuracy |
| Reference data (orgs) | SCD Type 2 | Track organizational restructuring |

### Data Quality Strategy

Bronze: Schema validation and not-null checks on identity fields. Silver:
Referential integrity (FK checks), business rule validation, derived field
computation. Gold: Column-level assertions on consumer-facing fields
(patient_id NOT NULL, allergy array never suppressed).

---

## 4. Technology Decisions

| Component | Selected Tool | Why |
|-----------|--------------|-----|
| Processing Engine | Apache Spark (PySpark) | Team proficiency; handles 4.4M rows |
| Table Format | Delta Lake | ACID writes, time travel, MERGE INTO for SCD2; team proficient |
| Metastore | Unity Catalog OSS | Catalog/schema hierarchy, REST API for consumer access |
| Lineage | OpenLineage + Marquez | HIPAA audit trail requirement (DRD Section 7.5) |
| Data Quality | Spark Expectations | Rule-based DQ enforcement at each layer boundary |
| Language | Python | Team high proficiency; PySpark + pytest ecosystem |
| Orchestration | Make + scripts | Minimal overhead for local dev phase |

> Detailed technology versions, JAR coordinates, and deployment configurations
> belong in the **Low-Level Design (LLD)** document.

### Key Compatibility Constraints

- Spark 4.x requires Scala 2.13 JARs and Java 11 or 17 (not 21)
- UC OSS catalog name must be `spark_catalog` (Spark default)
- OpenLineage port remapped to 5001 due to macOS AirPlay conflict

---

## 5. Integration Architecture

### Source Systems

| Source | Type | Access Pattern | Tables Consumed |
|--------|------|---------------|-----------------|
| Synthea EHR | CSV (DuckDB) | File read + validation | All 18 tables [DRD §2.2] |

### Consumer Access Pattern

| Consumer Group | Access Method | Gold Tables | SLA |
|---------------|--------------|-------------|-----|
| Physicians (120) | Unity Catalog REST API | patient_summary, clinical_history | < 2s at p90 |
| Nurses (200) | Unity Catalog REST API | patient_summary, clinical_history | < 2s at p90 |
| Care Coordinators (30) | Unity Catalog REST API | patient_summary | < 2s at p90 |
| Billing Staff (50) | Unity Catalog REST API | patient_billing_summary | < 2s at p90 |

### Observability Strategy

Every pipeline job emits OpenLineage events to Marquez. Bronze-to-Silver-to-Gold
lineage graph is visible in the Marquez Web UI. Spark Expectations DQ results are
logged per layer.

---

## 6. Scalability & Capacity Model

### Current Scale

Total dataset: ~6.9M rows across 18 tables (~3.8 GB as Delta). Largest table:
observations at 4.4M rows. Patient count: 5,767.

### Growth Model

| Metric | Current | Year 1 | Year 3 | Assumption |
|--------|---------|--------|--------|------------|
| Patient count | 5,767 | ~6,000 | ~6,500 | ~200 new patients/year |
| Total rows | 6.9M | ~7.1M | ~7.6M | Linear growth with patients |
| Storage (Delta) | 3.8 GB | ~4.2 GB | ~5.0 GB | Delta compression ~30% vs CSV |
| Pipeline runtime | ~15 min | ~16 min | ~18 min | Linear growth with row count |

### Scaling Levers

- At 10x patient volume: move from local[*] to Spark cluster mode
- At 50 GB Delta: evaluate cloud object storage (S3/GCS/ADLS)
- Observations table: increase shuffle partitions if runtime exceeds 30 min

### Cost Model

Phase 1 is local dev with $0 infrastructure cost. Cloud migration cost scales
linearly with compute hours and storage volume. Estimated ~$200/month for
cloud deployment at current scale.

---

## 7. Security & Compliance

### Data Classification

| Classification | Examples | Handling Strategy |
|---------------|----------|-------------------|
| PHI - Confidential | Demographics, SSN, DOB | Encrypted at rest (Phase 2), RBAC |
| PHI - Clinical | Conditions, medications, allergies | Clinical role access only [DRD §5.5] |
| Financial | Claims, encounter costs | Billing role only per DRD Section 5.5 |
| Internal | Reference data (orgs, providers) | Standard access controls |

### Access Strategy

| Role Group | Layer Access | Restrictions | Phase |
|-----------|-------------|-------------|-------|
| Clinical users | Gold READ | No cost columns, masked SSN | Phase 1 |
| Billing staff | Gold READ | No clinical notes | Phase 1 |
| Data engineers | All layers WRITE | No restrictions | Phase 1 |
| Full RBAC + SSO | All layers | Column-level enforcement | Phase 2 |

### Compliance Requirements

HIPAA compliance is a separate workstream per DRD Section 6.1. Phase 1 focuses
on data consolidation with application-layer masking (SSN last 4, address
city/state only). Full HIPAA technical safeguards (encryption at rest, TLS,
audit logging) deferred to Phase 2.

---

## 8. Operational Considerations

### CDC Strategy

All source tables use Full Snapshot in Phase 1. The source database has no
reliable `updated_at` timestamps (verified via schema inspection), making
Timestamp Watermark unreliable. Log-Based CDC (Debezium) is out of scope
for the local Docker environment.

| Source Type | CDC Method | Frequency | Rationale |
|------------|-----------|-----------|-----------|
| Small tables (<10K rows) | Full Snapshot | Weekly | Static reference data; changes rare |
| Medium tables (10K-500K) | Full Snapshot | Daily | Daily batch satisfies DRD clinical 1hr SLA |
| Large tables (>500K rows) | Full Snapshot | Daily | Hourly batch for meds/allergies (Phase 1) |

### Recovery Strategy

| Metric | Target | Justification |
|--------|--------|---------------|
| RTO | 4 hours | Read-only system; rebuild from source CSVs |
| RPO | 24 hours (last batch) | Source EHR CSVs are authoritative |

### Backup Approach

Source CSVs are immutable and re-ingestible. Delta Lake time travel provides
7-day rollback. UC and Marquez metadata stored in named Docker volumes with
daily backup.

> Detailed recovery runbooks and per-table CDC configurations belong in the
> **Low-Level Design (LLD)** document.

---

## 9. Decision Log

### Decision 1: Architecture Pattern

**Options Considered**:
1. Medallion (Bronze/Silver/Gold) — batch pipeline, team high proficiency
2. Lambda Architecture — dual batch + streaming paths
3. Kappa Architecture — streaming-only with reprocessing
4. Data Vault — hub-satellite with surrogate keys

**Selected**: Medallion (Bronze/Silver/Gold)

**Rationale**: DRD requires 1-hour maximum latency for clinical users.
Team has demonstrated high proficiency in Medallion + Delta Lake.
No sub-minute requirement exists at the query level.

**Trade-off**: Cannot achieve sub-minute data freshness. Hourly batch
is the Phase 1 acceptable compromise.

### Decision 2: Storage Format

**Options Considered**:
1. Delta Lake — ACID, time travel, MERGE INTO
2. Apache Iceberg — multi-engine, no team experience
3. Apache Hudi — upsert-optimized, no team experience

**Selected**: Delta Lake

**Rationale**: Infrastructure constraints mandate Delta Lake. Team has
high proficiency in Delta MERGE INTO for SCD2.

**Trade-off**: Vendor lock-in to Databricks ecosystem. Acceptable for
local dev; Iceberg migration path exists for production.

---

## 10. Open Questions & Risks

### Open Questions

| # | Question | Owner | Due Date | Status |
|---|----------|-------|----------|--------|
| 1 | Cloud deployment timeline | CIO | 2026-04-01 | Open |
| 2 | Sub-minute CDC path for meds/allergies in Phase 2? | CIO | 2026-04-15 | Open |

### Key Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Observations exceeds local capacity | Pipeline failures | Low | Scale to cluster at 10x |
| HIPAA audit gaps in Phase 1 | Compliance gap | Medium | Phase 2 adds encryption + audit |

---

## 11. Appendix

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-14 | Architect Agent | Initial HLD |

### Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Technical Lead | _Pending_ | | |

### Related Documents

- **DRD**: DRD-2026-02-11-patient-360-v1.md
- **DMS**: Data Model Specification (downstream)
- **LLD**: Low-Level Design (downstream)
"""

MINIMAL_INVALID_HLD = """\
# High-Level Design: Incomplete

## 2. Architecture Overview

This HLD is intentionally incomplete for testing.
"""

EMPTY_SECTIONS_HLD = """\
# High-Level Design: Empty Sections

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-03-14 |
| **Author** | Test |
| **Status** | Draft |
| **DRD Reference** | DRD-test.md |

## 1. Executive Summary

Test summary.

## 2. Architecture Overview

Test overview.

## 3. Data Architecture

## 4. Technology Decisions

## 5. Integration Architecture

## 6. Scalability & Capacity Model

## 7. Security & Compliance

## 8. Operational Considerations
"""

PLACEHOLDER_HLD = """\
# High-Level Design: Placeholder Test

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-03-14 |
| **Author** | Test |
| **Status** | Draft |
| **DRD Reference** | DRD-test.md |

## 1. Executive Summary

[TO BE DETERMINED - requires input from architect]

This pipeline consolidates patient data. It uses a Medallion pattern.

## 2. Architecture Overview

Medallion architecture selected because DRD specifies mixed latency.
The trade-off is no sub-minute freshness.

```mermaid
flowchart LR
    SRC --> BRZ --> SLV --> GLD
```

## 3. Data Architecture

**Bronze Layer**: Raw ingestion of source tables.

**Silver Layer**: Cleansed and conformed data.

**Gold Layer**: Dimensional model.

> Detailed table inventories are in the **DMS**.

## 4. Technology Decisions

| Component | Selected Tool | Why |
|-----------|--------------|-----|
| Processing | Spark | Team proficiency |
| Storage | Delta Lake | ACID writes |
| Metastore | Unity Catalog | Catalog management |

## 5. Integration Architecture

Source: Synthea CSV via file-based ingestion.

## 6. Scalability & Capacity Model

Current volume: 5,767 patients, ~5M rows total.
Growth: 100K patients in 12 months.
Cost: $0 local, ~$200/month cloud.

## 7. Security & Compliance

HIPAA compliance required per DRD Section 7.1.
Data classification includes PHI and financial data.

## 8. Operational Considerations

Full snapshot for small tables. Timestamp-based for large tables.
Snapshot is acceptable because DRD projects <100K patients initially.
RTO: 2 hours. RPO: 6 hours.
"""


@pytest.fixture
def valid_hld_file(tmp_path: Path) -> Path:
    """Create a valid HLD file for testing."""
    f = tmp_path / "valid-hld.md"
    f.write_text(VALID_HLD, encoding="utf-8")
    return f


@pytest.fixture
def invalid_hld_file(tmp_path: Path) -> Path:
    """Create a minimal invalid HLD file for testing."""
    f = tmp_path / "invalid-hld.md"
    f.write_text(MINIMAL_INVALID_HLD, encoding="utf-8")
    return f


@pytest.fixture
def empty_hld_sections_file(tmp_path: Path) -> Path:
    """Create an HLD with empty required sections."""
    f = tmp_path / "empty-sections-hld.md"
    f.write_text(EMPTY_SECTIONS_HLD, encoding="utf-8")
    return f


@pytest.fixture
def placeholder_hld_file(tmp_path: Path) -> Path:
    """Create an HLD with placeholder text."""
    f = tmp_path / "placeholder-hld.md"
    f.write_text(PLACEHOLDER_HLD, encoding="utf-8")
    return f


@pytest.fixture
def valid_drd_file(tmp_path: Path) -> Path:
    """Create a valid DRD file for testing."""
    f = tmp_path / "valid-drd.md"
    f.write_text(VALID_DRD, encoding="utf-8")
    return f


@pytest.fixture
def invalid_drd_file(tmp_path: Path) -> Path:
    """Create a minimal invalid DRD file for testing."""
    f = tmp_path / "invalid-drd.md"
    f.write_text(MINIMAL_INVALID_DRD, encoding="utf-8")
    return f


@pytest.fixture
def empty_sections_file(tmp_path: Path) -> Path:
    """Create a DRD with empty required sections."""
    f = tmp_path / "empty-sections-drd.md"
    f.write_text(EMPTY_SECTIONS_DRD, encoding="utf-8")
    return f


@pytest.fixture
def placeholder_drd_file(tmp_path: Path) -> Path:
    """Create a DRD with placeholder text."""
    f = tmp_path / "placeholder-drd.md"
    f.write_text(PLACEHOLDER_DRD, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# DMS (Data Model Specification) fixtures
# ---------------------------------------------------------------------------

VALID_DMS = """\
# Data Model Specification: Patient 360 Dimensional Model

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-03-15 |
| **Last Modified** | 2026-03-15 |
| **Author** | Data Modeler Agent |
| **Status** | Draft |
| **HLD Reference** | HLD-2026-03-14-patient-360-v1.md |

---

## 1. Design Overview

This DMS defines the bronze, silver, and gold layer schemas for the Patient 360
Medallion pipeline. The design follows HLD §2 Layer Specifications and implements
the dimensional model described in HLD §2.3 Gold Layer.

```mermaid
erDiagram
    bronze_patients {
        VARCHAR ID PK
        TIMESTAMP _ingested_at
    }
    bronze_encounters {
        VARCHAR ID PK
        VARCHAR PATIENT FK
    }
    silver_patients {
        VARCHAR patient_id PK
        VARCHAR first_name
    }
    silver_encounters {
        VARCHAR encounter_id PK
        VARCHAR patient_id FK
    }
    dim_patient {
        BIGINT patient_sk PK
        VARCHAR patient_id UK
        BOOLEAN is_current
    }
    fact_encounter {
        BIGINT encounter_sk PK
        BIGINT patient_sk FK
    }
    bronze_patients ||--|| silver_patients : "cleanse"
    bronze_encounters ||--|| silver_encounters : "cleanse"
    silver_patients ||--o{ silver_encounters : "has"
    silver_patients ||--|| dim_patient : "SCD2"
    silver_encounters ||--|| fact_encounter : "per enc"
    dim_patient ||--o{ fact_encounter : "patient_sk"
```

---

## 2. Bronze Layer Schemas

### patients (Bronze)

Raw ingestion of the Synthea patients table per HLD §2.1 Bronze Layer.

```yaml
table: patients
layer: bronze
schema: raw
partition_by: _ingested_date
columns:
  - name: Id
    type: VARCHAR
    nullable: false
    description: Original patient identifier
  - name: BIRTHDATE
    type: VARCHAR
    nullable: true
    description: Date of birth as string
  - name: FIRST
    type: VARCHAR
    nullable: true
    description: First name
  - name: LAST
    type: VARCHAR
    nullable: true
    description: Last name
  - name: GENDER
    type: VARCHAR
    nullable: true
    description: Gender code
  - name: _ingested_at
    type: TIMESTAMP
    nullable: false
    description: Ingestion timestamp (metadata)
  - name: _source_batch_id
    type: VARCHAR
    nullable: false
    description: Batch identifier (metadata)
  - name: _source_file
    type: VARCHAR
    nullable: false
    description: Source file path (metadata)
```

### encounters (Bronze)

Raw ingestion of the Synthea encounters table per HLD §2.1 Bronze Layer.

```yaml
table: encounters
layer: bronze
schema: raw
partition_by: _ingested_date
columns:
  - name: Id
    type: VARCHAR
    nullable: false
    description: Original encounter identifier
  - name: PATIENT
    type: VARCHAR
    nullable: false
    description: Patient reference
  - name: START
    type: VARCHAR
    nullable: true
    description: Encounter start datetime as string
  - name: STOP
    type: VARCHAR
    nullable: true
    description: Encounter stop datetime as string
  - name: ENCOUNTERCLASS
    type: VARCHAR
    nullable: true
    description: Encounter classification
  - name: _ingested_at
    type: TIMESTAMP
    nullable: false
    description: Ingestion timestamp (metadata)
  - name: _source_batch_id
    type: VARCHAR
    nullable: false
    description: Batch identifier (metadata)
  - name: _source_file
    type: VARCHAR
    nullable: false
    description: Source file path (metadata)
```

---

## 3. Silver Layer Schemas

### patients (Silver)

Canonical patient entity. Standardized from bronze patients per HLD §2.2.

```yaml
table: patients
layer: silver
schema: clinical
primary_key: patient_id
partition_by: _ingested_date
columns:
  - name: patient_id
    type: VARCHAR
    nullable: false
    source: bronze.patients.Id
    description: Unique patient identifier
  - name: birth_date
    type: DATE
    nullable: true
    source: bronze.patients.BIRTHDATE
    business_rule: BR-001
    description: Date of birth
  - name: first_name
    type: VARCHAR
    nullable: true
    source: bronze.patients.FIRST
    description: First name (proper case)
  - name: last_name
    type: VARCHAR
    nullable: false
    source: bronze.patients.LAST
    description: Last name (proper case)
  - name: gender
    type: VARCHAR(10)
    nullable: false
    source: bronze.patients.GENDER
    enum: [MALE, FEMALE, OTHER, UNKNOWN]
    business_rule: BR-002
    description: Standardized gender
```

### encounters (Silver)

Canonical encounter entity per HLD §2.2 Silver Layer.

```yaml
table: encounters
layer: silver
schema: clinical
primary_key: encounter_id
partition_by: encounter_date
columns:
  - name: encounter_id
    type: VARCHAR
    nullable: false
    source: bronze.encounters.Id
    description: Unique encounter identifier
  - name: patient_id
    type: VARCHAR
    nullable: false
    source: bronze.encounters.PATIENT
    description: FK to patients
  - name: encounter_start
    type: TIMESTAMP
    nullable: true
    source: bronze.encounters.START
    description: Encounter start timestamp
  - name: encounter_end
    type: TIMESTAMP
    nullable: true
    source: bronze.encounters.STOP
    description: Encounter end timestamp
  - name: encounter_class
    type: VARCHAR
    nullable: true
    source: bronze.encounters.ENCOUNTERCLASS
    description: Encounter classification (standardized)
```

---

## 4. Gold Layer Schemas

### dim_patient (Gold)

Patient dimension with SCD Type 2 for address tracking per HLD §2.3.

```yaml
table: dim_patient
layer: gold
schema: analytics
grain: one row per patient version
scd_type: 2
surrogate_key: patient_sk
columns:
  - name: patient_sk
    type: BIGINT
    nullable: false
    description: Surrogate key
  - name: patient_id
    type: VARCHAR
    nullable: false
    description: Natural key from silver
  - name: full_name
    type: VARCHAR
    nullable: false
    description: Derived from first_name and last_name
  - name: birth_date
    type: DATE
    nullable: true
  - name: gender
    type: VARCHAR(10)
    nullable: false
  - name: effective_from
    type: DATE
    nullable: false
  - name: effective_to
    type: DATE
    nullable: true
  - name: is_current
    type: BOOLEAN
    nullable: false
```

### fact_encounter (Gold)

Encounter fact table per HLD §2.3 Gold Layer.

```yaml
table: fact_encounter
layer: gold
schema: analytics
grain: one row per patient encounter
surrogate_key: encounter_sk
columns:
  - name: encounter_sk
    type: BIGINT
    nullable: false
    description: Surrogate key
  - name: encounter_id
    type: VARCHAR
    nullable: false
    description: Natural key
  - name: patient_sk
    type: BIGINT
    nullable: false
    description: FK to dim_patient
  - name: encounter_start
    type: TIMESTAMP
    nullable: true
  - name: encounter_end
    type: TIMESTAMP
    nullable: true
  - name: encounter_class
    type: VARCHAR
    nullable: true
foreign_keys:
  - column: patient_sk
    references: dim_patient.patient_sk
```

---

## 5. Naming Conventions

### Table Naming

- **Dimensions**: `dim_` prefix (e.g., `dim_patient`, `dim_provider`)
- **Facts**: `fact_` prefix (e.g., `fact_encounter`, `fact_condition`)
- **Silver**: domain prefix (e.g., `clinical_patients`)
- **Bronze**: source table name as-is

### Column Naming

- All columns use snake_case
- Surrogate keys: `{entity}_sk`
- Foreign keys: `{referenced_entity}_sk`
- Metadata columns: `_` prefix (`_ingested_at`, `_source_batch_id`)

---

## 6. SCD Strategy

| Dimension | Attribute | SCD Type | Rationale |
|-----------|-----------|----------|-----------|
| dim_patient | full_name | Type 1 | Only current name needed |
| dim_patient | birth_date | Type 1 | Corrections only |
| dim_patient | gender | Type 1 | Corrections only |
| dim_patient | address | Type 2 | Track address history for analytics |

---

## 7. Physical Design Notes

### Partitioning

- Bronze: partition by `_ingested_date` for idempotent re-ingestion
- Silver: partition by domain-relevant date (e.g., `encounter_date`)
- Gold: partition by reporting period

### Clustering

- Fact tables: cluster by most common join key (e.g., `patient_sk`)
- Dimensions: no clustering (small tables)

> Storage format, compression, and retention policies are in the LLD.

---

## 8. Traceability Matrix

| Gold Table | Silver Source | Bronze Source | Key Design Decisions |
|-----------|-------------|-------------|---------------------|
| dim_patient (SCD2) | patients | patients | SCD Type 2 for address |
| fact_encounter | encounters | encounters | Grain: one per encounter |

---

## 9. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-15 | Data Modeler Agent | Initial creation |
"""

MINIMAL_INVALID_DMS = """\
# Data Model Specification: Incomplete

## 1. Design Overview

This DMS is intentionally incomplete for testing.
"""

EMPTY_SECTIONS_DMS = """\
# Data Model Specification: Empty Sections

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-03-15 |
| **Author** | Test |
| **Status** | Draft |
| **HLD Reference** | HLD-test.md |

## 1. Design Overview

Test overview.

## 2. Bronze Layer Schemas

## 3. Silver Layer Schemas

## 4. Gold Layer Schemas

## 5. Naming Conventions

## 6. SCD Strategy

## 7. Physical Design Notes

## 8. Traceability Matrix

## 9. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-03-15 | Test | Initial |
"""

PLACEHOLDER_DMS = """\
# Data Model Specification: Placeholder Test

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-03-15 |
| **Author** | Test |
| **Status** | Draft |
| **HLD Reference** | HLD-test.md |

## 1. Design Overview

[TO BE DETERMINED - requires input from data modeler]

Medallion schema design per HLD §2 Layer Specifications.
References HLD §2.3 Gold Layer for dimensional model.

```mermaid
erDiagram
    patients ||--o{ encounters : has
```

## 2. Bronze Layer Schemas

```yaml
table: patients
layer: bronze
schema: raw
columns:
  - name: Id
    type: VARCHAR
    nullable: false
```

## 3. Silver Layer Schemas

[TODO: define silver schemas after source analysis]

```yaml
table: patients
layer: silver
schema: clinical
primary_key: patient_id
columns:
  - name: patient_id
    type: VARCHAR
    nullable: false
    source: bronze.patients.Id
    business_rule: BR-001
```

## 4. Gold Layer Schemas

```yaml
table: dim_patient
layer: gold
schema: analytics
grain: one row per patient
scd_type: 2
surrogate_key: patient_sk
columns:
  - name: patient_sk
    type: BIGINT
    nullable: false
foreign_keys:
  - column: provider_sk
    references: dim_provider.provider_sk
```

## 5. Naming Conventions

- dim_ prefix for dimensions
- fact_ prefix for facts
- snake_case for all columns

## 6. SCD Strategy

Type 1 for corrections, Type 2 for tracked attributes.

## 7. Physical Design Notes

Partition by ingestion date. Delta Lake compression.

## 8. Traceability Matrix

| Gold Table | Silver Source | Bronze Source | Key Design Decisions |
|-----------|-------------|-------------|---------------------|
| dim_patient (SCD2) | patients | patients | SCD Type 2, surrogate key |

## 9. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-03-15 | Test | Initial |
"""


@pytest.fixture
def valid_dms_file(tmp_path: Path) -> Path:
    """Create a valid DMS file for testing."""
    f = tmp_path / "valid-dms.md"
    f.write_text(VALID_DMS, encoding="utf-8")
    return f


@pytest.fixture
def invalid_dms_file(tmp_path: Path) -> Path:
    """Create a minimal invalid DMS file for testing."""
    f = tmp_path / "invalid-dms.md"
    f.write_text(MINIMAL_INVALID_DMS, encoding="utf-8")
    return f


@pytest.fixture
def empty_dms_sections_file(tmp_path: Path) -> Path:
    """Create a DMS with empty required sections."""
    f = tmp_path / "empty-sections-dms.md"
    f.write_text(EMPTY_SECTIONS_DMS, encoding="utf-8")
    return f


@pytest.fixture
def placeholder_dms_file(tmp_path: Path) -> Path:
    """Create a DMS with placeholder text."""
    f = tmp_path / "placeholder-dms.md"
    f.write_text(PLACEHOLDER_DMS, encoding="utf-8")
    return f
