-- migration: 20260620_028_patient_clinical_history
-- layer: gold  table: unity.gold.patient_clinical_history
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.gold.patient_clinical_history

CREATE TABLE IF NOT EXISTS gold.patient_clinical_history (
    -- Columns stubbed; run update-scaffold sync-contracts to populate from DMS.
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
