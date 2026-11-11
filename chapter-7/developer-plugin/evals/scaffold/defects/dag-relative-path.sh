#!/usr/bin/env bash
# Defect: add a second DAG that hardcodes application="run_local.py" so
# validate-dag must raise DAG-PATHS-001 on it.
set -euo pipefail
SRC="$DEST/patient_360/airflow/dags/patient360_hourly_v1.py"
BAD="$DEST/patient_360/airflow/dags/patient360_bad_paths.py"
cp "$SRC" "$BAD"
# Append a task that uses the forbidden relative application path.
cat >> "$BAD" <<'PY'


# --- injected for eval: forbidden relative application path ---
_bad_task = SparkSubmitOperator(
    task_id="bad_relative_path",
    application="run_local.py",
    conn_id="spark_default",
)
PY
