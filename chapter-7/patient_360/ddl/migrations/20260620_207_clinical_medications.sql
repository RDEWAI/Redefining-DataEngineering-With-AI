-- migration: 20260620_020_clinical_medications
-- layer: silver  table: unity.silver.clinical_medications
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_medications

CREATE TABLE IF NOT EXISTS unity.silver.clinical_medications (
    patient_id STRING NOT NULL,
    encounter_id STRING NOT NULL,
    payer_id STRING,
    start_date TIMESTAMP NOT NULL,
    stop_date TIMESTAMP,
    rxnorm_code STRING,
    medication_description STRING,
    base_cost DECIMAL(12,2),
    payer_coverage DECIMAL(12,2),
    dispenses INT,
    total_cost DECIMAL(12,2),
    reason_code STRING,
    reason_description STRING,
    medication_status STRING NOT NULL,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_medications'
PARTITIONED BY (ds)
