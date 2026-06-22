-- migration: 20260620_022_clinical_patients
-- layer: silver  table: unity.silver.clinical_patients
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_patients

CREATE TABLE IF NOT EXISTS unity.silver.clinical_patients (
    patient_id STRING NOT NULL,
    birth_date DATE,
    death_date DATE,
    prefix STRING,
    first_name STRING,
    middle_name STRING,
    last_name STRING,
    suffix STRING,
    maiden_name STRING,
    marital_status STRING,
    race STRING,
    ethnicity STRING,
    gender STRING,
    birth_place STRING,
    address STRING,
    city STRING,
    state STRING,
    county STRING,
    zip STRING,
    lat DECIMAL(9,6),
    lon DECIMAL(9,6),
    healthcare_expenses DECIMAL(12,2),
    healthcare_coverage DECIMAL(12,2),
    income INT,
    calculated_age INT,
    patient_status STRING,
    effective_from DATE,
    effective_to DATE,
    is_current BOOLEAN,
    _record_hash STRING,
    _ingested_at TIMESTAMP,
    _source_batch_id STRING
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_patients'
