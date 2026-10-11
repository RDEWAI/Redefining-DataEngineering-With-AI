---
type: regex
target: { source: file, path: patient_360/airflow/dags/patient360_hourly_v1.py }
pattern: 'application\s*=\s*"run_local\.py"'
match: not_contains
---
