-- migration: 20260620_004_synthea_conditions
-- layer: bronze  table: unity.bronze.synthea_conditions
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_conditions

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_conditions (
    START DATE,
    STOP DATE,
    PATIENT STRING,
    ENCOUNTER STRING,
    SYSTEM STRING,
    CODE BIGINT,
    DESCRIPTION STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_conditions'
