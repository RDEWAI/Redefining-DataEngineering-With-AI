#!/usr/bin/env bash
# Defect: delete one per-table Bronze ingestion config so validate-ingestion
# must report "LLD §5.1 lists ingest_<table> but no config exists".
set -euo pipefail
rm -f "$DEST/patient_360/airflow/configs/claims.yml"
