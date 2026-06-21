-- migration: 20260620_010_synthea_patients
-- layer: bronze  table: unity.bronze.synthea_patients
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.bronze.synthea_patients

CREATE TABLE IF NOT EXISTS unity.bronze.synthea_patients (
    Id STRING NOT NULL,
    BIRTHDATE DATE,
    DEATHDATE DATE,
    SSN STRING,
    DRIVERS STRING,
    PASSPORT STRING,
    PREFIX STRING,
    FIRST STRING,
    MIDDLE STRING,
    LAST STRING,
    SUFFIX STRING,
    MAIDEN STRING,
    MARITAL STRING,
    RACE STRING,
    ETHNICITY STRING,
    GENDER STRING,
    BIRTHPLACE STRING,
    ADDRESS STRING,
    CITY STRING,
    STATE STRING,
    COUNTY STRING,
    FIPS BIGINT,
    ZIP STRING,
    LAT DOUBLE,
    LON DOUBLE,
    HEALTHCARE_EXPENSES DOUBLE,
    HEALTHCARE_COVERAGE DOUBLE,
    INCOME BIGINT,
    ds DATE NOT NULL,
    _ingested_at TIMESTAMP NOT NULL,
    _source_batch_id STRING NOT NULL,
    _source_file STRING
) USING DELTA
PARTITIONED BY (ds)
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/bronze/synthea_patients'
