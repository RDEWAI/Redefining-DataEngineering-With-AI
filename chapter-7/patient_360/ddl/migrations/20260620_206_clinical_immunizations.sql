-- migration: 20260620_019_clinical_immunizations
-- layer: silver  table: unity.silver.clinical_immunizations
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_immunizations

CREATE TABLE IF NOT EXISTS unity.silver.clinical_immunizations (
    patient_id STRING NOT NULL,
    encounter_id STRING NOT NULL,
    immunization_date TIMESTAMP NOT NULL,
    cvx_code STRING,
    immunization_description STRING,
    base_cost DECIMAL(12,2),
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_immunizations'
PARTITIONED BY (ds)
