# Data Model: DuckDB CSV Data Loader

**Feature**: 002-duckdb-csv-loader
**Date**: 2025-12-01
**Purpose**: Define data entities and relationships for CSV loading feature

## Overview

This feature creates 18 DuckDB tables that mirror the structure of Synthea healthcare CSV files. The tables represent a healthcare data model with patients, encounters, clinical observations, billing claims, and related entities. The schema is automatically inferred from CSV files using DuckDB's `auto_detect` feature.

## Entity Relationships

```text
                    ┌─────────────┐
                    │  patients   │ (Demographics)
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼──────┐   ┌────▼─────┐   ┌─────▼──────┐
    │ encounters │   │allergies │   │  devices   │
    └──────┬─────┘   └──────────┘   └────────────┘
           │
    ┌──────┼──────────────┬─────────────┬──────────────┐
    │      │              │             │              │
┌───▼───┐ │  ┌──────────┐ │ ┌─────────┐ │ ┌──────────┐
│claims │ │  │procedures│ │ │conditions│ │ │careplans │
└───┬───┘ │  └──────────┘ │ └─────────┘ │ └──────────┘
    │     │                │             │
┌───▼───────────┐   ┌─────▼──────┐   ┌──▼────────┐
│claims_        │   │observations│   │medications│
│transactions   │   └────────────┘   └───────────┘
└───────────────┘

    ┌──────────────┐   ┌──────────────┐   ┌──────────┐
    │organizations │   │  providers   │   │  payers  │
    └──────────────┘   └──────────────┘   └──────────┘

    ┌──────────────┐   ┌──────────────┐   ┌──────────┐
    │imaging_studies│   │immunizations │   │ supplies │
    └──────────────┘   └──────────────┘   └──────────┘

    ┌──────────────────┐
    │payer_transitions │
    └──────────────────┘
```

## Core Entities

### Patient Domain

#### patients
**Purpose**: Core patient demographics and identifiers

**Key Attributes** (inferred from Synthea CSV format):
- Patient ID (primary key)
- First name, last name
- Date of birth
- Gender
- Race, ethnicity
- Address (street, city, state, zip)
- SSN, driver's license, passport
- Marital status

**Relationships**:
- One patient has many encounters
- One patient has many allergies
- One patient has many devices
- One patient has many conditions
- One patient has many medications
- One patient has many payer transitions

**Validation Rules**:
- Patient ID must be unique
- Date of birth must be in the past

---

### Clinical Encounters

#### encounters
**Purpose**: Healthcare visits and interactions

**Key Attributes**:
- Encounter ID (primary key)
- Patient ID (foreign key)
- Provider ID (foreign key)
- Organization ID (foreign key)
- Payer ID (foreign key)
- Start date/time, end date/time
- Encounter class (ambulatory, emergency, inpatient, etc.)
- Encounter type code
- Reason code/description
- Cost

**Relationships**:
- Many encounters belong to one patient
- One encounter has many observations
- One encounter has many procedures
- One encounter has many medications
- One encounter has many claims
- Many encounters reference one provider
- Many encounters reference one organization
- Many encounters reference one payer

**Validation Rules**:
- Start date must be before or equal to end date
- Patient ID must exist in patients table

---

### Clinical Data

#### observations
**Purpose**: Medical measurements and test results (vital signs, lab results, etc.)

**Key Attributes**:
- Observation ID
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Date/time
- Observation code (LOINC)
- Description
- Value (numeric or text)
- Units
- Type (vital sign, lab, assessment, etc.)

**Size**: Largest clinical table (~772MB)

**Relationships**:
- Many observations belong to one patient
- Many observations belong to one encounter

**Validation Rules**:
- Date must align with encounter date range
- Numeric values should have units

---

#### conditions
**Purpose**: Patient diagnoses and health conditions

**Key Attributes**:
- Condition ID
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Start date, end date
- Condition code (SNOMED-CT)
- Description

**Relationships**:
- Many conditions belong to one patient
- Many conditions belong to one encounter

---

#### procedures
**Purpose**: Medical procedures performed

**Key Attributes**:
- Procedure ID
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Date/time
- Procedure code (SNOMED-CT)
- Description
- Cost

**Relationships**:
- Many procedures belong to one patient
- Many procedures belong to one encounter

---

#### medications
**Purpose**: Prescribed medications

**Key Attributes**:
- Medication ID
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Payer ID (foreign key)
- Start date, end date
- Medication code (RxNorm)
- Description
- Cost
- Dispenses
- Total cost

**Relationships**:
- Many medications belong to one patient
- Many medications belong to one encounter

---

#### allergies
**Purpose**: Patient allergies and adverse reactions

**Key Attributes**:
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Start date, end date
- Allergy code (SNOMED-CT)
- Description

**Relationships**:
- Many allergies belong to one patient

---

#### immunizations
**Purpose**: Vaccination records

**Key Attributes**:
- Immunization ID
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Date
- Vaccine code (CVX)
- Description
- Cost

**Relationships**:
- Many immunizations belong to one patient
- Many immunizations belong to one encounter

---

#### careplans
**Purpose**: Care management plans

**Key Attributes**:
- Care plan ID
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Start date, end date
- Care plan code (SNOMED-CT)
- Description
- Reason code/description

**Relationships**:
- Many care plans belong to one patient
- Many care plans belong to one encounter

---

#### devices
**Purpose**: Medical devices assigned to patients (pacemakers, prosthetics, etc.)

**Key Attributes**:
- Device ID
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Start date, end date
- Device code (SNOMED-CT)
- Description
- UDI (Unique Device Identifier)

**Relationships**:
- Many devices belong to one patient

---

#### imaging_studies
**Purpose**: Radiology and imaging procedures

**Key Attributes**:
- Study ID
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Date/time
- Modality code (DICOM)
- Description
- SOP class UID
- Body site code

**Relationships**:
- Many imaging studies belong to one patient
- Many imaging studies belong to one encounter

---

### Financial/Administrative

#### claims
**Purpose**: Insurance claim records

**Key Attributes**:
- Claim ID (primary key)
- Patient ID (foreign key)
- Provider ID (foreign key)
- Organization ID (foreign key)
- Encounter ID (foreign key)
- Billable period start/end
- Total claim cost
- Current illness date
- Status (billed, paid, etc.)

**Relationships**:
- Many claims belong to one patient
- Many claims belong to one encounter
- One claim has many claim transactions

---

#### claims_transactions
**Purpose**: Individual line items on insurance claims

**Key Attributes**:
- Transaction ID
- Claim ID (foreign key)
- Charge ID (foreign key)
- Patient ID (foreign key)
- Service type
- Line item cost
- Payment details

**Size**: Largest table in dataset (~2.5GB)

**Relationships**:
- Many transactions belong to one claim

---

#### supplies
**Purpose**: Medical supplies used during care

**Key Attributes**:
- Patient ID (foreign key)
- Encounter ID (foreign key)
- Date
- Supply code (SNOMED-CT)
- Description
- Quantity

**Relationships**:
- Many supplies used in one encounter

---

### Reference Data

#### organizations
**Purpose**: Healthcare facilities (hospitals, clinics, etc.)

**Key Attributes**:
- Organization ID (primary key)
- Name
- Address (street, city, state, zip)
- Phone number
- Revenue
- Utilization

**Relationships**:
- One organization hosts many encounters

---

#### providers
**Purpose**: Healthcare professionals (doctors, nurses, etc.)

**Key Attributes**:
- Provider ID (primary key)
- Organization ID (foreign key)
- Name
- Gender
- Specialty
- Address

**Relationships**:
- Many providers belong to one organization
- One provider conducts many encounters

---

#### payers
**Purpose**: Insurance companies and payers

**Key Attributes**:
- Payer ID (primary key)
- Name
- Address (street, city, state, zip)
- Phone number
- Revenue
- Amount covered
- Amount uncovered
- Encounters covered

**Relationships**:
- One payer covers many encounters
- One payer covers many medications

---

#### payer_transitions
**Purpose**: Changes in patient insurance coverage

**Key Attributes**:
- Patient ID (foreign key)
- Start year, end year
- Payer ID (foreign key)
- Ownership (self, guardian, etc.)

**Relationships**:
- Many transitions belong to one patient
- Many transitions reference one payer

---

## Schema Inference Strategy

All table schemas are automatically inferred by DuckDB's `auto_detect=true` feature during CSV import. This approach:

1. **Scans first N rows** (default: 20,480 rows) to detect:
   - Column names from CSV header row
   - Data types (INTEGER, DOUBLE, VARCHAR, DATE, TIMESTAMP)
   - Null handling
   - Date/timestamp formats

2. **Applies detected schema** to full CSV file during streaming import

3. **Handles edge cases**:
   - Mixed types default to VARCHAR
   - Empty strings become NULLs
   - Date formats auto-detected from samples

## Data Quality Assumptions

Based on spec's "Out of Scope" section, the following are assumed:

- CSV files follow Synthea's standard format (comma-delimited, UTF-8, header row)
- Data is already validated by Synthea generator
- No data cleansing or transformation required
- Referential integrity is logical but not enforced (no foreign key constraints)

## Storage Estimates

| Table | Approximate Size | Row Count (typical) |
|-------|------------------|---------------------|
| claims_transactions | ~2.5GB | 5-10M rows |
| observations | ~772MB | 3-5M rows |
| encounters | ~200-400MB | 500k-1M rows |
| medications | ~100-200MB | 500k-1M rows |
| conditions | ~50-100MB | 200k-500k rows |
| procedures | ~50-100MB | 200k-500k rows |
| patients | ~10-50MB | 100k-200k rows |
| Other tables | <10MB each | <100k rows each |
| **Total** | **~4.3GB** | **~15-20M rows** |

## Post-Loading Schema Validation

After loading, the following can be verified:

```sql
-- Verify all tables exist
SELECT table_name, estimated_size
FROM duckdb_tables()
WHERE table_name IN (
    'patients', 'encounters', 'observations', 'claims', 'claims_transactions',
    'procedures', 'medications', 'conditions', 'imaging_studies', 'careplans',
    'payer_transitions', 'allergies', 'devices', 'immunizations',
    'organizations', 'providers', 'payers', 'supplies'
);

-- Verify row counts
SELECT 'patients' AS table_name, COUNT(*) AS row_count FROM patients
UNION ALL
SELECT 'encounters', COUNT(*) FROM encounters
-- ... repeat for all tables
```

This validation will be part of the integration tests.
