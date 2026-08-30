-- migration: 20260620_013_synthea_providers
-- layer: bronze  table: unity.bronze.synthea_providers
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_providers

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_providers (
    Id STRING,
    ORGANIZATION STRING,
    NAME STRING,
    GENDER STRING,
    SPECIALITY STRING,
    ADDRESS STRING,
    CITY STRING,
    STATE STRING,
    ZIP STRING,
    LAT DOUBLE,
    LON DOUBLE,
    ENCOUNTERS BIGINT,
    PROCEDURES BIGINT,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_providers'
