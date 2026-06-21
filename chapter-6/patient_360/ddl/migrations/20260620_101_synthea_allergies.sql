-- migration: 20260620_001_synthea_allergies
-- layer: bronze  table: unity.bronze.synthea_allergies
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_allergies

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_allergies (
    START DATE,
    STOP STRING,
    PATIENT STRING,
    ENCOUNTER STRING,
    CODE BIGINT,
    SYSTEM STRING,
    DESCRIPTION STRING,
    TYPE STRING,
    CATEGORY STRING,
    REACTION1 STRING,
    DESCRIPTION1 STRING,
    SEVERITY1 STRING,
    REACTION2 STRING,
    DESCRIPTION2 STRING,
    SEVERITY2 STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_allergies'
