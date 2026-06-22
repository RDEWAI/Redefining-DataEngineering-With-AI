-- migration: 20260620_024_reference_organizations
-- layer: silver  table: unity.silver.reference_organizations
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.reference_organizations

CREATE TABLE IF NOT EXISTS unity.silver.reference_organizations (
    organization_id STRING NOT NULL,
    organization_name STRING,
    address STRING,
    city STRING,
    state STRING,
    zip STRING,
    lat DECIMAL(9,6),
    lon DECIMAL(9,6),
    phone STRING,
    revenue DECIMAL(14,2),
    utilization INT,
    effective_from DATE,
    effective_to DATE,
    is_current BOOLEAN,
    _record_hash STRING,
    _ingested_at TIMESTAMP,
    _source_batch_id STRING
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/reference_organizations'
