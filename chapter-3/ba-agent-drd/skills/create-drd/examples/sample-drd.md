# Data Requirements Document: Patient 360 Search

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | 2026-01-29 |
| **Last Modified** | 2026-01-29 |
| **Author** | BA Agent |
| **Status** | Draft |
| **Business Sponsor** | Dr. Sarah Chen, Chief Medical Officer |

---

## Executive Summary

The Patient 360 initiative aims to provide clinicians and support staff with a single search interface to access a complete view of any patient. By typing a patient's name, users will see demographics, recent visits, active diagnoses, current medications, lab results, allergies, and billing information in one place. This eliminates the need to navigate multiple systems and reduces time spent looking up patient information from an average of 8 minutes to under 30 seconds.

---

## 1. Business Context

### 1.1 Business Request

Hospital leadership has identified that clinicians spend significant time switching between multiple systems (EHR, lab system, billing portal) to piece together a patient's full picture before appointments. The Patient 360 initiative will consolidate data from all source systems into a unified search experience, similar to how a web search engine returns comprehensive results from a single query.

### 1.2 Business Objectives

- Reduce clinician time spent on patient lookups from 8 minutes to under 30 seconds
- Provide a single search interface for all patient information across departments
- Surface critical alerts (allergies, overdue screenings, readmission risk) proactively
- Enable care coordinators to identify gaps in care without manual chart review
- Support billing staff with quick access to encounter and claims history

### 1.3 Success Criteria

- 90% of patient searches return complete results within 2 seconds
- Clinician satisfaction score above 4.0/5.0 in post-launch survey
- 50% reduction in time spent on pre-appointment chart review
- Zero missed allergy alerts in the first 90 days post-launch
- All active patients (estimated 50,000) searchable from day one

### 1.4 Stakeholders

| Name | Role | Interest | Contact |
|------|------|----------|---------|
| Dr. Sarah Chen | Chief Medical Officer | Clinical quality, patient safety | s.chen@hospital.org |
| Michael Torres | Chief Information Officer | System integration, performance | m.torres@hospital.org |
| Lisa Park | Clinical Operations Manager | Workflow efficiency, care gaps | l.park@hospital.org |
| James Wright | Revenue Cycle Director | Billing accuracy, claims tracking | j.wright@hospital.org |
| Dr. Amy Nguyen | Primary Care Physician | Daily patient lookup workflow | a.nguyen@hospital.org |

---

## 2. Source Discovery

### 2.1 Source Systems

#### Electronic Health Record (EHR) - Synthea

- **System Type**: Relational database (DuckDB)
- **Owner**: Health IT Department
- **Access Method**: SQL queries via DuckDB connection
- **Connection Details**: `data/duckdb/raw.db`, schema `synthea`

### 2.2 Available Tables and Datasets

| Source System | Table/Dataset | Description | Estimated Row Count | Update Frequency |
|---------------|---------------|-------------|---------------------|------------------|
| Synthea EHR | patients | Patient demographics (name, DOB, address, race, ethnicity) | 1,000 | Daily |
| Synthea EHR | encounters | Visit records (date, type, provider, reason, cost) | 50,000 | Real-time |
| Synthea EHR | conditions | Diagnoses (SNOMED code, description, onset, resolution) | 25,000 | Real-time |
| Synthea EHR | medications | Prescriptions (RxNorm code, description, start, stop, cost) | 30,000 | Real-time |
| Synthea EHR | observations | Lab results and vitals (LOINC code, value, units, date) | 200,000 | Daily |
| Synthea EHR | procedures | Procedures performed (SNOMED code, date, cost) | 40,000 | Real-time |
| Synthea EHR | allergies | Patient allergies (SNOMED code, description, onset) | 5,000 | Real-time |
| Synthea EHR | immunizations | Vaccination records (CVX code, date, cost) | 20,000 | Weekly |
| Synthea EHR | careplans | Active care plans (code, description, start, stop) | 15,000 | Daily |
| Synthea EHR | claims | Insurance claims (payer, amount, status) | 60,000 | Daily |

### 2.3 Data Volume Estimates

| Metric | Estimate | Notes |
|--------|----------|-------|
| Total patients | 1,000 | Synthea-generated population |
| Total encounters | 50,000 | ~50 encounters per patient average |
| Daily new encounters | 200 | Based on current admission rate |
| Total storage | 500 MB | All tables combined in DuckDB |
| Query result size | < 1 MB | Typical patient 360 response |

### 2.4 Access and Security

- **Synthea EHR**: Read-only SQL access via DuckDB. No authentication required for local development. Production will require role-based access control (RBAC) with clinical staff credentials.

---

## 3. Data Quality Expectations

### 3.1 Critical Fields

| Field Name | Source Table | Why Critical | Allowed Null? | Expected Format |
|------------|-------------|--------------|---------------|-----------------|
| patient_id | patients | Primary identifier for all joins | No | UUID format |
| first_name | patients | Required for patient search | No | Text, 1-100 chars |
| last_name | patients | Required for patient search | No | Text, 1-100 chars |
| birthdate | patients | Patient identification and age calculation | No | YYYY-MM-DD |
| encounter_id | encounters | Links visits to patients | No | UUID format |
| encounter_date | encounters | Timeline ordering | No | YYYY-MM-DD |
| condition_code | conditions | Clinical diagnosis identification | No | SNOMED CT code |
| medication_code | medications | Prescription identification | No | RxNorm code |
| allergy_code | allergies | Safety alert trigger | No | SNOMED CT code |

### 3.2 Valid Value Ranges

| Field Name | Valid Range / Allowed Values | Action if Out of Range |
|------------|------------------------------|------------------------|
| birthdate | 1900-01-01 to today | Reject record, flag for review |
| encounter_date | 2000-01-01 to today + 1 year | Reject record, flag for review |
| total_claim_cost | 0.00 to 10,000,000.00 | Flag for manual review |
| patient_age | 0 to 130 | Flag record, likely data error |
| observation_value | Depends on LOINC code | Flag for clinical review |

### 3.3 Referential Integrity Requirements

| Child Table | Child Field | Parent Table | Parent Field | Required? |
|-------------|-------------|--------------|--------------|-----------|
| encounters | patient_id | patients | id | Yes |
| conditions | patient_id | patients | id | Yes |
| conditions | encounter_id | encounters | id | Yes |
| medications | patient_id | patients | id | Yes |
| observations | patient_id | patients | id | Yes |
| observations | encounter_id | encounters | id | Yes |
| allergies | patient_id | patients | id | Yes |
| procedures | patient_id | patients | id | Yes |
| claims | patient_id | patients | id | Yes |

### 3.4 Tolerance Thresholds

| Quality Metric | Acceptable Threshold | Measurement Method |
|----------------|----------------------|--------------------|
| Missing patient_id | 0% (zero tolerance) | Count of null patient_id across all tables |
| Duplicate patient records | < 0.1% | Exact match on name + DOB + SSN |
| Orphaned encounters | < 0.5% | Encounters with no matching patient |
| Stale observation data | < 5% over 7 days old | Count observations not updated in 7 days |
| Missing allergy records | 0% for known allergies | Cross-reference with clinical notes |

---

## 4. Consumer Requirements

### 4.1 Data Consumers

| Consumer | Department | Use Case | Access Pattern |
|----------|------------|----------|----------------|
| Physicians | Clinical | Pre-appointment patient review, point-of-care lookup | Real-time search, 50-100 lookups/day per user |
| Nurses | Clinical | Medication verification, allergy checks | Real-time search, 30-50 lookups/day per user |
| Care Coordinators | Care Management | Care gap identification, follow-up scheduling | Batch review, 20-30 patients/day |
| Billing Staff | Revenue Cycle | Claims verification, payment tracking | On-demand search, 40-60 lookups/day per user |
| Department Heads | Administration | Utilization reports, quality metrics | Weekly aggregate queries |

### 4.2 Access Patterns

#### Physicians

- **Query Type**: Single patient lookup by name, then drill into encounters/diagnoses/medications
- **Frequency**: 50-100 per day per physician
- **Typical Data Volume Requested**: 1 patient profile with last 12 months of encounters
- **Peak Usage Times**: 7:00-9:00 AM (pre-clinic), 12:00-1:00 PM (between sessions)

#### Care Coordinators

- **Query Type**: Patient panel review with care gap filters
- **Frequency**: 20-30 patient reviews per day
- **Typical Data Volume Requested**: Panel of 20-50 patients with screening status
- **Peak Usage Times**: 9:00 AM - 3:00 PM (business hours)

### 4.3 Service Level Agreements (SLAs)

| SLA Metric | Target | Measurement | Escalation |
|------------|--------|-------------|------------|
| Search response time | < 2 seconds for 90th percentile | Application performance monitoring | Page on-call engineer if > 5 seconds for 5 minutes |
| Data freshness | < 1 hour for clinical data | Timestamp comparison against source | Alert data engineering team |
| System availability | 99.5% uptime during business hours (6 AM - 10 PM) | Uptime monitoring | Page on-call, notify CIO if downtime > 30 minutes |
| Data completeness | 100% of active patients searchable | Daily reconciliation count | Alert data quality team |

### 4.4 Data Freshness Requirements

| Consumer / Use Case | Maximum Acceptable Latency | Refresh Cadence |
|---------------------|----------------------------|-----------------|
| Physician patient lookup | 1 hour | Near real-time (streaming preferred) |
| Allergy alerts | 15 minutes | Near real-time (critical safety data) |
| Billing and claims | 24 hours | Daily batch load |
| Care gap analysis | 24 hours | Daily batch load |
| Lab results | 1 hour | Hourly incremental |

---

## 5. Business Rules

### 5.1 Default Values

| Field | Default Value | When Applied | Business Justification |
|-------|---------------|--------------|------------------------|
| encounter_status | "Active" | New encounter without explicit status | Encounters are active until discharged |
| allergy_severity | "Moderate" | Allergy recorded without severity | Clinical safety: assume moderate until confirmed |
| claim_status | "Pending" | New claim without adjudication | Claims start as pending until payer responds |
| data_currency_flag | "Current" | Data refreshed within SLA window | Indicates data meets freshness requirements |

### 5.2 Calculations and Derivations

#### Patient Age

- **Formula / Logic**: `FLOOR(DATEDIFF('year', birthdate, CURRENT_DATE))`
- **Input Fields**: `patients.birthdate`
- **Output Field**: `patient_age` (derived, not stored)
- **Business Purpose**: Display patient age on search results without requiring mental math
- **Example**: Patient born 1985-03-15, today 2026-01-29 = 40 years old

#### Total Visit Cost

- **Formula / Logic**: `SUM(encounter_cost + procedure_costs + medication_costs)`
- **Input Fields**: `encounters.total_claim_cost`, `procedures.base_cost`, `medications.total_cost`
- **Output Field**: `total_visit_cost` (derived per encounter)
- **Business Purpose**: Give billing staff a quick cost summary per visit
- **Example**: Encounter cost $150 + Procedure $500 + Medications $75 = $725 total

#### Readmission Flag

- **Formula / Logic**: If a patient has an inpatient encounter within 30 days of a prior inpatient discharge, flag as readmission
- **Input Fields**: `encounters.start`, `encounters.stop`, `encounters.encounterclass`
- **Output Field**: `is_readmission` (boolean, derived)
- **Business Purpose**: Alert care coordinators to patients at risk, supports quality reporting
- **Example**: Patient discharged Jan 5, readmitted Jan 20 = flagged as readmission

### 5.3 Transformation Rules

- **Name standardization**: Convert patient names to title case (e.g., "john smith" becomes "John Smith")
- **Date formatting**: Display all dates as "Month DD, YYYY" for user-facing views (e.g., "January 29, 2026")
- **Code descriptions**: Always show human-readable descriptions alongside medical codes (e.g., "J06.9 - Acute upper respiratory infection")
- **Currency formatting**: Display all costs as USD with two decimal places (e.g., "$1,234.56")

### 5.4 Edge Cases and Exceptions

- **Scenario**: Patient has no recorded encounters
  - **Expected Behavior**: Display demographics and a message "No encounter history found" instead of an empty section
  - **Rationale**: New patients or those recently transferred may have no local history

- **Scenario**: Patient has an allergy with no recorded severity
  - **Expected Behavior**: Display the allergy with "Severity: Unknown - Please verify" highlighted in yellow
  - **Rationale**: Patient safety requires visibility even with incomplete data

- **Scenario**: Duplicate patient records (same name, different IDs)
  - **Expected Behavior**: Show all matching records with a banner "Multiple records found - possible duplicate" and display key identifiers (DOB, SSN last 4) to help the user distinguish
  - **Rationale**: Merging records requires clinical review; system should surface the issue, not hide it

- **Scenario**: Search returns more than 100 results
  - **Expected Behavior**: Show first 100 results sorted by most recent encounter, with a prompt to refine the search
  - **Rationale**: Prevents performance issues and encourages specific searches

---

## 6. Assumptions and Open Questions

### 6.1 Assumptions

- All Synthea data tables are loaded and current in the DuckDB database
- Patient search will initially support name-based lookup; SSN/MRN search is a future enhancement
- The system operates in a single time zone (hospital local time)
- HIPAA compliance requirements will be addressed in the security architecture document (separate from this DRD)
- The initial release targets 1,000 patients; scaling to 500,000+ is planned for Phase 2

### 6.2 Open Questions

| # | Question | Assigned To | Due Date | Status |
|---|----------|-------------|----------|--------|
| 1 | Should lab results show only the most recent value per test, or full history? | Dr. Sarah Chen | 2026-02-15 | Open |
| 2 | What role-based access restrictions apply? (e.g., billing cannot see clinical notes) | Michael Torres | 2026-02-10 | Open |
| 3 | Should the search support fuzzy matching for misspelled names? | Lisa Park | 2026-02-05 | Open |
| 4 | What is the data retention policy for historical encounters? | Legal / Compliance | 2026-02-20 | Open |
| 5 | Will external lab results (from partner facilities) be included? | Dr. Amy Nguyen | 2026-02-15 | Open |

---

## 7. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | BA Agent | Initial DRD creation from stakeholder inputs |

---

## 8. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Business Sponsor | Dr. Sarah Chen | _Pending_ | |
| Technical Lead | Michael Torres | _Pending_ | |
| Clinical Operations | Lisa Park | _Pending_ | |
| Data Engineering Lead | _TBD_ | _Pending_ | |
