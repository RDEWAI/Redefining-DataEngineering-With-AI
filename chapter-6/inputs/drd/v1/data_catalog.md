# Existing Data Catalog: Synthea Healthcare

## Catalog Overview

| Property | Value |
|----------|-------|
| **Database** | See [source_system_docs.md](source_system_docs.md) for connection details |
| **Schema** | `synthea` |
| **Total Tables** | 18 |
| **Load Method** | CSV batch load via `scripts/load_raw_csv_to_duckdb.py` |
| **Last Refreshed** | January 2026 |

## Table Inventory

| # | Table Name | Primary Key | Description |
|---|-----------|-------------|-------------|
| 1 | patients | id (UUID) | Patient demographics |
| 2 | encounters | id (UUID) | Visit records |
| 3 | conditions | (patient, encounter, code) | Diagnoses |
| 4 | medications | (patient, encounter, code, start) | Prescriptions |
| 5 | observations | (patient, encounter, code, date) | Lab results and vitals |
| 6 | procedures | (patient, encounter, code, start) | Procedures performed |
| 7 | allergies | (patient, encounter, code) | Patient allergies |
| 8 | immunizations | (patient, encounter, code, date) | Vaccinations |
| 9 | careplans | id (UUID) | Active care plans |
| 10 | claims | id (UUID) | Insurance claims |
| 11 | claims_transactions | id (UUID) | Claim line items |
| 12 | payers | id (UUID) | Insurance companies |
| 13 | payer_transitions | (patient, start_date) | Insurance changes |
| 14 | organizations | id (UUID) | Healthcare facilities |
| 15 | providers | id (UUID) | Clinicians |
| 16 | devices | (patient, encounter, code) | Medical devices |
| 17 | supplies | (patient, encounter, code, date) | Medical supplies |
| 18 | imaging_studies | id (UUID) | Imaging records |

## Data Quality Notes

- **Patient ID consistency**: All child tables reference `patients.id` via a `patient` column
- **Encounter linkage**: Most clinical tables (conditions, medications, observations) link to both `patients.id` and `encounters.id`
- **Code systems**: Conditions use SNOMED CT, medications use RxNorm, observations use LOINC, immunizations use CVX
- **Date coverage**: Data spans from approximately 1920 (oldest patient birth) to 2026 (most recent encounters)
- **Known gaps**: Some older encounters may have NULL values for cost fields; approximately 2% of observations have NULL values

## Sample Queries

```sql
-- Count patients
SELECT COUNT(*) FROM synthea.patients;

-- Most recent encounter per patient
SELECT p.first, p.last, MAX(e.start) as last_visit
FROM synthea.patients p
JOIN synthea.encounters e ON p.id = e.patient
GROUP BY p.first, p.last;

-- Active medications for a patient
SELECT m.description, m.start, m.stop
FROM synthea.medications m
WHERE m.patient = '{patient_id}'
  AND (m.stop IS NULL OR m.stop > CURRENT_DATE);

-- Allergy list for a patient
SELECT a.description, a.type, a.category, a.severity1
FROM synthea.allergies a
WHERE a.patient = '{patient_id}'
  AND (a.stop IS NULL OR a.stop > CURRENT_DATE);
```
