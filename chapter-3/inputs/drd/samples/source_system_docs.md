# Source System Documentation: Synthea Healthcare Database

## System Overview

| Property | Value |
|----------|-------|
| **System Name** | Synthea Healthcare EHR (Electronic Health Record) |
| **Database** | DuckDB |
| **Location** | `data/duckdb/raw.db` |
| **Schema** | `synthea` |
| **Access Method** | SQL queries via DuckDB connection |
| **Owner** | Health IT Department |
| **Update Frequency** | Daily batch load from CSV source files |

## Available Tables

### Core Patient Tables

#### `synthea.patients`
Primary patient demographics table.

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| id | VARCHAR | Unique patient identifier (UUID) | No |
| birthdate | DATE | Patient date of birth | No |
| deathdate | DATE | Date of death (if applicable) | Yes |
| ssn | VARCHAR | Social Security Number | No |
| drivers | VARCHAR | Driver's license number | Yes |
| passport | VARCHAR | Passport number | Yes |
| prefix | VARCHAR | Name prefix (Mr., Mrs., Dr.) | Yes |
| first | VARCHAR | First name | No |
| last | VARCHAR | Last name | No |
| suffix | VARCHAR | Name suffix (Jr., Sr.) | Yes |
| maiden | VARCHAR | Maiden name | Yes |
| marital | VARCHAR | Marital status (M, S, W, D) | Yes |
| race | VARCHAR | Race | Yes |
| ethnicity | VARCHAR | Ethnicity | Yes |
| gender | VARCHAR | Gender (M, F) | No |
| birthplace | VARCHAR | Place of birth | Yes |
| address | VARCHAR | Street address | Yes |
| city | VARCHAR | City | Yes |
| state | VARCHAR | State | Yes |
| county | VARCHAR | County | Yes |
| fips | VARCHAR | FIPS code | Yes |
| zip | VARCHAR | ZIP code | Yes |
| lat | DOUBLE | Latitude | Yes |
| lon | DOUBLE | Longitude | Yes |
| healthcare_expenses | DOUBLE | Total healthcare expenses | Yes |
| healthcare_coverage | DOUBLE | Insurance coverage amount | Yes |
| income | INTEGER | Annual income | Yes |

**Estimated rows**: 1,000

#### `synthea.encounters`
Patient visit/encounter records.

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| id | VARCHAR | Unique encounter identifier (UUID) | No |
| start | TIMESTAMP | Encounter start date/time | No |
| stop | TIMESTAMP | Encounter end date/time | Yes |
| patient | VARCHAR | FK to patients.id | No |
| organization | VARCHAR | FK to organizations.id | Yes |
| provider | VARCHAR | FK to providers.id | Yes |
| payer | VARCHAR | FK to payers.id | Yes |
| encounterclass | VARCHAR | Type (ambulatory, inpatient, emergency, etc.) | No |
| code | VARCHAR | SNOMED CT encounter code | No |
| description | VARCHAR | Human-readable encounter description | No |
| base_encounter_cost | DOUBLE | Base cost of the encounter | Yes |
| total_claim_cost | DOUBLE | Total cost including all services | Yes |
| payer_coverage | DOUBLE | Amount covered by payer | Yes |
| reasoncode | VARCHAR | Reason code (SNOMED) | Yes |
| reasondescription | VARCHAR | Reason description | Yes |

**Estimated rows**: 50,000

#### `synthea.conditions`
Patient diagnoses and conditions.

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| start | DATE | Condition onset date | No |
| stop | DATE | Condition resolution date | Yes |
| patient | VARCHAR | FK to patients.id | No |
| encounter | VARCHAR | FK to encounters.id | No |
| code | VARCHAR | SNOMED CT condition code | No |
| description | VARCHAR | Human-readable description | No |

**Estimated rows**: 25,000

#### `synthea.medications`
Medication prescriptions.

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| start | DATE | Prescription start date | No |
| stop | DATE | Prescription end date | Yes |
| patient | VARCHAR | FK to patients.id | No |
| payer | VARCHAR | FK to payers.id | Yes |
| encounter | VARCHAR | FK to encounters.id | No |
| code | VARCHAR | RxNorm medication code | No |
| description | VARCHAR | Medication name and dosage | No |
| base_cost | DOUBLE | Cost per unit | Yes |
| payer_coverage | DOUBLE | Amount covered by payer | Yes |
| dispenses | INTEGER | Number of dispenses | Yes |
| totalcost | DOUBLE | Total medication cost | Yes |
| reasoncode | VARCHAR | Reason code (SNOMED) | Yes |
| reasondescription | VARCHAR | Reason for prescription | Yes |

**Estimated rows**: 30,000

#### `synthea.observations`
Lab results, vitals, and clinical observations.

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| date | DATE | Observation date | No |
| patient | VARCHAR | FK to patients.id | No |
| encounter | VARCHAR | FK to encounters.id | No |
| category | VARCHAR | Observation category (vital-signs, laboratory, etc.) | No |
| code | VARCHAR | LOINC observation code | No |
| description | VARCHAR | Human-readable description | No |
| value | VARCHAR | Observation value | Yes |
| units | VARCHAR | Units of measurement | Yes |
| type | VARCHAR | Value data type | Yes |

**Estimated rows**: 200,000

### Clinical Support Tables

#### `synthea.procedures`
| Column | Type | Description |
|--------|------|-------------|
| start | TIMESTAMP | Procedure start |
| stop | TIMESTAMP | Procedure end |
| patient | VARCHAR | FK to patients.id |
| encounter | VARCHAR | FK to encounters.id |
| code | VARCHAR | SNOMED procedure code |
| description | VARCHAR | Procedure description |
| base_cost | DOUBLE | Procedure cost |
| reasoncode | VARCHAR | Reason code |
| reasondescription | VARCHAR | Reason description |

**Estimated rows**: 40,000

#### `synthea.allergies`
| Column | Type | Description |
|--------|------|-------------|
| start | DATE | Allergy onset date |
| stop | DATE | Allergy resolution date |
| patient | VARCHAR | FK to patients.id |
| encounter | VARCHAR | FK to encounters.id |
| code | VARCHAR | SNOMED allergy code |
| system | VARCHAR | Code system |
| description | VARCHAR | Allergy description |
| type | VARCHAR | Allergy type |
| category | VARCHAR | Allergy category |
| reaction1 | VARCHAR | Primary reaction |
| description1 | VARCHAR | Reaction description |
| severity1 | VARCHAR | Reaction severity |
| reaction2 | VARCHAR | Secondary reaction |
| description2 | VARCHAR | Secondary reaction description |
| severity2 | VARCHAR | Secondary reaction severity |

**Estimated rows**: 5,000

#### `synthea.immunizations`
| Column | Type | Description |
|--------|------|-------------|
| date | DATE | Immunization date |
| patient | VARCHAR | FK to patients.id |
| encounter | VARCHAR | FK to encounters.id |
| code | VARCHAR | CVX vaccine code |
| description | VARCHAR | Vaccine description |
| base_cost | DOUBLE | Vaccination cost |

**Estimated rows**: 20,000

### Financial Tables

#### `synthea.claims`
| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR | Claim identifier |
| patient | VARCHAR | FK to patients.id |
| provider | VARCHAR | FK to providers.id |
| primarypatientinsuranceid | VARCHAR | Primary insurance |
| secondarypatientinsuranceid | VARCHAR | Secondary insurance |
| departmentid | VARCHAR | Department |
| patientdepartmentid | VARCHAR | Patient department |
| diagnosis1-8 | VARCHAR | Diagnosis codes (up to 8) |
| referringproviderid | VARCHAR | Referring provider |
| appointmentid | VARCHAR | Appointment |
| currentillnessdate | DATE | Current illness onset |
| servicedate | DATE | Service date |
| supervisingproviderid | VARCHAR | Supervising provider |
| status1-2 | VARCHAR | Claim status |

**Estimated rows**: 60,000

#### `synthea.careplans`
| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR | Care plan identifier |
| start | DATE | Plan start date |
| stop | DATE | Plan end date |
| patient | VARCHAR | FK to patients.id |
| encounter | VARCHAR | FK to encounters.id |
| code | VARCHAR | SNOMED care plan code |
| description | VARCHAR | Care plan description |
| reasoncode | VARCHAR | Reason code |
| reasondescription | VARCHAR | Reason description |

**Estimated rows**: 15,000

### Reference Tables

- `synthea.organizations` — Healthcare organizations (~50 rows)
- `synthea.providers` — Healthcare providers (~200 rows)
- `synthea.payers` — Insurance payers (~10 rows)
- `synthea.payer_transitions` — Insurance changes over time (~2,000 rows)
- `synthea.devices` — Medical devices (~3,000 rows)
- `synthea.supplies` — Medical supplies (~5,000 rows)
- `synthea.imaging_studies` — Imaging records (~8,000 rows)

## Data Relationships

```
patients (1) ──── (many) encounters
patients (1) ──── (many) conditions
patients (1) ──── (many) medications
patients (1) ──── (many) observations
patients (1) ──── (many) procedures
patients (1) ──── (many) allergies
patients (1) ──── (many) immunizations
patients (1) ──── (many) claims
patients (1) ──── (many) careplans
encounters (1) ── (many) conditions
encounters (1) ── (many) medications
encounters (1) ── (many) observations
encounters (1) ── (many) procedures
```

## Access Notes

- Database is local DuckDB file — no network latency
- Read-only access for analytics; source data loaded via batch ETL
- No authentication for local development; production RBAC TBD
- Current database size: approximately 500 MB
