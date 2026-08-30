-- migration: 20260620_303_patient_summary
-- layer: gold  table: unity.gold.patient_summary
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.gold.patient_summary
-- Columns per DMS §4 patient_summary (29 cols; no `ds`, full overwrite, no partition).

CREATE TABLE IF NOT EXISTS unity.gold.patient_summary (
    patient_id STRING NOT NULL,
    first_name STRING NOT NULL,
    middle_name STRING,
    last_name STRING NOT NULL,
    prefix STRING,
    suffix STRING,
    birth_date DATE NOT NULL,
    death_date DATE,
    patient_status STRING NOT NULL,
    calculated_age INT,
    gender STRING,
    race STRING,
    ethnicity STRING,
    marital_status STRING,
    address STRING,
    city STRING,
    state STRING,
    zip STRING,
    active_condition_count INT NOT NULL,
    active_medication_count INT NOT NULL,
    has_allergy BOOLEAN NOT NULL,
    allergies ARRAY<STRUCT<description: STRING, severity: STRING>>,
    conditions ARRAY<STRUCT<snomed_code: STRING, description: STRING, onset_date: DATE>>,
    medications ARRAY<STRUCT<rxnorm_code: STRING, description: STRING, status: STRING>>,
    recent_encounter_date DATE,
    recent_encounter_class STRING,
    encounter_count INT NOT NULL,
    has_30day_readmission_history BOOLEAN NOT NULL,
    _ingested_at TIMESTAMP NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/gold/patient_summary'
