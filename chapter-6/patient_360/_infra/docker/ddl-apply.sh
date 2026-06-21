#!/usr/bin/env bash
# One-shot DDL applier (LLD §9.1.1, §13 Decision 12).
#
# Applies plain dated .sql migration files in lexical order (= dated +
# zero-padded sequence, bronze -> silver -> gold) via the beeline client
# bundled in the Spark Thrift Server image:
#
#     beeline -u jdbc:hive2://spark-thrift-server:10000/<UC_CATALOG> -f <file.sql>
#
# Liquibase was REMOVED (developer-plugin L-015): on Unity Catalog OSS +
# Spark Thrift there is no working Liquibase path — core Liquibase has no
# Spark SQL dialect and the Apache Hive JDBC driver is too incomplete to
# connect/track; the only Delta/UC-aware option (the liquibase-databricks
# extension) is welded to the Databricks JDBC driver, which NPEs in
# DatabricksConnectionContext.buildCompute() without a Databricks `httpPath`
# (it requires Databricks compute, not a local Spark Thrift). Proven
# empirically. So DDL lives as plain .sql under ddl/migrations/ — no
# Liquibase XML, no master-changelog, no regex-on-XML extraction.
#
# Each migration: ddl/migrations/<YYYYMMDD>_<NNN>_<table>.sql — a
# `CREATE TABLE IF NOT EXISTS ... USING DELTA ... LOCATION '...'` with
# ${PATIENT360_WAREHOUSE_ROOT} (substituted here; beeline does not expand
# env vars). The `-- ...` header lines (incl. `-- rollback: DROP ...`) are
# SQL comments and are ignored by beeline.
#
# Invoked as the `ddl-apply` compose service (one-shot) after the
# spark-thrift-server reports healthy, and by `make ddl-apply`.
#
# Env (all optional — defaults match the compose wiring):
#   DDL_DIR            : migrations dir inside the container  (default: /ddl/migrations)
#   THRIFT_HOST        : Spark Thrift Server host             (default: spark-thrift-server)
#   THRIFT_PORT        : HiveServer2 port                     (default: 10000)
#   UC_CATALOG         : default catalog in the JDBC URL      (default: unity)
#   DDL_LAYERS         : optional space-separated layer allow-list matched on
#                        each file's `-- layer: <name>` header (e.g.
#                        "bronze silver" to skip stubbed gold). Empty = all.
#   PATIENT360_WAREHOUSE_ROOT : substituted into LOCATION '...' (must be exported)
set -euo pipefail

DDL_DIR="${DDL_DIR:-/ddl/migrations}"
THRIFT_HOST="${THRIFT_HOST:-spark-thrift-server}"
THRIFT_PORT="${THRIFT_PORT:-10000}"
UC_CATALOG="${UC_CATALOG:-unity}"
DDL_LAYERS="${DDL_LAYERS:-}"
JDBC_URL="jdbc:hive2://${THRIFT_HOST}:${THRIFT_PORT}/${UC_CATALOG}"

# Ordered list of migrations. Filenames are dated + zero-padded sequence, so a
# plain lexical sort gives the intended bronze -> silver -> gold apply order.
mapfile -t MIGRATIONS < <(ls "${DDL_DIR}"/*.sql 2>/dev/null | sort)

if [ "${#MIGRATIONS[@]}" -eq 0 ]; then
  echo "[ddl-apply] CRITICAL: no .sql migrations found in ${DDL_DIR}." >&2
  exit 2
fi

echo "[ddl-apply] Applying ${#MIGRATIONS[@]} migration(s) from ${DDL_DIR} -> ${JDBC_URL}"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
applied=0

for mig in "${MIGRATIONS[@]}"; do
  # Optional layer allow-list (reads the `-- layer: <name>` header line).
  if [ -n "${DDL_LAYERS}" ]; then
    lyr="$(sed -nE 's/^-- layer:[[:space:]]*([a-z]+).*/\1/p' "${mig}" | head -1)"
    case " ${DDL_LAYERS} " in
      *" ${lyr} "*) : ;;
      *) echo "[ddl-apply] skip (${lyr:-?}) $(basename "${mig}")"; continue ;;
    esac
  fi

  out="${WORK}/$(basename "${mig}")"
  # Substitute ${VAR} from the environment (beeline does not expand env vars).
  python3 - "${mig}" > "${out}" <<'PYEOF'
import os, re, sys
text = open(sys.argv[1], encoding="utf-8").read()
sys.stdout.write(
    re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
           lambda g: os.environ.get(g.group(1), g.group(0)), text)
)
PYEOF

  # Ensure a trailing ';' so beeline -f executes the final statement.
  if [ "$(tail -c1 "${out}")" != ";" ]; then
    printf ';\n' >> "${out}"
  fi

  echo "[ddl-apply] -> $(basename "${mig}")"
  # beeline ships under $SPARK_HOME/bin in the apache/spark image but is NOT
  # on PATH — invoke by absolute path or it dies "command not found".
  "${SPARK_HOME:-/opt/spark}/bin/beeline" -u "${JDBC_URL}" --silent=true -f "${out}"
  applied=$((applied + 1))
done

echo "[ddl-apply] OK -- applied ${applied} migration(s) against ${JDBC_URL}"
