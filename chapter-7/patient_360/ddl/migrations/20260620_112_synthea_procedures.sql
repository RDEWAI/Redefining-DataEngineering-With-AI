-- migration: 20260620_012_synthea_procedures
-- layer: bronze  table: unity.bronze.synthea_procedures
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_procedures

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_procedures (
    START TIMESTAMP,
    STOP TIMESTAMP,
    PATIENT STRING,
    ENCOUNTER STRING,
    SYSTEM STRING,
    CODE BIGINT,
    DESCRIPTION STRING,
    BASE_COST DOUBLE,
    REASONCODE BIGINT,
    REASONDESCRIPTION STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_procedures'
