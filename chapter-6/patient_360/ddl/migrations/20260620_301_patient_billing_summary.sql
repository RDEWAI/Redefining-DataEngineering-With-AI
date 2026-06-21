-- migration: 20260620_027_patient_billing_summary
-- layer: gold  table: unity.gold.patient_billing_summary
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.gold.patient_billing_summary

CREATE TABLE IF NOT EXISTS gold.patient_billing_summary (
    -- Columns stubbed; run update-scaffold sync-contracts to populate from DMS.
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
