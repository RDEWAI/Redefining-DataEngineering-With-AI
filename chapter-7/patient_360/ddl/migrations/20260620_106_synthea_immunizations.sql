-- migration: 20260620_006_synthea_immunizations
-- layer: bronze  table: unity.bronze.synthea_immunizations
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_immunizations

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_immunizations (
    DATE TIMESTAMP,
    PATIENT STRING,
    ENCOUNTER STRING,
    CODE STRING,
    DESCRIPTION STRING,
    BASE_COST DOUBLE,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_immunizations'
