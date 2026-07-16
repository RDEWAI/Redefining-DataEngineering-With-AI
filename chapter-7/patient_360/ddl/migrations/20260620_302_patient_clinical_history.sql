-- migration: 20260620_302_patient_clinical_history
-- layer: gold  table: unity.gold.patient_clinical_history
-- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
-- rollback: DROP TABLE IF EXISTS unity.gold.patient_clinical_history
-- Columns per DMS §4 patient_clinical_history (24 cols; no `ds`, full overwrite, no partition).

CREATE TABLE IF NOT EXISTS unity.gold.patient_clinical_history (
    encounter_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    first_name STRING NOT NULL,
    last_name STRING NOT NULL,
    birth_date DATE NOT NULL,
    encounter_class STRING,
    encounter_description STRING,
    start_date TIMESTAMP NOT NULL,
    stop_date TIMESTAMP,
    encounter_duration_hours DECIMAL(10,2),
    los_days INT,
    is_30_day_readmission BOOLEAN NOT NULL,
    provider_id STRING,
    provider_name STRING,
    organization_id STRING,
    organization_name STRING,
    reason_description STRING,
    condition_count INT NOT NULL,
    procedure_count INT NOT NULL,
    medication_count INT NOT NULL,
    observation_count INT NOT NULL,
    immunization_count INT NOT NULL,
    active_careplan_count INT NOT NULL,
    _ingested_at TIMESTAMP NOT NULL
) USING DELTA
LOCATION '${PATIENT360_WAREHOUSE_ROOT}/dev/gold/patient_clinical_history'
