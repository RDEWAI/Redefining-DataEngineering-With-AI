# Existing Data Catalog: Synthea Healthcare

## Catalog Overview

| Property | Value |
|----------|-------|
| **Database** | DuckDB (`data/duckdb/raw.db`) |
| **Schema** | `synthea` |
| **Total Tables** | 18 |
| **Load Method** | CSV batch load via `scripts/load_raw_csv_to_duckdb.py` |
| **Last Refreshed** | January 2026 |

## Table Inventory

| # | Table Name | Row Count | Column Count | Primary Key | Description |
|---|-----------|-----------|--------------|-------------|-------------|
| 1 | patients | 1,171 | 26 | id (UUID) | Patient demographics |
| 2 | encounters | 48,723 | 15 | id (UUID) | Visit records |
| 3 | conditions | 24,891 | 6 | (patient, encounter, code) | Diagnoses |
| 4 | medications | 31,456 | 13 | (patient, encounter, code, start) | Prescriptions |
| 5 | observations | 198,234 | 9 | (patient, encounter, code, date) | Lab results and vitals |
| 6 | procedures | 41,102 | 9 | (patient, encounter, code, start) | Procedures performed |
| 7 | allergies | 4,987 | 15 | (patient, encounter, code) | Patient allergies |
| 8 | immunizations | 19,834 | 6 | (patient, encounter, code, date) | Vaccinations |
| 9 | careplans | 14,567 | 9 | id (UUID) | Active care plans |
| 10 | claims | 58,912 | 14+ | id (UUID) | Insurance claims |
| 11 | claims_transactions | 72,345 | 12 | id | Claim line items |
| 12 | payers | 10 | 9 | id (UUID) | Insurance companies |
| 13 | payer_transitions | 2,134 | 7 | (patient, start_date) | Insurance changes |
| 14 | organizations | 48 | 8 | id (UUID) | Healthcare facilities |
| 15 | providers | 198 | 9 | id (UUID) | Clinicians |
| 16 | devices | 2,876 | 9 | (patient, encounter, code) | Medical devices |
| 17 | supplies | 4,523 | 5 | (patient, encounter, code, date) | Medical supplies |
| 18 | imaging_studies | 7,891 | 8 | id (UUID) | Imaging records |

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
