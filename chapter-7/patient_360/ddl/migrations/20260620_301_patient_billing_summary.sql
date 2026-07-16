-- migration: 20260620_301_patient_billing_summary
-- layer: gold  table: unity.gold.patient_billing_summary
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.gold.patient_billing_summary
-- Columns per DMS §4 patient_billing_summary (21 cols; no `ds`, full overwrite, no
-- partition; grain: one row per encounter per patient; cost fields isolated here per DRD §5.5).

CREATE TABLE IF NOT EXISTS unity.gold.patient_billing_summary (
    encounter_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    first_name STRING NOT NULL,
    last_name STRING NOT NULL,
    birth_date DATE NOT NULL,
    encounter_class STRING,
    service_date DATE,
    base_encounter_cost DECIMAL(12,2) NOT NULL,
    total_claim_cost DECIMAL(12,2) NOT NULL,
    payer_coverage DECIMAL(12,2) NOT NULL,
    total_visit_cost DECIMAL(12,2) NOT NULL,
    claim_id STRING,
    primary_payer_id STRING,
    primary_payer_name STRING,
    secondary_payer_id STRING,
    secondary_payer_name STRING,
    claim_status STRING,
    outstanding_amount DECIMAL(12,2),
    provider_id STRING,
    provider_name STRING,
    _ingested_at TIMESTAMP NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/gold/patient_billing_summary'
