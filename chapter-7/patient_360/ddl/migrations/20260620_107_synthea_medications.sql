-- migration: 20260620_007_synthea_medications
-- layer: bronze  table: unity.bronze.synthea_medications
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_medications

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_medications (
    START TIMESTAMP,
    STOP TIMESTAMP,
    PATIENT STRING,
    PAYER STRING,
    ENCOUNTER STRING,
    CODE BIGINT,
    DESCRIPTION STRING,
    BASE_COST DOUBLE,
    PAYER_COVERAGE DOUBLE,
    DISPENSES BIGINT,
    TOTALCOST DOUBLE,
    REASONCODE BIGINT,
    REASONDESCRIPTION STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_medications'
