-- migration: 20260620_008_synthea_observations
-- layer: bronze  table: unity.bronze.synthea_observations
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_observations

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_observations (
    DATE TIMESTAMP,
    PATIENT STRING,
    ENCOUNTER STRING,
    CATEGORY STRING,
    CODE STRING,
    DESCRIPTION STRING,
    VALUE STRING,
    UNITS STRING,
    TYPE STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_observations'
