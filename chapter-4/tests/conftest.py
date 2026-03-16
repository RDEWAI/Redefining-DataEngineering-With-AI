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

## 1. Design Overview

### Architecture Pattern

**Selected**: Medallion (Lakehouse) Architecture

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

```mermaid
flowchart LR
    SRC[Synthea EHR] --> BRZ[Bronze Layer]
    BRZ --> SLV[Silver Layer]
    SLV --> GLD[Gold Layer]
    GLD --> CLIN[Clinical Dashboard]
    GLD --> ANLYT[Analytics Team]
```

---

## 2. Layer Specifications

### 2.1 Bronze Layer

**Purpose**: Raw ingestion of all 18 Synthea tables with metadata.

**Responsibilities**:
- Load source tables as-is, preserving original schema
- Add metadata: `_ingested_at`, `_source_batch_id`, `_source_file`
- Partition by `ds` (load date) for idempotent re-runs
- Store as Delta Lake tables

**DQ at this layer**: Schema validation only — confirm all expected
columns are present and types match the source.

### 2.2 Silver Layer

**Purpose**: Cleansed and conformed business entities.

**Responsibilities**:
- Type standardization (string dates to DATE/TIMESTAMP)
- Null handling per DRD business rules (Section 5)
- Deduplication using surrogate keys
- Name standardization (snake_case, consistent prefixes)
- Business rule implementation (encounter classification)

### 2.3 Gold Layer

**Purpose**: Dimensional model for analytics and clinical use.

**Responsibilities**:
- Fact tables: `fact_encounter`, `fact_condition`
- Dimensions: `dim_patient` (SCD2), `dim_provider` (SCD1)
- Aggregations: `patient_summary` for Patient 360 view
- Readmission scoring per DRD BR-003

---

## 3. Technology Stack

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Processing | Apache Spark | 4.1.1 | Team proficiency: High (DRD Section 2) |
| Table Format | Delta Lake | 4.1.0 | ACID, idempotent writes, MERGE |
| Metastore | Unity Catalog OSS | 0.4.0 | Catalog/schema management |
| Lineage | OpenLineage + Marquez | 1.44.0 | HIPAA audit trail (DRD 7.5) |
| DQ Framework | Spark Expectations | 2.0.0 | Rule-based enforcement |
| Language | Python (PySpark) | 3.10-3.12 | Team proficiency: High |
| Orchestration | Make + scripts | N/A | Minimal overhead for local dev |

---

## 4. Integration Points

### Source Connections

| Source | Method | Credentials | Refresh |
|--------|--------|-------------|---------|
| Synthea CSV | File-based ingestion | Filesystem | Per pipeline run |

### Target Connections

| Consumer | Method | Access Pattern |
|----------|--------|---------------|
| Clinical Dashboard | Direct Delta query | Real-time, 50-100/day |
| Analytics Team | SQL via Unity Catalog | Batch, daily reports |

---

## 5. Capacity Planning

### Current Volumes

| Table | Row Count | Size (est.) |
|-------|-----------|-------------|
| patients | 5,767 | 2 MB |
| encounters | 150,000 | 30 MB |
| observations | 4,400,000 | 800 MB |
| Total (all 18) | ~5,000,000 | ~1 GB |

### Growth Projections

| Timeframe | Patients | Total Rows | Storage |
|-----------|----------|------------|---------|
| Current | 5,767 | 5M | 1 GB |
| 12 months | 100,000 | 87M | 17 GB |
| 24 months | 500,000 | 435M | 87 GB |

### Scaling Triggers

- At 1M patients: evaluate Spark cluster (currently local mode)
- At 10 GB bronze: evaluate S3 storage (currently local filesystem)
- Cost: $0/month (local dev); ~$200/month projected cloud

---

## 6. Security Architecture

### HIPAA Compliance (DRD Section 7.1)

- **Encryption at rest**: Delta Lake on encrypted filesystem
- **Encryption in transit**: TLS for all API connections
- **RBAC**: Unity Catalog ACLs per consumer group
- **PHI masking**: SSN, drivers license dropped at silver layer
- **Audit logging**: OpenLineage captures all data access events

### Data Classification

| Level | Examples | Controls |
|-------|----------|----------|
| PHI - Confidential | Patient demographics | Encrypted, RBAC, logged |
| Internal | Encounter counts | RBAC only |

---

## 7. Disaster Recovery

### Backup Strategy

- Delta Lake provides time-travel (30-day retention)
- Source CSVs are immutable — re-ingestible at any time
- UC metadata in Docker volume — backup via `docker export`

### RTO/RPO

| Metric | Target | Basis |
|--------|--------|-------|
| RPO | 6 hours | DRD SLA: clinical data within 1 hour |
| RTO | 2 hours | Bronze re-ingest + silver rebuild |

---

## 8. CDC Strategy

### Per-Source Change Detection

| Table | Method | Fallback | Schema Evolution |
|-------|--------|----------|-----------------|
| patients | Full snapshot | N/A (small table) | mergeSchema |
| encounters | Timestamp-based | Full snapshot | mergeSchema |
| observations | Timestamp-based | Partition reload | mergeSchema |
| All others | Full snapshot | N/A | mergeSchema |

**Justification**: Synthea is a batch source with no change log.
Timestamp-based incremental for large tables (encounters, observations)
because full snapshot is too slow at projected volumes. Small tables
(<10K rows) use full snapshot for simplicity.

### Schema Evolution

- `mergeSchema = true` for bronze ingestion
- Silver/Gold: schema changes require model version bump

---

## Decision Log

| # | Decision | Options | Selected | Rationale |
|---|----------|---------|----------|-----------|
| 1 | Architecture pattern | Medallion, Lambda, Data Vault | Medallion | Mixed latency |
| 2 | Processing engine | Spark, DuckDB, dbt | Spark | Team proficiency, Delta Lake |
| 3 | CDC approach | Full snapshot, timestamp, CDC | Mixed | Volume-dependent per table |

---

## Open Questions

| # | Question | Owner | Due Date | Status |
|---|----------|-------|----------|--------|
| 1 | Cloud deployment timeline | CIO | 2026-04-01 | Open |

---

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Technical Lead | _Pending_ | | |
"""

MINIMAL_INVALID_HLD = """\
# High-Level Design: Incomplete

## 1. Design Overview

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

## 1. Design Overview

Test overview.

## 2. Layer Specifications

## 3. Technology Stack

## 4. Integration Points

## 5. Capacity Planning

## 6. Security Architecture

## 7. Disaster Recovery

## 8. CDC Strategy
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

## 1. Design Overview

[TO BE DETERMINED - requires input from architect]

Medallion architecture selected because DRD specifies mixed latency.

```mermaid
flowchart LR
    SRC --> BRZ --> SLV --> GLD
```

## 2. Layer Specifications

### Bronze Layer
Raw ingestion of source tables.

### Silver Layer
Cleansed and conformed data.

### Gold Layer
Dimensional model.

## 3. Technology Stack

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Processing | Spark | 4.1.1 | Team proficiency |
| Storage | Delta Lake | 4.1.0 | ACID writes |
| Metastore | Unity Catalog | 0.4.0 | Catalog management |

## 4. Integration Points

Source: Synthea CSV via file-based ingestion.

## 5. Capacity Planning

Current volume: 5,767 patients, ~5M rows total.
Growth: 100K patients in 12 months.
Cost: $0 local, ~$200/month cloud.

## 6. Security Architecture

HIPAA compliance required per DRD Section 7.1.
PHI fields encrypted at rest.

## 7. Disaster Recovery

Delta Lake time-travel provides 30-day recovery window.
RTO: 2 hours. RPO: 6 hours.

## 8. CDC Strategy

Full snapshot for small tables. Timestamp-based for large tables.
Snapshot is acceptable because DRD projects <100K patients initially.
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
    bronze_patients ||--|| silver_patients : cleanses
    silver_patients ||--|| dim_patient : conforms
    bronze_encounters ||--|| silver_encounters : cleanses
    silver_encounters ||--|| fact_encounter : conforms
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
    transform: "CAST(BIRTHDATE AS DATE)"
    null_handling: "pass through null, flag WARNING"
    business_rule: BR-001
  - name: first_name
    type: VARCHAR
    nullable: true
    source: bronze.patients.FIRST
    transform: "INITCAP(TRIM(FIRST))"
  - name: last_name
    type: VARCHAR
    nullable: false
    source: bronze.patients.LAST
    transform: "INITCAP(TRIM(LAST))"
  - name: gender
    type: VARCHAR(10)
    nullable: false
    source: bronze.patients.GENDER
    transform: "UPPER(TRIM(GENDER))"
    enum: [MALE, FEMALE, OTHER, UNKNOWN]
    business_rule: BR-002
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
    transform: "CAST(START AS TIMESTAMP)"
  - name: encounter_end
    type: TIMESTAMP
    nullable: true
    source: bronze.encounters.STOP
    transform: "CAST(STOP AS TIMESTAMP)"
  - name: encounter_class
    type: VARCHAR
    nullable: true
    source: bronze.encounters.ENCOUNTERCLASS
    transform: "UPPER(TRIM(ENCOUNTERCLASS))"
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
    transform: "first_name || ' ' || last_name"
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

### Compression

- Delta Lake default (Snappy) for all layers

---

## 8. Traceability Matrix

| Gold Column | Silver | Bronze | Transform |
|-------------|--------|--------|-----------|
| dim_patient.full_name | first_name+last_name | FIRST+LAST | INITCAP |
| dim_patient.birth_date | birth_date | BIRTHDATE | CAST DATE |
| fact_encounter.patient_sk | patient_id | PATIENT | SK lookup |

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

| Gold Column | Silver Source | Bronze Source | Raw Source | Transform |
|-------------|-------------|-------------|-----------|-----------|
| dim_patient.patient_sk | patients.patient_id | patients.Id | Synthea | SK generation |

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
