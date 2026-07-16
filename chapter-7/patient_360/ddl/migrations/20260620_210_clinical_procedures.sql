-- migration: 20260620_023_clinical_procedures
-- layer: silver  table: unity.silver.clinical_procedures
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_procedures

CREATE TABLE IF NOT EXISTS unity.silver.clinical_procedures (
    patient_id STRING NOT NULL,
    encounter_id STRING NOT NULL,
    start_date TIMESTAMP NOT NULL,
    stop_date TIMESTAMP,
    code_system STRING,
    snomed_code STRING,
    procedure_description STRING,
    base_cost DECIMAL(12,2),
    reason_code STRING,
    reason_description STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_procedures'
PARTITIONED BY (ds)
