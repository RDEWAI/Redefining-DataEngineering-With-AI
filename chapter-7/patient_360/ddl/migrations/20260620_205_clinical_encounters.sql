-- migration: 20260620_018_clinical_encounters
-- layer: silver  table: unity.silver.clinical_encounters
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.clinical_encounters

CREATE TABLE IF NOT EXISTS unity.silver.clinical_encounters (
    encounter_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    organization_id STRING,
    provider_id STRING,
    payer_id STRING,
    encounter_class STRING,
    snomed_code STRING,
    encounter_description STRING,
    start_date TIMESTAMP NOT NULL,
    stop_date TIMESTAMP,
    encounter_duration_hours DECIMAL(10,2),
    los_days INT,
    base_encounter_cost DECIMAL(12,2),
    total_claim_cost DECIMAL(12,2),
    payer_coverage DECIMAL(12,2),
    total_visit_cost DECIMAL(12,2),
    reason_code STRING,
    reason_description STRING,
    is_30_day_readmission BOOLEAN NOT NULL,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/clinical_encounters'
PARTITIONED BY (ds)
