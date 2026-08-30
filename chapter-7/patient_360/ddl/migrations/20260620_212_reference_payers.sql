-- migration: 20260620_025_reference_payers
-- layer: silver  table: unity.silver.reference_payers
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.silver.reference_payers

CREATE TABLE IF NOT EXISTS unity.silver.reference_payers (
    payer_id STRING NOT NULL,
    payer_name STRING,
    ownership STRING,
    address STRING,
    city STRING,
    state STRING,
    zip STRING,
    phone STRING,
    amount_covered DECIMAL(14,2),
    amount_uncovered DECIMAL(14,2),
    revenue DECIMAL(12,2),
    covered_encounters INT,
    uncovered_encounters INT,
    unique_customers INT,
    member_months INT,
    effective_from DATE,
    effective_to DATE,
    is_current BOOLEAN,
    _record_hash STRING,
    _ingested_at TIMESTAMP,
    _source_batch_id STRING
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/silver/reference_payers'
