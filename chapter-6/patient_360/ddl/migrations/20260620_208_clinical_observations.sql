-- migration: 20260620_021_clinical_observations
-- layer: silver  table: unity.silver.clinical_observations
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_observations

CREATE TABLE IF NOT EXISTS unity.silver.clinical_observations (
    patient_id STRING NOT NULL,
    encounter_id STRING NOT NULL,
    observation_date TIMESTAMP NOT NULL,
    category STRING,
    loinc_code STRING,
    observation_description STRING,
    observation_value STRING,
    units STRING,
    value_type STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_observations'
PARTITIONED BY (ds)
