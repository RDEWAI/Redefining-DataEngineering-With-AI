"""Shared fixtures for DRD and HLD validator tests."""
# ruff: noqa: E501  # test fixtures embed long markdown tables verbatim

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

## 2. Requirements Summary

### Functional Requirements

| FR# | Requirement | DRD Reference | Satisfied By |
|-----|------------|---------------|--------------|
| FR-1 | Consolidate source tables | DRD §2.1 | Gold layer |
| FR-2 | Track demographics changes | DRD §3.2 | SCD Type 2 |

### Non-Functional Requirements

| NFR# | Requirement | DRD Ref | Satisfied By | Target |
|------|------------|---------|--------------|--------|
| NFR-1 | Query response time | DRD §4.3 | Gold partitioning | < 2s |
| NFR-2 | Data freshness | DRD §4.4 | Hourly batch | 1 hour |

---

## 3. Integration Architecture

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

## 4. Data Architecture

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

### SCD Strategy

| Dimension Type | SCD Approach | Rationale |
|----------------|-------------|-----------|
| Patient demographics | SCD Type 2 | Track address/name changes over time for clinical accuracy |
| Provider attributes | SCD Type 2 | Track specialty and organization changes |

---

## 5. Pipeline Architecture

### Technology Decisions

| Component | Selected Tool | Why |
|-----------|--------------|-----|
| Processing Engine | Apache Spark (PySpark) | Team proficiency; handles 4.4M rows |
| Table Format | Delta Lake | ACID writes, time travel, MERGE INTO for SCD2; team proficient |
| Metastore | Unity Catalog OSS | Catalog/schema hierarchy, REST API for consumer access |
| Lineage | OpenLineage + Marquez | HIPAA audit trail requirement (DRD Section 7.5) |
| Data Quality | Spark Expectations | Rule-based DQ enforcement at each layer boundary |
| Language | Python | Team high proficiency; PySpark + pytest ecosystem |
| Orchestration | Make + scripts | Minimal overhead for local dev phase |

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

### Scalability Model

Total dataset: ~6.9M rows across 18 tables (~3.8 GB as Delta). Largest table:
observations at 4.4M rows. Patient count: 5,767.

| Metric | Current | Year 1 | Year 3 | Assumption |
|--------|---------|--------|--------|------------|
| Patient count | 5,767 | ~6,000 | ~6,500 | ~200 new patients/year |
| Total rows | 6.9M | ~7.1M | ~7.6M | Linear growth with patients |
| Storage (Delta) | 3.8 GB | ~4.2 GB | ~5.0 GB | Delta compression ~30% vs CSV |
| Pipeline runtime | ~15 min | ~16 min | ~18 min | Linear growth with row count |

### Cost Model

Phase 1 is local dev with $0 infrastructure cost. Cloud migration cost scales
linearly with compute hours and storage volume. Estimated ~$200/month for
cloud deployment at current scale.

### Reliability Targets

| Metric | Target | Justification |
|--------|--------|---------------|
| RTO | 4 hours | Read-only system; rebuild from source CSVs |
| RPO | 24 hours (last batch) | Source EHR CSVs are authoritative |

---

## 6. Governance

### Data Classification

| Classification | Examples | Handling Strategy |
|---------------|----------|-------------------|
| PHI - Confidential | Demographics, SSN, DOB | Encrypted at rest (Phase 2), RBAC |
| PHI - Clinical | Conditions, medications, allergies | Clinical role access only [DRD §5.5] |
| Financial | Claims, encounter costs | Billing role only per DRD Section 5.5 |
| Internal | Reference data (orgs, providers) | Standard access controls |

### IAM Access Strategy

| Role Group | Layer Access | Restrictions | Phase |
|-----------|-------------|-------------|-------|
| Clinical users | Gold READ | No cost columns, masked SSN | Phase 1 |
| Billing staff | Gold READ | No clinical notes | Phase 1 |
| Data engineers | All layers WRITE | No restrictions | Phase 1 |
| Full RBAC + SSO | All layers | Column-level enforcement | Phase 2 |

### Data Quality Strategy

Bronze: Schema validation and not-null checks on identity fields. Silver:
Referential integrity (FK checks), business rule validation, derived field
computation. Gold: Column-level assertions on consumer-facing fields
(patient_id NOT NULL, allergy array never suppressed).

### Compliance Requirements

HIPAA compliance is a separate workstream per DRD Section 6.1. Phase 1 focuses
on data consolidation with application-layer masking (SSN last 4, address
city/state only). Full HIPAA technical safeguards (encryption at rest, TLS,
audit logging) deferred to Phase 2.

---

## 7. Decision Log

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

## 8. Open Questions & Risks

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

## 9. Appendix

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

## 2. Requirements Summary

## 3. Integration Architecture

## 4. Data Architecture

## 5. Pipeline Architecture

Some pipeline content without change data capture details.

## 6. Governance

## 7. Decision Log

## 8. Open Questions & Risks
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

## 2. Requirements Summary

| FR# | Requirement | DRD Reference | Satisfied By |
|-----|------------|---------------|--------------|
| FR-1 | Consolidate patient data | DRD §2.1 | Gold layer |

| NFR# | Requirement | DRD Reference | Satisfied By | Target |
|------|------------|---------------|--------------|--------|
| NFR-1 | Query response time | DRD §4.3 | Gold partitioning | < 2s |

## 3. Integration Architecture

Source: Synthea CSV via file-based ingestion.

## 4. Data Architecture

**Bronze Layer**: Raw ingestion of source tables.

**Silver Layer**: Cleansed and conformed data.

**Gold Layer**: Dimensional model.

```mermaid
flowchart LR
    SRC --> BRZ --> SLV --> GLD
```

## 5. Pipeline Architecture

| Component | Selected Tool | Why |
|-----------|--------------|-----|
| Processing | Spark | Team proficiency |
| Storage | Delta Lake | ACID writes |
| Metastore | Unity Catalog | Catalog management |

Full snapshot for small tables. Timestamp-based for large tables.
Snapshot is acceptable because DRD projects <100K patients initially.

Current volume: 5,767 patients, ~5M rows total.
Growth: 100K patients in 12 months.
Cost: $0 local, ~$200/month cloud.

## 6. Governance

HIPAA compliance required per DRD Section 7.1.
Data classification includes PHI and financial data.

## 7. Decision Log

### Decision 1: Architecture Pattern

**Selected**: Medallion

**Rationale**: DRD specifies mixed latency. Trade-off is no sub-minute freshness.

## 8. Open Questions & Risks

| # | Question | Owner | Due Date | Status |
|---|----------|-------|----------|--------|
| 1 | Cloud timeline | CIO | 2026-04-01 | Open |
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


# ---------------------------------------------------------------------------
# DQS (Data Quality Specification) test constants
# ---------------------------------------------------------------------------

VALID_DQS = """\
# Data Quality Specification: Patient 360 Pipeline

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-03-17 |
| **Last Modified** | 2026-03-17 |
| **Author** | DQ Engineer Agent |
| **Status** | Draft |
| **STM Reference** | STM-2026-03-17-patient-360.xlsx v1.0 |
| **DMS Reference** | DMS-2026-03-16-patient-360.md v1.0 |
| **DRD Reference** | DRD-2026-02-11-patient-360.md v1.1 |

## 1. Overview

This Data Quality Specification defines validation rules for the Patient 360
pipeline across bronze, silver, and gold layers.

### Severity Definitions

| Severity | Action | Description |
|----------|--------|-------------|
| **CRITICAL** | Halt pipeline / reject record | Data integrity at risk |
| **WARNING** | Log and continue / quarantine row | Data quality degraded |
| **INFO** | Record for monitoring only | Informational observation |

### Rule ID Conventions

| Prefix | Category | Applies To |
|--------|----------|------------|
| DQ-FLD | Field-level validations | All layers |
| DQ-REF | Referential integrity | Silver, Gold |
| DQ-STA | Statistical distribution | All layers |
| DQ-REC | Reconciliation | Gold vs Source |
| DQ-FRS | Freshness monitoring | All layers |

## 2. Field-Level Validation Rules

### Bronze Layer

| Rule ID | Table | Column | Expression | Severity |
|---------|-------|--------|------------|----------|
| DQ-FLD-001 | bronze.patients | id | id IS NOT NULL | CRITICAL |
| DQ-FLD-002 | bronze.patients | birthdate | FORMAT check | WARNING |
| DQ-FLD-003 | bronze.encounters | id | id IS NOT NULL | CRITICAL |
| DQ-FLD-004 | bronze.encounters | start | start IS NOT NULL | CRITICAL |

### Silver Layer

| Rule ID | Table | Column | Expression | Severity |
|---------|-------|--------|------------|----------|
| DQ-FLD-005 | clinical.patients | patient_id | NOT NULL | CRITICAL |
| DQ-FLD-006 | clinical.patients | birth_date | RANGE check | WARNING |
| DQ-FLD-007 | clinical.patients | gender | ENUM check | WARNING |
| DQ-FLD-008 | clinical.encounters | encounter_class | ENUM check | WARNING |
| DQ-FLD-009 | clinical.encounters | start_date | NOT NULL | CRITICAL |

### Gold Layer

| Rule ID | Table | Column | Expression | Severity |
|---------|-------|--------|------------|----------|
| DQ-FLD-010 | analytics.dim_patient | patient_sk | NOT NULL | CRITICAL |
| DQ-FLD-011 | analytics.dim_patient | patient_id | UNIQUE check | CRITICAL |
| DQ-FLD-012 | analytics.fact_encounter | encounter_sk | NOT NULL | CRITICAL |
| DQ-FLD-013 | analytics.fact_encounter | patient_sk | NOT NULL | CRITICAL |
| DQ-FLD-014 | analytics.fact_encounter | encounter_date | RANGE | WARNING |

## 3. Referential Integrity Rules

| Rule ID | Child Table | Child Col | Parent Table | Severity |
|---------|-------------|-----------|--------------|----------|
| DQ-REF-001 | clinical.encounters | patient_id | clinical.patients | CRITICAL |
| DQ-REF-002 | clinical.conditions | patient_id | clinical.patients | CRITICAL |
| DQ-REF-003 | fact_encounter | patient_sk | dim_patient | WARNING |
| DQ-REF-004 | fact_encounter | provider_sk | dim_provider | WARNING |
| DQ-REF-005 | fact_condition | encounter_sk | fact_encounter | CRITICAL |

## 4. Statistical Distribution Tests

| Rule ID | Table | Metric | Baseline | Threshold |
|---------|-------|--------|----------|-----------|
| DQ-STA-001 | bronze.patients | row_count | 1000 | ±20% |
| DQ-STA-002 | bronze.encounters | row_count | 50000 | ±20% |
| DQ-STA-003 | clinical.patients | null_rate(birth_date) | 0.5% | <5% |
| DQ-STA-004 | clinical.encounters | value_dist | 60% | ±15% |
| DQ-STA-005 | analytics.dim_patient | is_current_count | 1000 | ±10% |

## 5. Reconciliation Rules

| Rule ID | Source | Target | Comparison | Tolerance |
|---------|--------|--------|------------|-----------|
| DQ-REC-001 | bronze.patients | dim_patient | COUNT DISTINCT | ±0.1% |
| DQ-REC-002 | bronze.encounters | fact_encounter | COUNT(*) | ±0.1% |
| DQ-REC-003 | bronze.encounters | fact_encounter | SUM(cost) | ±0.01% |

## 6. Freshness & SLA Monitoring

| Consumer | Table | Max Latency | Check Frequency | Alert Channel | DRD Ref |
|----------|-------|-------------|-----------------|---------------|---------|
| Clinical Dashboard | analytics.dim_patient | 1 hour | Every 15 min | PagerDuty | DRD §5.1 |
| Clinical Dashboard | analytics.fact_encounter | 1 hour | Every 15 min | PagerDuty | DRD §5.1 |
| BI Analytics | analytics.dim_patient | 24 hours | Every 4 hours | Slack | DRD §5.2 |
| Regulatory Reporting | analytics.fact_encounter | 30 days | Weekly | Email | DRD §5.4 |

## 7. Alert & Escalation Framework

### Severity Routing

| Severity | Response Time | Notification Channel | Escalation |
|----------|--------------|---------------------|------------|
| CRITICAL | 15 minutes | PagerDuty + Slack #data-alerts | On-call data engineer |
| WARNING | 4 hours | Slack #data-quality | Data quality team lead |
| INFO | Next business day | Email digest | DQ dashboard only |

### Threshold Breach Actions

When error_drop_threshold is exceeded:
- PROD: Halt pipeline, page on-call engineer
- QA: Log warning, continue processing
- DEV: Log info only

## 8. Traceability Matrix

| DQS Rule | DRD Req | DMS Ref | STM Sheet | Description |
|----------|---------|---------|-----------|-------------|
| DQ-FLD-001 | DRD §4 | DMS §2 | Src-Bronze | Patient ID |
| DQ-FLD-005 | DRD §4 | DMS §3 | Brz-Silver | Patient ID |
| DQ-FLD-010 | DRD §4 | DMS §4 | Slv-Gold | Patient SK |
| DQ-REF-001 | DRD §4 | DMS §3 | Brz-Silver | Enc→Pat FK |
| DQ-STA-001 | DRD §4 | DMS §2 | Src-Bronze | Row count |
| DQ-REC-001 | DRD §4 | DMS §4 | Slv-Gold | Pat recon |
| DQ-FRS-001 | DRD §5.1 | DMS §4 | N/A | Freshness |
| DQ-FLD-014 | DRD §6 | DMS §4 | Slv-Gold | Date range |

## 9. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-17 | DQ Engineer Agent | Initial DQS for Patient 360 pipeline |
"""

MINIMAL_INVALID_DQS = """\
# Data Quality Specification: Incomplete

| Field | Value |
|-------|-------|
| **Version** | 0.1 |

## 1. Overview

This DQS is incomplete.
"""

EMPTY_SECTIONS_DQS = """\
# Data Quality Specification: Empty Sections

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-03-17 |
| **Author** | Test |
| **Status** | Draft |
| **STM Reference** | STM-test.xlsx |
| **DMS Reference** | DMS-test.md |

## 1. Overview

## 2. Field-Level Validation Rules

## 3. Referential Integrity Rules

## 4. Statistical Distribution Tests

## 5. Reconciliation Rules

## 6. Freshness & SLA Monitoring

## 7. Alert & Escalation Framework

## 8. Traceability Matrix

## 9. Version History
"""

PLACEHOLDER_DQS = """\
# Data Quality Specification: Placeholder

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-03-17 |
| **Author** | Test |
| **Status** | Draft |
| **STM Reference** | [TBD] |
| **DMS Reference** | [TODO] |

## 1. Overview

[TO BE DETERMINED]

## 2. Field-Level Validation Rules

[TBD] - Rules will be defined after STM review.

## 3. Referential Integrity Rules

[PLACEHOLDER]

## 4. Statistical Distribution Tests

[TODO]

## 5. Reconciliation Rules

[TBD]

## 6. Freshness & SLA Monitoring

[TBD]

## 7. Alert & Escalation Framework

[TBD]

## 8. Traceability Matrix

[TBD]

## 9. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-03-17 | Test | Initial placeholder |
"""


@pytest.fixture
def valid_dqs_file(tmp_path: Path) -> Path:
    """Create a valid DQS file for testing."""
    f = tmp_path / "valid-dqs.md"
    f.write_text(VALID_DQS, encoding="utf-8")
    return f


@pytest.fixture
def invalid_dqs_file(tmp_path: Path) -> Path:
    """Create an invalid (minimal) DQS file for testing."""
    f = tmp_path / "invalid-dqs.md"
    f.write_text(MINIMAL_INVALID_DQS, encoding="utf-8")
    return f


@pytest.fixture
def empty_dqs_sections_file(tmp_path: Path) -> Path:
    """Create a DQS with empty required sections."""
    f = tmp_path / "empty-sections-dqs.md"
    f.write_text(EMPTY_SECTIONS_DQS, encoding="utf-8")
    return f


@pytest.fixture
def placeholder_dqs_file(tmp_path: Path) -> Path:
    """Create a DQS with placeholder text."""
    f = tmp_path / "placeholder-dqs.md"
    f.write_text(PLACEHOLDER_DQS, encoding="utf-8")
    return f


# ── LLD (Low-Level Design) fixtures ──────────────────────────────────────────

VALID_LLD = """\
# Low-Level Design: Patient 360 Pipeline

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-03-22 |
| **Last Modified** | 2026-03-22 |
| **Author** | Technical Lead Agent |
| **Status** | Draft |
| **DRD Reference** | DRD-2026-03-10-patient-360.md v1.0 |
| **HLD Reference** | HLD-2026-03-12-patient-360.md v1.0 |
| **DMS Reference** | DMS-2026-03-14-patient-360.md v1.0 |
| **STM Reference** | STM-2026-03-16-patient-360.xlsx v1.0 |
| **DQS Reference** | DQS-2026-03-18-patient-360.md v1.0 |
| **Target Scaffold** | cookiecutter-chapter (see `inputs/lld/v1/templates/cookiecutter-chapter/`) |
| **Project Name** | patient_360 |
| **Chapter** | chapter-5 |

---

## 1. Design Overview

This LLD specifies the implementation details for the Patient 360 data pipeline.
The pipeline uses a Medallion architecture (Bronze/Silver/Gold) with PySpark
on a Docker-based Spark cluster, orchestrated via Airflow DAGs. Key decisions
include Delta Lake for storage format [HLD §5.1], daily batch processing
[DRD §4.4], and Spark-Expectations for DQ validation [DQS §2].

## 2. Code Architecture

### 2.1 Project Layout

The project structure below is the cookiecutter scaffold at
`inputs/lld/v1/templates/cookiecutter-chapter/`.

```
patient_360/
├── src/patient_360/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── utils/
├── tests/
├── airflow/
│   ├── dags/
│   └── configs/
├── contracts/
├── dq_rules/
├── ddl/
│   └── liquibase/
└── _infra/
    ├── ci/
    ├── cd/
    └── docker/
```

### 2.2 Module Responsibilities

| Module Path | DMS Layer | Responsibility |
|---|---|---|
| `src/patient_360/bronze/` | Bronze | Ingestion from raw sources. |
| `src/patient_360/silver/` | Silver | Conformed dimensions/facts. |
| `src/patient_360/gold/` | Gold | Patient 360 marts. |
| `src/patient_360/utils/` | Cross-cutting | SparkSession, contracts, DQ. |

Coding conventions follow PEP 8 with Ruff linting. For schema definitions,
see DMS §4.2. Testing targets 80% coverage with pytest.

## 3. File Formats & Storage Layout

Storage uses Delta Lake format with Snappy compression per HLD §5.1.
Partitioning strategy follows the DMS layer definitions [DMS §3].

| Layer | Format | Compression | Partitioning |
|-------|--------|-------------|-------------|
| Bronze | Delta | Snappy | ingestion_date |
| Silver | Delta | Snappy | processing_date |
| Gold | Delta | Zstd | report_date |

Directory layout: `/data/{layer}/{domain}/{table}/year={YYYY}/month={MM}/`.

## 4. DAG Specification

The pipeline DAG runs daily at 02:00 UTC with the following tasks.
Critical path: ingest → cleanse → denormalize → validate (4.5 hours).

| Task | Type | Layer | Dependencies | Timeout | Retries |
|------|------|-------|-------------|---------|---------|
| ingest_patients | ingestion | bronze | none | 30m | 3 |
| ingest_encounters | ingestion | bronze | none | 30m | 3 |
| ingest_conditions | ingestion | bronze | none | 30m | 3 |
| cleanse_patients | transform | silver | ingest_patients | 45m | 2 |
| cleanse_encounters | transform | silver | ingest_encounters | 45m | 2 |
| build_patient_360 | denorm | gold | cleanse_patients, cleanse_encounters | 60m | 1 |
| validate_gold | dq_check | gold | build_patient_360 | 15m | 1 |

```mermaid
graph TD
    A[ingest_patients] --> D[cleanse_patients]
    B[ingest_encounters] --> E[cleanse_encounters]
    C[ingest_conditions] --> F[cleanse_conditions]
    D --> G[build_patient_360]
    E --> G
    G --> H[validate_gold]
```

## 5. Task Implementation Details

Each task has explicit I/O contracts per STM Tab:source-to-bronze mappings.

| Task ID | Layer | Module Path | Contract File | DQ Rules File | DAG Task Node | Inputs | Outputs | Transform Ref | DQ Check |
|---|---|---|---|---|---|---|---|---|---|
| T-B01 | Bronze | `src/patient_360/bronze/patients.py` | `contracts/patients.yml` | `dq_rules/patients.yml` | ingest_patients | raw/patients.csv | bronze/patients/ | STM src-to-bronze | DQS §2 |
| T-S01 | Silver | `src/patient_360/silver/patient_dim.py` | `contracts/patient_dim.yml` | `dq_rules/patient_dim.yml` | cleanse_patients | bronze/patients/ | silver/patient_dim/ | STM brz-to-silver | DQS §2 |
| T-G01 | Gold | `src/patient_360/gold/patient_360.py` | `contracts/patient_360.yml` | `dq_rules/patient_360.yml` | build_patient_360 | silver/patient_dim/ | gold/patient_360/ | STM slv-to-gold | DQS §4 |
| T-G02 | Gold | `src/patient_360/gold/readmission_risk.py` | `contracts/readmission_risk.yml` | `dq_rules/readmission_risk.yml` | validate_gold | gold/patient_360/ | gold/readmission_risk/ | DQS §5 | DQS §5 (DQ-REC-001) |

When input is empty, ingestion tasks write a zero-row Delta table with schema preserved.

## 6. Performance & Optimization

Spark cluster: 4 executors x 4 cores x 8GB each = 128GB total [HLD §5.4].
Target file size: 128MB per partition. Broadcast join threshold: 10MB.
Parallelism: 16 partitions default. Cache silver tables used by multiple gold tasks.

## 7. Configuration Schema

| Parameter | Type | Default | Description | Per-Environment |
|-----------|------|---------|-------------|----------------|
| schedule_cron | string | 0 2 * * * | DAG schedule | Yes |
| spark_executor_memory | string | 8g | Executor memory | Yes |
| spark_num_executors | int | 4 | Number of executors | Yes |
| base_data_path | string | /data | Root storage path | Yes |
| retry_max_attempts | int | 3 | Max task retries | Yes |
| alert_channel | string | #pipeline-alerts | Slack channel | Yes |
| dq_fail_threshold | float | 0.05 | DQ failure rate threshold | Yes |

## 8. Error Handling

Retry policy: ingestion tasks retry 3 times with 60-second exponential backoff.
Transform tasks retry 2 times with 120-second backoff. DQ tasks retry once.

Dead letter / quarantine: failed records written to `/data/quarantine/{table}/{date}/`
with retention of 30 days. Alert triggered when quarantine volume exceeds 5%.

Alerting: CRITICAL failures page on-call via PagerDuty. WARNING issues post to
#pipeline-alerts Slack channel. All failures logged to monitoring dashboard.

## 9. Deployment

Environments: DEV (2 executors, 4GB each), STAGING (4 executors, 8GB each),
PROD (8 executors, 16GB each).

### 9.1 `_infra/ci/` — Continuous Integration

`_infra/ci/github-actions.yaml` runs `ruff check`, `pytest`, and contract
validation on every PR.

### 9.2 `_infra/cd/` — Continuous Deployment

`_infra/cd/deploy.yaml` promotes an image tag across envs using per-env YAMLs
in `_infra/cd/config/{dev,stage,prod}.yaml`.

### 9.3 `_infra/docker/` — Container Images

One image per layer: `_infra/docker/Dockerfile.{bronze,silver,gold}`.

### 9.4 `ddl/liquibase/` — Schema Migrations

`ddl/liquibase/master.xml` includes per-table changelogs under
`ddl/liquibase/changelogs/`.

Promotion: PR merge → CI tests → DEV deploy → smoke test → STAGING deploy →
integration test → PROD deploy with manual approval gate.

Rollback procedure:
1. Detect failure via monitoring dashboard alert
2. Revert to previous container image tag
3. Re-process affected date partitions from source
4. Notify stakeholders via #pipeline-alerts
5. Post-mortem within 24 hours

## 10. Monitoring

| Metric | Type | Collection | Threshold | Alert Channel |
|--------|------|-----------|-----------|---------------|
| task_duration | timer | OpenTelemetry | > 2x baseline | Slack |
| row_count_delta | gauge | Custom metric | > 20% change | PagerDuty |
| dq_pass_rate | gauge | SE framework | < 95% | PagerDuty |
| pipeline_latency | timer | Airflow | > SLA target | PagerDuty |

Dashboard: Grafana board refreshed every 5 minutes showing task durations,
row counts, DQ pass rates, and SLA compliance per DRD §4.3.

## 11. Upstream Artifact References

| Topic | Upstream Artifact | Section |
|-------|-------------------|---------|
| Business requirements & SLAs | DRD | DRD §1, DRD §4.3, DRD §4.4 |
| Architecture pattern & tech stack | HLD | HLD §4.1, HLD §5.1-5.6 |
| Logical/physical schemas | DMS | DMS §2-4, DMS §6-7 |
| Transformation mappings | STM | STM Tabs: source-to-bronze, bronze-to-silver |
| DQ rules & thresholds | DQS | DQS §2-5, DQS §7 |

## 12. Traceability Matrix

| Requirement | Source | LLD Component |
|-------------|--------|---------------|
| FR-1: Consolidate sources | DRD §2.1 | Task: build_patient_360 |
| FR-2: Track demographics | DRD §3.2 | Silver layer SCD Type 2 |
| NFR-1: Query < 2s | DRD §4.3 | Gold partitioning + Zstd |
| NFR-2: Daily freshness | DRD §4.4 | DAG schedule: 02:00 UTC |

## 13. Decision Log

### Decision: Storage Format

**Options Considered**:
1. Parquet — simple, widely supported
2. Delta Lake — ACID, time travel, schema evolution
3. Iceberg — catalog integration, partition evolution

**Selected**: Delta Lake

**Rationale**: Delta provides ACID transactions and time travel needed for
SCD Type 2 tracking and rollback capability per HLD §5.1.

**Trade-off**: Vendor lock-in to Databricks ecosystem accepted because
the team has Delta expertise (team capabilities assessment).

## 14. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-22 | Technical Lead Agent | Initial LLD creation |
"""

MINIMAL_INVALID_LLD = """\
# Low-Level Design: Incomplete

| Field | Value |
|-------|-------|
| **Version** | 0.1 |

## 1. Design Overview

This is a minimal LLD.
"""

EMPTY_SECTIONS_LLD = """\
# Low-Level Design: Empty Sections

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-03-22 |
| **Author** | Test |
| **Status** | Draft |
| **DRD Reference** | test |
| **HLD Reference** | test |
| **DMS Reference** | test |
| **STM Reference** | test |
| **DQS Reference** | test |

## 1. Design Overview

## 2. Code Architecture

## 3. File Formats & Storage Layout

## 4. DAG Specification

## 5. Task Implementation Details

## 6. Performance & Optimization

## 7. Configuration Schema

## 8. Error Handling

## 9. Deployment

## 10. Monitoring

## 11. Upstream Artifact References

## 12. Traceability Matrix

## 13. Decision Log

## 14. Version History
"""

PLACEHOLDER_LLD = """\
# Low-Level Design: Placeholder

| Field | Value |
|-------|-------|
| **Version** | 0.1 |
| **Created** | 2026-03-22 |
| **Author** | Test |
| **Status** | Draft |
| **DRD Reference** | DRD v1 |
| **HLD Reference** | HLD v1 |
| **DMS Reference** | DMS v1 |
| **STM Reference** | STM v1 |
| **DQS Reference** | DQS v1 |

## 1. Design Overview

The pipeline implements the Patient 360 use case. It processes healthcare
data through bronze, silver, and gold layers. DRD §1 defines the scope and
HLD §4.1 specifies the Medallion pattern. DMS §2 has schema definitions.
STM Tab:source covers mappings. DQS §2 defines field rules.

## 2. Code Architecture

[TBD - awaiting development standards review]

## 3. File Formats & Storage Layout

| Layer | Format | Compression |
|-------|--------|-------------|
| Bronze | Delta | Snappy |
| Silver | Delta | Snappy |
| Gold | Delta | Zstd |

## 4. DAG Specification

| Task | Type | Layer | Dependencies | Timeout | Retries |
|------|------|-------|-------------|---------|---------|
| ingest_patients | ingestion | bronze | none | 30m | 3 |
| cleanse_patients | transform | silver | ingest_patients | 45m | 2 |
| build_patient_360 | denorm | gold | cleanse_patients | 60m | 1 |

Critical path analysis pending.

## 5. Task Implementation Details

| Task | Input Path | Output Path | Transform Ref | DQ Check |
|------|-----------|-------------|---------------|----------|
| ingest_patients | /raw/patients.csv | /bronze/patients/ | STM Tab:src | DQS §2 |
| cleanse_patients | /bronze/patients/ | /silver/patients/ | STM Tab:brz | DQS §2 |
| build_patient_360 | /silver/patients/ | /gold/patient_360/ | STM Tab:slv | DQS §4 |

## 6. Performance & Optimization

Cluster: 4 executors x 4 cores x 8GB each = 128GB total.

## 7. Configuration Schema

| Parameter | Type | Default | Description | Per-Environment |
|-----------|------|---------|-------------|----------------|
| schedule_cron | string | 0 2 * * * | DAG schedule | Yes |
| spark_executor_memory | string | 8g | Executor memory | Yes |
| base_data_path | string | /data | Root path | Yes |

## 8. Error Handling

[TODO - define retry and dead letter strategy]

## 9. Deployment

DEV and PROD environments defined. Rollback is manual.

## 10. Monitoring

[TBD - monitoring metrics to be defined]

## 11. Upstream Artifact References

| Topic | Upstream | Section |
|-------|----------|---------|
| Requirements | DRD | DRD §1 |
| Architecture | HLD | HLD §4 |
| Schemas | DMS | DMS §2 |
| Mappings | STM | STM Tabs |
| DQ Rules | DQS | DQS §2 |

## 12. Traceability Matrix

[TBD]

## 13. Decision Log

Options Considered and Rationale pending review.

## 14. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-03-22 | Test | Initial placeholder |
"""


@pytest.fixture
def valid_lld_file(tmp_path: Path) -> Path:
    """Create a valid LLD file for testing."""
    f = tmp_path / "valid-lld.md"
    f.write_text(VALID_LLD, encoding="utf-8")
    return f


@pytest.fixture
def invalid_lld_file(tmp_path: Path) -> Path:
    """Create an invalid (minimal) LLD file for testing."""
    f = tmp_path / "invalid-lld.md"
    f.write_text(MINIMAL_INVALID_LLD, encoding="utf-8")
    return f


@pytest.fixture
def empty_lld_sections_file(tmp_path: Path) -> Path:
    """Create an LLD with empty required sections."""
    f = tmp_path / "empty-sections-lld.md"
    f.write_text(EMPTY_SECTIONS_LLD, encoding="utf-8")
    return f


@pytest.fixture
def placeholder_lld_file(tmp_path: Path) -> Path:
    """Create an LLD with placeholder text."""
    f = tmp_path / "placeholder-lld.md"
    f.write_text(PLACEHOLDER_LLD, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Stories (Sprint Backlog) fixtures
# ---------------------------------------------------------------------------

VALID_BACKLOG = """\
# Sprint Backlog: Patient 360 Data Pipeline

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-03-23 |
| **Last Modified** | 2026-03-23 |
| **Author** | Scrum Master Agent |
| **Status** | Draft |
| **LLD Reference** | LLD-2026-03-23-patient-360.md v1.0 |

---

## 1. Executive Summary

The Patient 360 sprint backlog decomposes the LLD into 3 epics and 6 stories
across 3 sprints. Total effort is estimated at 45 story points.

---

## 2. Epic Overview

| Epic | Title | Stories | Points | Sprints | LLD Section |
|------|-------|---------|--------|---------|-------------|
| EPIC-01 | Infrastructure Setup | 2 | 10 | 1 | §2 |
| EPIC-02 | Bronze Ingestion | 2 | 15 | 1-2 | §4.1 |
| EPIC-03 | Silver Transformation | 2 | 20 | 2-3 | §4.2 |

**Total**: 6 stories, 45 points across 3 sprints

---

## 3. Dependency Graph

```mermaid
flowchart LR
    S01001[STORY-01-001] --> S01002[STORY-01-002]
    S01002 --> S02001[STORY-02-001]
    S01002 --> S02002[STORY-02-002]
    S02001 --> S03001[STORY-03-001]
    S02002 --> S03002[STORY-03-002]
```

---

## 4. Sprint Plan

### Sprint 1: Foundation

| Story ID | Title | Points | Epic |
|----------|-------|--------|------|
| STORY-01-001 | Set up DuckDB environment | 5 | EPIC-01 |
| STORY-01-002 | Create bronze schemas | 5 | EPIC-01 |

**Sprint Total**: 10 points

---

## 5. Traceability Matrix

| Epic / Story | LLD | DMS | STM | DQS | DRD | HLD |
|-------------|-----|-----|-----|-----|-----|-----|
| EPIC-01 | §2 | §4.1 | — | — | §2.1 | §4 |
| STORY-01-001 | §2.1 | §4.1.1 | — | — | §2.1 | §4.1 |

---

## 6. Risks & Assumptions

- **Risk**: Sam R. at 50% allocation may delay Bronze stories _(Mitigation: Alex as backup)_

### Assumptions

- All upstream artifacts (DRD through LLD) are approved and stable

---

## 7. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-23 | Scrum Master Agent | Initial backlog creation |
"""

VALID_EPIC = """\
# EPIC-01: Infrastructure Setup

| Field | Value |
|-------|-------|
| **LLD Section** | §2 |
| **Stories** | 2 |
| **Total Points** | 10 |
| **Sprints** | 1 |
| **Status** | Draft |

## Objective

Set up the DuckDB development environment and create all bronze layer schemas
required for the Patient 360 data pipeline.

## Scope

### In Scope
- DuckDB environment configuration
- Bronze schema DDL for all 18 Synthea tables

### Out of Scope
- Data loading (covered in EPIC-02)

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-01-001 | Set up DuckDB environment | 5 | 1 | None |
| STORY-01-002 | Create bronze schemas | 5 | 1 | STORY-01-001 |

## Acceptance Criteria (Epic-Level)

- [ ] DuckDB environment operational with all required extensions [LLD §2.1]
- [ ] All 18 bronze tables created matching DMS §4.1 specifications [DMS §4.1]

## Risks & Assumptions

- Assumes DuckDB version compatibility with required extensions
"""

VALID_STORY = """\
# STORY-01-001: Set up DuckDB environment

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Infrastructure Setup |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 1 |
| **Dependencies** | None |
| **Status** | To Do |

## User Story

As a data engineer, I want a configured DuckDB environment so that I can begin
building the Patient 360 data pipeline.

## Description

Set up the DuckDB development environment with all required extensions and
configurations per the LLD specifications. This includes installing DuckDB,
configuring the database file location, and verifying connectivity.

## Acceptance Criteria

- [ ] DuckDB installed and accessible via CLI [LLD §2.1]
- [ ] Database file created at configured path [LLD §2.2]
- [ ] Required extensions loaded (httpfs, parquet) [LLD §2.3]
- [ ] Read-only connection verified for source data [DMS §4.1]

## Technical Notes

- Upstream references: LLD §2.1-2.3, HLD §5.1
- Implementation hints: Use DuckDB 1.1.3 per LLD §5.1 technology table

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.1 Environment Setup, §2.2 Database Configuration, §2.3 Extensions |
| HLD | §5.1 Technology Decisions (DuckDB) |
| DMS | §4.1 Bronze Layer Schema Overview |
"""

MINIMAL_INVALID_BACKLOG = """\
# Sprint Backlog: Incomplete

## 1. Executive Summary

Too short.
"""

EMPTY_SECTIONS_BACKLOG = """\
# Sprint Backlog: Empty Sections

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-03-23 |
| **Author** | Test |
| **Status** | Draft |
| **LLD Reference** | test |

## 1. Executive Summary

A short summary sentence here.

## 2. Epic Overview

## 3. Dependency Graph

## 4. Sprint Plan

## 5. Traceability Matrix

## 6. Risks & Assumptions

## 7. Version History
"""

PLACEHOLDER_BACKLOG = """\
# Sprint Backlog: With Placeholders

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-03-23 |
| **Author** | Test |
| **Status** | Draft |
| **LLD Reference** | test |

## 1. Executive Summary

The Patient 360 pipeline [TBD - add details].

## 2. Epic Overview

[TODO: Add epic table]

## 3. Dependency Graph

```mermaid
flowchart LR
    A --> B
```

## 4. Sprint Plan

[TO BE DETERMINED]

## 5. Traceability Matrix

TBD

## 6. Risks & Assumptions

None identified yet.

## 7. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-23 | Test | Initial |
"""


@pytest.fixture
def valid_backlog_file(tmp_path: Path) -> Path:
    """Create a valid backlog file for testing."""
    f = tmp_path / "BACKLOG-2026-03-23-test.md"
    f.write_text(VALID_BACKLOG, encoding="utf-8")
    return f


@pytest.fixture
def invalid_backlog_file(tmp_path: Path) -> Path:
    """Create an invalid (minimal) backlog file for testing."""
    f = tmp_path / "BACKLOG-invalid.md"
    f.write_text(MINIMAL_INVALID_BACKLOG, encoding="utf-8")
    return f


@pytest.fixture
def empty_backlog_sections_file(tmp_path: Path) -> Path:
    """Create a backlog with empty required sections."""
    f = tmp_path / "BACKLOG-empty.md"
    f.write_text(EMPTY_SECTIONS_BACKLOG, encoding="utf-8")
    return f


@pytest.fixture
def placeholder_backlog_file(tmp_path: Path) -> Path:
    """Create a backlog with placeholder text."""
    f = tmp_path / "BACKLOG-placeholder.md"
    f.write_text(PLACEHOLDER_BACKLOG, encoding="utf-8")
    return f


@pytest.fixture
def valid_stories_dir(tmp_path: Path) -> Path:
    """Create a complete valid stories directory structure for testing."""
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()

    # Write backlog index
    (stories_dir / "BACKLOG-2026-03-23-patient-360.md").write_text(VALID_BACKLOG, encoding="utf-8")

    # Create epic directory with epic and story files
    epic_dir = stories_dir / "EPIC-01-infrastructure-setup"
    epic_dir.mkdir()
    (epic_dir / "EPIC-01.md").write_text(VALID_EPIC, encoding="utf-8")
    (epic_dir / "STORY-01-001-setup-duckdb.md").write_text(VALID_STORY, encoding="utf-8")

    return stories_dir
