-- migration: 20260620_017_clinical_conditions
-- layer: silver  table: unity.silver.clinical_conditions
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_conditions

CREATE TABLE IF NOT EXISTS unity.silver.clinical_conditions (
    patient_id STRING NOT NULL,
    encounter_id STRING NOT NULL,
    onset_date DATE NOT NULL,
    resolution_date DATE,
    code_system STRING,
    snomed_code STRING,
    condition_description STRING,
    condition_status STRING NOT NULL,
    condition_duration_days INT,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_conditions'
PARTITIONED BY (ds)
