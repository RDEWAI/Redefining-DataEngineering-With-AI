-- migration: 20260620_002_synthea_careplans
-- layer: bronze  table: unity.bronze.synthea_careplans
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_careplans

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_careplans (
    Id STRING,
    START DATE,
    STOP DATE,
    PATIENT STRING,
    ENCOUNTER STRING,
    CODE BIGINT,
    DESCRIPTION STRING,
    REASONCODE BIGINT,
    REASONDESCRIPTION STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_careplans'
