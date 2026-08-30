-- migration: 20260620_009_synthea_organizations
-- layer: bronze  table: unity.bronze.synthea_organizations
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_organizations

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_organizations (
    Id STRING,
    NAME STRING,
    ADDRESS STRING,
    CITY STRING,
    STATE STRING,
    ZIP STRING,
    LAT DOUBLE,
    LON DOUBLE,
    PHONE STRING,
    REVENUE DOUBLE,
    UTILIZATION BIGINT,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_organizations'
