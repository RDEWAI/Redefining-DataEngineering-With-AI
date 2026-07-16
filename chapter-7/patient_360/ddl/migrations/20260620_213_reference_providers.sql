-- migration: 20260620_026_reference_providers
-- layer: silver  table: unity.silver.reference_providers
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.reference_providers

CREATE TABLE IF NOT EXISTS unity.silver.reference_providers (
    provider_id STRING NOT NULL,
    organization_id STRING,
    provider_name STRING,
    gender STRING,
    specialty STRING,
    address STRING,
    city STRING,
    state STRING,
    zip STRING,
    lat DECIMAL(9,6),
    lon DECIMAL(9,6),
    encounter_count INT,
    procedure_count INT,
    effective_from DATE,
    effective_to DATE,
    is_current BOOLEAN,
    _record_hash STRING,
    _ingested_at TIMESTAMP,
    _source_batch_id STRING
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/reference_providers'
