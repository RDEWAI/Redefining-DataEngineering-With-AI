# Enterprise Data Dictionary

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Last Updated** | 2026-03-16 |
| **Owner** | Data Modeling Team |
| **Domain** | Healthcare — Patient 360 |

---

## 1. Approved Data Types

Only these data types are permitted in Silver and Gold layer schemas. Bronze preserves source types as-is.

| Approved Type | Usage | Notes |
|--------------|-------|-------|
| `VARCHAR` | Free-text, codes, identifiers | Prefer `VARCHAR(n)` with explicit length for bounded fields |
| `VARCHAR(n)` | Bounded strings | Use for enumerations, codes, short text |
| `DATE` | Calendar dates without time | Birth dates, effective dates, encounter dates |
| `TIMESTAMP` | Date + time | Event timestamps, ingestion times, modification times |
| `INTEGER` | Whole numbers | Counts, ages, sequence numbers |
| `BIGINT` | Large whole numbers | Surrogate keys, high-cardinality identifiers |
| `DECIMAL(p,s)` | Exact numeric with precision | Currency amounts (`DECIMAL(12,2)`), percentages (`DECIMAL(5,2)`) |
| `BOOLEAN` | True/false flags | `is_readmission`, `is_current`, `has_allergy` |

**Prohibited types** (use the approved alternative instead):

| Prohibited | Why | Use Instead |
|-----------|-----|-------------|
| `TEXT` | Unbounded — breaks predicate pushdown | `VARCHAR` or `VARCHAR(n)` |
| `FLOAT` / `DOUBLE` | Floating-point imprecision for financial/clinical data | `DECIMAL(p,s)` |
| `CHAR(n)` | Fixed-width padding wastes storage | `VARCHAR(n)` |
| `BLOB` / `BINARY` | Not suitable for analytical tables | Store externally, reference by path |
| `ARRAY` / `MAP` / `STRUCT` | Complex types complicate downstream consumers | Normalize into separate tables |

---

## 2. Standard Business Entity Definitions

Each entity has a canonical definition that all layers must respect.

| Entity | Definition | Source Table(s) | Silver Table | Gold Table(s) |
|--------|-----------|----------------|--------------|---------------|
| **Patient** | An individual receiving healthcare services. Uniquely identified by `patient_id` (natural key from source) | `patients` | `clinical_patients` | `dim_patient` |
| **Encounter** | A single interaction between a patient and a healthcare provider. Has a start and optional stop time, a class (inpatient, outpatient, etc.), and associated costs | `encounters` | `clinical_encounters` | `fact_encounter` |
| **Condition** | A diagnosed medical condition for a patient, with onset and optional resolution dates. Coded in SNOMED-CT | `conditions` | `clinical_conditions` | `fact_condition` |
| **Medication** | A prescribed medication for a patient encounter. Coded in RxNorm | `medications` | `clinical_medications` | (included in `fact_encounter` or separate `fact_medication`) |
| **Allergy** | A documented allergy or intolerance for a patient. Coded in SNOMED-CT | `allergies` | `clinical_allergies` | (included in `dim_patient` as flag or separate `bridge_patient_allergy`) |
| **Observation** | A clinical measurement or lab result (vitals, lab values). Coded in LOINC | `observations` | `clinical_observations` | (fact table or bridge, depending on grain) |
| **Procedure** | A medical procedure performed during an encounter. Coded in SNOMED-CT | `procedures` | `clinical_procedures` | `fact_procedure` |
| **Immunization** | A vaccine administered to a patient. Coded in CVX | `immunizations` | `clinical_immunizations` | (included in patient summary or separate fact) |
| **Provider** | A healthcare professional delivering services | `providers` | `reference_providers` | `dim_provider` |
| **Organization** | A healthcare facility or organization | `organizations` | `reference_organizations` | `dim_organization` |
| **Payer** | An insurance company or payer | `payers` | `reference_payers` | `dim_payer` |
| **Claim** | An insurance claim for services rendered during an encounter | `claims`, `claims_transactions` | `billing_claims` | `fact_claim` |
| **Care Plan** | A documented treatment plan for managing a patient's conditions | `careplans` | `clinical_careplans` | (bridge or fact, depending on analysis needs) |

---

## 3. Common Derived Columns

These derived columns are standard across ZenHealth projects. Use these definitions unless a DRD business rule specifies otherwise.

| Derived Column | Type | Formula | Business Rule |
|---------------|------|---------|---------------|
| `patient_age` | INTEGER | `DATEDIFF(year, birth_date, CURRENT_DATE)` | Age as of today; null if `birth_date` is null |
| `patient_age_at_encounter` | INTEGER | `DATEDIFF(year, birth_date, encounter_date)` | Age at time of encounter |
| `encounter_duration_hours` | DECIMAL(10,2) | `DATEDIFF(hour, start_date, stop_date)` | Null if `stop_date` is null (encounter still active) |
| `los_days` | INTEGER | `DATEDIFF(day, start_date, stop_date)` | Length of stay in days; 0 for same-day encounters |
| `is_readmission` | BOOLEAN | Inpatient encounter within 30 calendar days of a previous inpatient discharge | Per DRD BR-003; first encounter is never a readmission |
| `days_since_last_discharge` | INTEGER | Calendar days between current admission and most recent prior inpatient discharge | Null for first encounter |
| `is_active` | BOOLEAN | SCD Type 2 current version flag | `effective_to = '9999-12-31'` |
| `total_encounter_cost` | DECIMAL(12,2) | Sum of `BASE_ENCOUNTER_COST` + `TOTAL_CLAIM_COST` + `PAYER_COVERAGE` adjustments | Per DRD cost calculation rules |
| `condition_duration_days` | INTEGER | `DATEDIFF(day, onset_date, resolution_date)` | Null if condition is ongoing (no resolution date) |

---

## 4. Code System References

All coded clinical data must use standard terminologies. The modeler must preserve code columns and add human-readable description columns.

| Code System | Domain | Column Pattern | Description Column | Example Values |
|------------|--------|---------------|-------------------|----------------|
| **SNOMED-CT** | Conditions, Allergies, Procedures | `snomed_code` | `condition_description` | `38341003` (Hypertension) |
| **RxNorm** | Medications | `rxnorm_code` | `medication_description` | `855332` (Lisinopril 10mg) |
| **LOINC** | Observations, Lab Results | `loinc_code` | `observation_description` | `8302-2` (Body Height) |
| **CPT / HCPCS** | Procedures (billing) | `cpt_code` | `procedure_description` | `99213` (Office Visit) |
| **CVX** | Immunizations | `cvx_code` | `immunization_description` | `08` (Hepatitis B) |
| **ICD-10** | Diagnoses (billing) | `icd10_code` | `diagnosis_description` | `I10` (Essential Hypertension) |

**Rule**: Every table with coded data must include both the code column and a human-readable description column. The description is populated via lookup at the Silver layer.

---

## 5. Enumeration Standards

Standardized enumeration values for common categorical fields. Source values must be mapped to these canonical values at the Bronze-to-Silver boundary.

### 5.1 Encounter Class

| Canonical Value | Source Values (Synthea) | Description |
|----------------|------------------------|-------------|
| `INPATIENT` | `inpatient` | Hospital admission with overnight stay |
| `OUTPATIENT` | `outpatient` | Hospital visit without admission |
| `AMBULATORY` | `ambulatory` | Office or clinic visit |
| `EMERGENCY` | `emergency` | Emergency department visit |
| `WELLNESS` | `wellness` | Preventive care / annual checkup |
| `URGENTCARE` | `urgentcare` | Urgent care facility visit |
| `HOME` | `home` | Home health visit |
| `VIRTUAL` | `virtual` | Telehealth encounter |
| `OTHER` | Any unrecognized value | Catch-all — log DQ warning if >5% of batch |

**Transform**: `UPPER(TRIM(ENCOUNTERCLASS))`. Null handling: default to `UNKNOWN`, log DQ warning.

### 5.2 Gender

| Canonical Value | Source Values | Description |
|----------------|--------------|-------------|
| `MALE` | `M`, `Male`, `male` | Male |
| `FEMALE` | `F`, `Female`, `female` | Female |
| `OTHER` | `O`, `Other`, `other` | Other / non-binary |
| `UNKNOWN` | Null, empty, unrecognized | Unknown or not recorded |

**Transform**: `UPPER(TRIM(GENDER))` then map via CASE expression. Null handling: default to `UNKNOWN`.

### 5.3 Patient Status

| Canonical Value | Derivation | Description |
|----------------|-----------|-------------|
| `ALIVE` | `death_date IS NULL` | Patient is alive |
| `DECEASED` | `death_date IS NOT NULL` | Patient is deceased |

### 5.4 Condition Status

| Canonical Value | Derivation | Description |
|----------------|-----------|-------------|
| `ACTIVE` | `resolution_date IS NULL` | Condition is ongoing |
| `RESOLVED` | `resolution_date IS NOT NULL` | Condition has resolved |

---

## 6. Null Handling Defaults

Default null handling rules by field criticality. These apply unless a DRD business rule specifies otherwise.

| Criticality | Null Action | DQ Severity | Examples |
|------------|------------|-------------|----------|
| **Critical** | Reject record | CRITICAL | `patient_id`, `encounter_id`, `start_date` — pipeline halts for the affected table |
| **Important** | Default value + DQ warning | WARNING | `birth_date` (null → null, but flag), `encounter_class` (null → `UNKNOWN`), `gender` (null → `UNKNOWN`) |
| **Optional** | Pass through null | INFO (monitoring only) | `death_date`, `stop_date`, `allergy_severity`, `medication_reason` |
| **Derived** | Null if input is null | No DQ action | `patient_age` (null if `birth_date` null), `encounter_duration_hours` (null if `stop_date` null) |

---

## 7. Key Relationship Standards

| Relationship Type | Convention | Example |
|------------------|-----------|---------|
| **Natural key (source)** | `{entity}_id` column, VARCHAR | `patient_id VARCHAR NOT NULL` |
| **Surrogate key (Gold)** | `{entity}_sk` column, BIGINT, auto-generated | `patient_sk BIGINT NOT NULL` |
| **Foreign key** | Column name matches the referenced PK/SK column | `fact_encounter.patient_sk` → `dim_patient.patient_sk` |
| **Composite key** | Documented as tuple in schema definition | `(patient_id, encounter_id, condition_code)` |
| **Degenerate dimension** | Natural key stored directly in fact table | `fact_encounter.encounter_id` (no separate dim table needed) |
