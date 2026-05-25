#!/usr/bin/env bash
# Local CD step — apply the project-wide Liquibase master changelog
# against the Postgres audit-trail database (Marquez backing DB).
#
# Per LLD v1.17 §13 Decision 17 (Revised 2026-05-23): Liquibase reverts
# to its pre-v1.16 Postgres-only audit-trail role. UC table registration
# moved to `scripts/bootstrap_uc_tables.py` (a one-shot Spark application
# using `UCSingleCatalog`) because `io.unitycatalog:unitycatalog-jdbc`
# is not published on Maven Central — the v1.16 UC-JDBC path was
# unbuildable.
#
# Invocation (idempotent — Liquibase tracks applied changesets in
# DATABASECHANGELOG and skips already-applied ones):
#
#   bash _infra/cd/liquibase-apply.sh
#
# Env overrides (all optional):
#   COMPOSE           : docker compose binary    (default: "docker compose")
#   COMPOSE_FILE      : path to compose file     (default: _infra/docker/docker-compose.yml)
#   LIQUIBASE_IMAGE   : Liquibase Docker image   (default: liquibase/liquibase:4.29)
#   CHANGELOG_FILE    : path inside container    (default: master-changelog.xml)
#   POSTGRES_SERVICE  : compose service name     (default: marquez-db)
#   POSTGRES_DB       : DB name                  (default: marquez)
#   POSTGRES_USER     : DB user                  (default: marquez)
#   POSTGRES_PASSWORD : DB password              (default: marquez)

set -euo pipefail

COMPOSE="${COMPOSE:-docker compose}"
COMPOSE_FILE="${COMPOSE_FILE:-_infra/docker/docker-compose.yml}"
LIQUIBASE_IMAGE="${LIQUIBASE_IMAGE:-liquibase/liquibase:4.29}"
CHANGELOG_FILE="${CHANGELOG_FILE:-master-changelog.xml}"

POSTGRES_SERVICE="${POSTGRES_SERVICE:-marquez-db}"
POSTGRES_DB="${POSTGRES_DB:-marquez}"
POSTGRES_USER="${POSTGRES_USER:-marquez}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-marquez}"

# Resolve script-relative paths so the script works from any cwd.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
DDL_DIR="${PROJECT_ROOT}/ddl/liquibase"

if [ ! -f "${DDL_DIR}/${CHANGELOG_FILE}" ]; then
  echo "[liquibase-apply] CRITICAL: ${DDL_DIR}/${CHANGELOG_FILE} not found." >&2
  exit 2
fi

cd -- "${PROJECT_ROOT}"

RUNNING_SERVICES="$(${COMPOSE} -f "${COMPOSE_FILE}" ps --status running --services 2>/dev/null || true)"
if ! printf '%s\n' "${RUNNING_SERVICES}" | grep -qx "${POSTGRES_SERVICE}"; then
  echo "[liquibase-apply] CRITICAL: compose service '${POSTGRES_SERVICE}' is not running." >&2
  echo "[liquibase-apply] Hint: \`make dev-up\` or \`${COMPOSE} -f ${COMPOSE_FILE} up -d ${POSTGRES_SERVICE}\`." >&2
  exit 3
fi

COMPOSE_PROJECT="$(${COMPOSE} -f "${COMPOSE_FILE}" config --format json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("name",""))' 2>/dev/null || true)"
if [ -z "${COMPOSE_PROJECT}" ]; then
  COMPOSE_PROJECT="$(basename "$(dirname "${COMPOSE_FILE}")")"
fi
NETWORK="${COMPOSE_PROJECT}_default"

JDBC_URL="jdbc:postgresql://${POSTGRES_SERVICE}:5432/${POSTGRES_DB}"
echo "[liquibase-apply] Applying ${CHANGELOG_FILE} -> ${JDBC_URL}"

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
