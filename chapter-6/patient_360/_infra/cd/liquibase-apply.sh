#!/usr/bin/env bash
# Local CD smoke step — apply the project-wide Liquibase master changelog
# against the local Postgres (the Marquez backing DB doubles as a local
# DDL target per STORY-02-009). Fail-closed: any non-zero step exits the
# script with a non-zero status and a readable hint to stderr.
#
# Invocation (idempotent — Liquibase tracks applied changesets in
# DATABASECHANGELOG and skips already-applied ones):
#
#   bash _infra/cd/liquibase-apply.sh
#
# Env overrides (all optional):
#   COMPOSE              : docker compose binary             (default: "docker compose")
#   COMPOSE_FILE         : path to compose file              (default: _infra/docker/docker-compose.yml)
#   POSTGRES_SERVICE     : compose service name for Postgres (default: marquez-db)
#   POSTGRES_DB          : DB name                           (default: marquez)
#   POSTGRES_USER        : DB user                           (default: marquez)
#   POSTGRES_PASSWORD    : DB password                       (default: marquez)
#   LIQUIBASE_IMAGE      : Liquibase Docker image            (default: liquibase/liquibase:4.29)
#   CHANGELOG_FILE       : path inside container             (default: master-changelog.xml)
#
# The Liquibase container is networked onto the compose project's
# default network so it can reach the Postgres service by name.

set -euo pipefail

COMPOSE="${COMPOSE:-docker compose}"
COMPOSE_FILE="${COMPOSE_FILE:-_infra/docker/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-marquez-db}"
POSTGRES_DB="${POSTGRES_DB:-marquez}"
POSTGRES_USER="${POSTGRES_USER:-marquez}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-marquez}"
LIQUIBASE_IMAGE="${LIQUIBASE_IMAGE:-liquibase/liquibase:4.29}"
CHANGELOG_FILE="${CHANGELOG_FILE:-master-changelog.xml}"

# Resolve script-relative paths so the script works from any cwd.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
DDL_DIR="${PROJECT_ROOT}/ddl/liquibase"

if [ ! -f "${DDL_DIR}/${CHANGELOG_FILE}" ]; then
  echo "[liquibase-apply] CRITICAL: ${DDL_DIR}/${CHANGELOG_FILE} not found." >&2
  exit 2
fi

# Pre-flight: verify the Postgres service is up. ${COMPOSE} ps emits the
# service name when it is running; absent means we should not proceed.
cd -- "${PROJECT_ROOT}"
RUNNING_SERVICES="$(${COMPOSE} -f "${COMPOSE_FILE}" ps --status running --services 2>/dev/null || true)"
if ! printf '%s\n' "${RUNNING_SERVICES}" | grep -qx "${POSTGRES_SERVICE}"; then
  echo "[liquibase-apply] CRITICAL: compose service '${POSTGRES_SERVICE}' is not running." >&2
  echo "[liquibase-apply] Hint: \`make dev-up\` or \`${COMPOSE} -f ${COMPOSE_FILE} up -d ${POSTGRES_SERVICE}\`." >&2
  exit 3
fi

# Resolve the compose project network so the Liquibase container can
# reach the Postgres service by its compose service name.
COMPOSE_PROJECT="$(${COMPOSE} -f "${COMPOSE_FILE}" config --format json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("name",""))' 2>/dev/null || true)"
if [ -z "${COMPOSE_PROJECT}" ]; then
  COMPOSE_PROJECT="$(basename "$(dirname "${COMPOSE_FILE}")")"
fi
NETWORK="${COMPOSE_PROJECT}_default"

JDBC_URL="jdbc:postgresql://${POSTGRES_SERVICE}:5432/${POSTGRES_DB}"

echo "[liquibase-apply] Applying ${CHANGELOG_FILE} -> ${JDBC_URL}"

# Mount the project's ddl/liquibase directory into the standard
# Liquibase image and run `update`. The image's entrypoint already
# wraps the `liquibase` CLI.
docker run --rm \
  --network "${NETWORK}" \
  -v "${DDL_DIR}:/liquibase/changelog:ro" \
  "${LIQUIBASE_IMAGE}" \
  --url="${JDBC_URL}" \
  --username="${POSTGRES_USER}" \
  --password="${POSTGRES_PASSWORD}" \
  --changeLogFile="/liquibase/changelog/${CHANGELOG_FILE}" \
  --logLevel=info \
  update

echo "[liquibase-apply] OK -- applied ${CHANGELOG_FILE} against ${JDBC_URL}"
