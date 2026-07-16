-- migration: 20260620_014_billing_claims
-- layer: silver  table: unity.silver.billing_claims
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.billing_claims

CREATE TABLE IF NOT EXISTS unity.silver.billing_claims (
    claim_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    appointment_id STRING,
    provider_id STRING,
    primary_payer_id STRING,
    secondary_payer_id STRING,
    diagnosis_code_1 STRING,
    diagnosis_code_2 STRING,
    diagnosis_code_3 STRING,
    referring_provider_id STRING,
    supervising_provider_id STRING,
    service_date TIMESTAMP,
    current_illness_date TIMESTAMP,
    status_primary STRING,
    status_secondary STRING,
    status_patient STRING,
    outstanding_primary DECIMAL(12,2),
    outstanding_secondary DECIMAL(12,2),
    outstanding_patient DECIMAL(12,2),
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _record_hash STRING NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/billing_claims'
PARTITIONED BY (ds)
