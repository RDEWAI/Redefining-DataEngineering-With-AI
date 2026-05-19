#!/usr/bin/env bash
# Bronze SQL launcher — interactive spark-sql REPL (or `-e "<query>"`) wired
# to the patient_360 dev stack: Delta + Spark's built-in Hive metastore
# (persistent Derby) + 1g driver memory. Intended for ad-hoc validation
# of Bronze tables and the SE stats table.
#
# Run from inside the airflow container:
#     docker exec -it patient_360-airflow /opt/patient_360/scripts/bsql.sh
# Or pipe a one-off query:
#     docker exec -it patient_360-airflow /opt/patient_360/scripts/bsql.sh -e "SHOW TABLES IN bronze;"
#
# Catalog wiring matches src/patient_360/utils/delta_helpers.py — keep
# the two in sync if the stack moves off Derby (e.g. to Postgres-backed
# Hive metastore or back to a UC integration).

set -euo pipefail

WAREHOUSE="${PATIENT360_WAREHOUSE_ROOT:-/tmp/uc-warehouse}"
METASTORE="${PATIENT360_METASTORE:-/tmp/patient360_metastore_db}"

exec spark-sql --master "local[2]" \
  --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
  --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog \
  --conf spark.sql.catalogImplementation=hive \
  --conf "spark.hadoop.javax.jdo.option.ConnectionURL=jdbc:derby:;databaseName=${METASTORE};create=true" \
  --conf "spark.sql.warehouse.dir=${WAREHOUSE}" \
  --packages io.delta:delta-spark_2.13:4.0.0 \
  --driver-memory 1g \
  "$@"
