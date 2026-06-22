-- migration: 20260620_005_synthea_encounters
-- layer: bronze  table: unity.bronze.synthea_encounters
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_encounters

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_encounters (
    Id STRING,
    START TIMESTAMP,
    STOP TIMESTAMP,
    PATIENT STRING,
    ORGANIZATION STRING,
    PROVIDER STRING,
    PAYER STRING,
    ENCOUNTERCLASS STRING,
    CODE BIGINT,
    DESCRIPTION STRING,
    BASE_ENCOUNTER_COST DOUBLE,
    TOTAL_CLAIM_COST DOUBLE,
    PAYER_COVERAGE DOUBLE,
    REASONCODE BIGINT,
    REASONDESCRIPTION STRING,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_encounters'
