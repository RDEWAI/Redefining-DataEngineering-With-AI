-- migration: 20260620_015_clinical_allergies
-- layer: silver  table: unity.silver.clinical_allergies
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_allergies

CREATE TABLE IF NOT EXISTS unity.silver.clinical_allergies (
    patient_id STRING NOT NULL,
    encounter_id STRING,
    start_date DATE,
    stop_date DATE,
    allergy_code STRING,
    code_system STRING,
    allergy_description STRING NOT NULL,
    allergy_type STRING,
    allergy_category STRING,
    reaction1_code STRING,
    reaction1_description STRING,
    severity1 STRING,
    reaction2_code STRING,
    reaction2_description STRING,
    severity2 STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_allergies'
PARTITIONED BY (ds)
