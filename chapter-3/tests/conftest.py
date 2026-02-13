"""Shared fixtures for DRD validator tests."""

from __future__ import annotations

import pytest
from pathlib import Path


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
| HIPAA | All patient data | PHI protection, minimum necessary access, breach notification | Encrypt at rest and in transit; role-based access control |

### 7.2 Data Classification

| Data Element | Classification Level | Handling Requirements |
|-------------|---------------------|----------------------|
| Patient demographics | PHI - Confidential | Encrypted storage, access logging, no external sharing |
| Clinical records | PHI - Confidential | Encrypted storage, access logging, clinician-only access |

### 7.3 Retention Requirements

| Data Category | Retention Period | Deletion Method | Legal Basis |
|--------------|-----------------|-----------------|-------------|
| Medical records | 7 years minimum | Secure deletion with audit trail | State medical records retention law |

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
