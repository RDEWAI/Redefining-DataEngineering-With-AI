#!/usr/bin/env bash
# Local CD smoke step — re-sync the Airflow DAG bag in the running
# Airflow container and assert it reports no DAG import errors.
#
# The compose file bind-mounts `airflow/dags/` into the Airflow
# container (see _infra/docker/docker-compose.yml volumes), so this
# script does not copy files in. It only forces a reserialize and then
# inspects the import-error report.
#
# Fail-closed: exits non-zero on any reserialize failure OR if
# `airflow dags list-import-errors` lists ANY error.
#
# Env overrides:
#   COMPOSE              : docker compose binary             (default: "docker compose")
#   COMPOSE_FILE         : path to compose file              (default: _infra/docker/docker-compose.yml)
#   AIRFLOW_SERVICE      : compose service name for Airflow  (default: airflow)

set -euo pipefail

COMPOSE="${COMPOSE:-docker compose}"
COMPOSE_FILE="${COMPOSE_FILE:-_infra/docker/docker-compose.yml}"
AIRFLOW_SERVICE="${AIRFLOW_SERVICE:-airflow}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd -- "${PROJECT_ROOT}"

# Pre-flight: Airflow service must be running.
RUNNING_SERVICES="$(${COMPOSE} -f "${COMPOSE_FILE}" ps --status running --services 2>/dev/null || true)"
if ! printf '%s\n' "${RUNNING_SERVICES}" | grep -qx "${AIRFLOW_SERVICE}"; then
  echo "[airflow-sync] CRITICAL: compose service '${AIRFLOW_SERVICE}' is not running." >&2
  echo "[airflow-sync] Hint: \`make dev-up\` or \`${COMPOSE} -f ${COMPOSE_FILE} up -d ${AIRFLOW_SERVICE}\`." >&2
  exit 3
fi

echo "[airflow-sync] Reserializing DAG bag in service '${AIRFLOW_SERVICE}'"
${COMPOSE} -f "${COMPOSE_FILE}" exec -T "${AIRFLOW_SERVICE}" airflow dags reserialize

echo "[airflow-sync] Listing DAG import errors"
# `list-import-errors` exits 0 even when errors exist — we have to read
# the output to gate on it. Strip the table border lines and the column
# header so that "no errors" yields an empty stream.
IMPORT_ERRORS="$(
  ${COMPOSE} -f "${COMPOSE_FILE}" exec -T "${AIRFLOW_SERVICE}" \
    airflow dags list-import-errors 2>&1 \
  | sed -E '/^[[:space:]]*$/d; /^=+$/d; /^-+$/d; /^filepath[[:space:]]+\|[[:space:]]+error/Id; /No data found/Id'
)"

if [ -n "${IMPORT_ERRORS}" ]; then
  echo "[airflow-sync] CRITICAL: airflow reported DAG import errors:" >&2
  printf '%s\n' "${IMPORT_ERRORS}" >&2
  exit 4
fi

echo "[airflow-sync] OK -- DAG bag reserialized, no import errors"
