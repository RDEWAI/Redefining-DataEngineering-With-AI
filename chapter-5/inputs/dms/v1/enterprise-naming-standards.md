# Enterprise Naming Standards

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Last Updated** | 2026-03-16 |
| **Owner** | Data Governance Team |
| **Scope** | All data platform schemas — Bronze, Silver, Gold |

---

## 1. Table Naming Rules

| Layer | Convention | Pattern | Examples |
|-------|-----------|---------|----------|
| Bronze | Source-aligned, prefixed by source system | `{source}_{table}` | `synthea_patients`, `synthea_encounters` |
| Silver | Domain-prefixed, business entity name | `{domain}_{entity}` | `clinical_patients`, `clinical_encounters`, `billing_claims` |
| Gold — Dimensions | `dim_` prefix + entity | `dim_{entity}` | `dim_patient`, `dim_provider`, `dim_organization` |
| Gold — Facts | `fact_` prefix + event/entity | `fact_{event}` | `fact_encounter`, `fact_condition`, `fact_claim` |
| Gold — Aggregates | `agg_` prefix + metric scope | `agg_{scope}` | `agg_readmission_30d`, `agg_encounter_monthly` |
| Gold — Bridges | `bridge_` prefix + relationship | `bridge_{rel}` | `bridge_patient_payer` |

**General rules**:
- All table names use `snake_case` — no camelCase, no PascalCase
- Singular nouns preferred (`dim_patient`, not `dim_patients`) unless the entity is inherently plural
- No abbreviations unless in the approved abbreviation list (see section 5)
- Maximum 63 characters (database identifier limit)

---

## 2. Column Naming Rules

| Convention | Pattern | Examples |
|-----------|---------|----------|
| Natural keys | `{entity}_id` | `patient_id`, `encounter_id`, `provider_id` |
| Surrogate keys | `{entity}_sk` | `patient_sk`, `encounter_sk`, `provider_sk` |
| Foreign keys | Match the referenced column name | `patient_sk` in `fact_encounter` references `dim_patient.patient_sk` |
| Timestamps | `{event}_at` | `created_at`, `updated_at`, `discharged_at` |
| Dates (no time) | `{event}_date` | `birth_date`, `encounter_date`, `effective_date` |
| Booleans | `is_` or `has_` prefix | `is_readmission`, `is_active`, `has_allergy`, `is_current` |
| Counts | `{what}_count` | `encounter_count`, `condition_count` |
| Amounts | `{what}_amount` | `claim_amount`, `total_cost_amount` |
| Durations | `{what}_{unit}` | `encounter_duration_hours`, `los_days` |
| Codes | `{system}_code` | `snomed_code`, `rxnorm_code`, `loinc_code` |
| Descriptions | `{what}_description` | `condition_description`, `medication_description` |
| Enumerations | Plain name (no suffix) | `encounter_class`, `gender`, `marital_status` |

**General rules**:
- All column names use `snake_case`
- No Hungarian notation (`str_name`, `int_age`)
- No reserved SQL keywords as column names (`order`, `group`, `select`)
- Maximum 63 characters

---

## 3. Metadata Column Standards

All tables at every layer include these pipeline metadata columns:

| Column | Type | Layer | Description |
|--------|------|-------|-------------|
| `_ingested_at` | TIMESTAMP | Bronze, Silver, Gold | When the record was loaded by the pipeline |
| `_source_batch_id` | VARCHAR | Bronze, Silver | Pipeline run identifier that produced this record |
| `_source_file` | VARCHAR | Bronze | Source file path (for file-based ingestion) |
| `_record_hash` | VARCHAR | Bronze, Silver | SHA-256 hash of all business columns — used for change detection |

**Gold layer** additionally includes:

| Column | Type | Description |
|--------|------|-------------|
| `effective_from` | DATE | SCD Type 2: row version start date |
| `effective_to` | DATE | SCD Type 2: row version end date (`9999-12-31` for current) |
| `is_current` | BOOLEAN | SCD Type 2: `TRUE` for the active version |

---

## 4. Schema Organization

| Schema | Contents | Example Tables |
|--------|----------|----------------|
| `bronze` | Source-aligned tables with metadata columns | `synthea_patients`, `synthea_encounters`, `synthea_conditions` |
| `clinical` | Silver-layer clinical entities | `clinical_patients`, `clinical_encounters`, `clinical_conditions`, `clinical_allergies` |
| `billing` | Silver-layer financial entities | `billing_claims`, `billing_payer_transitions` |
| `reference` | Silver-layer reference/lookup entities | `reference_providers`, `reference_organizations`, `reference_payers` |
| `analytics` | Gold-layer dimensional model | `dim_patient`, `dim_provider`, `fact_encounter`, `fact_condition`, `agg_readmission_30d` |

---

## 5. Approved Abbreviations

Only these abbreviations are permitted in table and column names:

| Abbreviation | Full Term |
|-------------|-----------|
| `id` | Identifier |
| `sk` | Surrogate Key |
| `dt` | Not approved — use `date` |
| `ts` | Not approved — use `at` suffix |
| `desc` | Not approved — use `description` |
| `num` | Not approved — use `count` or full name |
| `amt` | Not approved — use `amount` |
| `qty` | Not approved — use `quantity` |
| `dim` | Dimension (table prefix only) |
| `fact` | Fact (table prefix only) |
| `agg` | Aggregate (table prefix only) |
| `dq` | Data Quality (rule IDs only, not columns) |
| `los` | Length of Stay (domain-specific, approved for healthcare) |
| `dob` | Not approved — use `birth_date` |

---

## 6. Prohibited Patterns

| Pattern | Why | Use Instead |
|---------|-----|-------------|
| camelCase (`patientName`) | Inconsistent with SQL conventions | `patient_name` |
| ALL_CAPS (`PATIENT_ID`) | Reserved for source system column references | `patient_id` |
| Generic names (`data`, `info`, `value`, `misc`, `temp`) | Ambiguous, undiscoverable | Specific business term |
| Prefixed types (`str_name`, `int_count`) | Hungarian notation obscures meaning | Plain `name`, `count` |
| Trailing numbers (`patient_1`, `address_2`) | Suggests poor normalization | Separate table or array column |
| Double underscores (`patient__id`) | Confusing, may conflict with metadata prefixes | Single underscore |

---

## 7. Healthcare-Specific Naming

| Area | Convention | Examples |
|------|-----------|----------|
| FHIR resource alignment | Silver table names align with FHIR resource names where applicable | `patients` (FHIR: Patient), `encounters` (FHIR: Encounter), `conditions` (FHIR: Condition) |
| PHI column tagging | Columns containing PHI include a comment tag in the schema definition | `-- PHI: patient name`, `-- PHI: date of birth` |
| Code system columns | Include the code system name in the column | `snomed_code`, `rxnorm_code`, `loinc_code` |
| PHI columns to exclude | SSN, driver's license, passport numbers must NOT appear in Silver or Gold | Drop `SSN`, `DRIVERS`, `PASSPORT` at Bronze-to-Silver boundary |
