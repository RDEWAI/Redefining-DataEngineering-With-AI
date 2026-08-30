# Code System Mappings — Patient 360 Pipeline

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2026-03-16 |
| Scope | Healthcare code standardization |
| Applies To | STM Bronze-to-Silver and Silver-to-Gold layers |

## 1. Gender Codes

| Source Value | Target Code | Target Display | Standard |
|-------------|-------------|----------------|----------|
| M | MALE | Male | HL7 AdministrativeGender |
| F | FEMALE | Female | HL7 AdministrativeGender |
| O | OTHER | Other | HL7 AdministrativeGender |
| NULL | UNKNOWN | Unknown | Default |

```sql
CASE UPPER(TRIM(gender))
    WHEN 'M' THEN 'MALE'
    WHEN 'F' THEN 'FEMALE'
    WHEN 'O' THEN 'OTHER'
    ELSE 'UNKNOWN'
END AS gender_code
```

## 2. Encounter Class (SNOMED-CT)

| Source Value | SNOMED Code | Display | Category |
|-------------|-------------|---------|----------|
| ambulatory | 371883000 | Outpatient procedure | Outpatient |
| emergency | 50849002 | Emergency room admission | Emergency |
| inpatient | 32485007 | Hospital admission | Inpatient |
| wellness | 410620009 | Well child visit | Preventive |
| urgentcare | 702927004 | Urgent care clinic | Urgent |
| outpatient | 371883000 | Outpatient procedure | Outpatient |

```sql
CASE LOWER(TRIM(encounterclass))
    WHEN 'ambulatory' THEN '371883000'
    WHEN 'emergency' THEN '50849002'
    WHEN 'inpatient' THEN '32485007'
    WHEN 'wellness' THEN '410620009'
    WHEN 'urgentcare' THEN '702927004'
    WHEN 'outpatient' THEN '371883000'
    ELSE 'UNMAPPED'
END AS encounter_snomed_code
```

## 3. Race Codes

| Source Value | Target Code | Standard |
|-------------|-------------|----------|
| white | 2106-3 | CDC Race & Ethnicity |
| black | 2054-5 | CDC Race & Ethnicity |
| asian | 2028-9 | CDC Race & Ethnicity |
| native | 1002-5 | CDC Race & Ethnicity |
| hawaiian | 2076-8 | CDC Race & Ethnicity |
| other | 2131-1 | CDC Race & Ethnicity |
| NULL | UNK | Unknown |

## 4. Ethnicity Codes

| Source Value | Target Code | Standard |
|-------------|-------------|----------|
| hispanic | 2135-2 | CDC Race & Ethnicity |
| nonhispanic | 2186-5 | CDC Race & Ethnicity |
| NULL | UNK | Unknown |

## 5. Condition Codes (SNOMED-CT — Common)

| Condition Category | Example SNOMED | Display |
|-------------------|----------------|---------|
| Diabetes | 44054006 | Type 2 diabetes mellitus |
| Hypertension | 59621000 | Essential hypertension |
| Asthma | 195967001 | Asthma |
| Depression | 36923009 | Major depressive disorder |
| Obesity | 162864005 | Body mass index 30+ |

Note: Synthea data already contains SNOMED codes in the `CODE` column.
The STM should validate these codes exist and map display names.

## 6. Medication Codes (RxNorm — Common)

| Category | Example RxNorm | Display |
|----------|---------------|---------|
| Metformin | 860975 | Metformin 500 MG Oral Tablet |
| Lisinopril | 314076 | Lisinopril 10 MG Oral Tablet |
| Albuterol | 245314 | Albuterol 0.83 MG/ML Inhalant Solution |
| Fluoxetine | 310385 | Fluoxetine 20 MG Oral Capsule |

Note: Synthea data already contains RxNorm codes in the `CODE` column.
The STM should validate and carry forward these codes.

## 7. Observation Codes (LOINC — Common)

| Observation | LOINC Code | Display | Unit |
|------------|------------|---------|------|
| Body Height | 8302-2 | Body Height | cm |
| Body Weight | 29463-7 | Body Weight | kg |
| BMI | 39156-5 | Body Mass Index | kg/m2 |
| Blood Pressure (Systolic) | 8480-6 | Systolic Blood Pressure | mmHg |
| Blood Pressure (Diastolic) | 8462-4 | Diastolic Blood Pressure | mmHg |
| Heart Rate | 8867-4 | Heart rate | /min |

## 8. Enumeration Standards

### Boolean Mappings

| Source Pattern | Target |
|---------------|--------|
| true, 1, yes, Y, T | TRUE |
| false, 0, no, N, F | FALSE |
| NULL, empty | NULL (or FALSE if non-nullable) |

### Status Codes

| Domain | Values |
|--------|--------|
| Record Status | ACTIVE, INACTIVE, DELETED |
| SCD Flag | CURRENT, EXPIRED |
| DQ Status | VALID, SUSPECT, INVALID |
