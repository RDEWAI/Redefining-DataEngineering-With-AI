-- migration: 20260620_016_clinical_careplans
-- layer: silver  table: unity.silver.clinical_careplans
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_careplans

CREATE TABLE IF NOT EXISTS unity.silver.clinical_careplans (
    careplan_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    encounter_id STRING,
    start_date DATE,
    stop_date DATE,
    snomed_code STRING,
    careplan_description STRING,
    reason_code STRING,
    reason_description STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_careplans'
PARTITIONED BY (ds)
