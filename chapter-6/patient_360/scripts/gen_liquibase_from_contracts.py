"""Generate Liquibase changelogs from `contracts/*.yml`.

SUPERSEDED by LLD v1.17 §13 Decision 17 (Revised 2026-05-23). The v1.16
plan to apply these changelogs via Liquibase against UC OSS over the
open-source `io.unitycatalog:unitycatalog-jdbc` driver is abandoned —
the artifact is not published on Maven Central. UC table registration
now happens via `scripts/bootstrap_uc_tables.py` (a one-shot Spark
application that boots `UCSingleCatalog` DDL-only). This script is
no longer wired to `make bootstrap-uc`; disposition (delete vs repurpose
as a Postgres-changelog generator for the audit trail) is deferred to a
future `update-scaffold` pass.

Per LLD v1.16 §13 Decision 17 (original intent — superseded) —
contracts are the human-edited source of truth. This script regenerates
`ddl/liquibase/changelogs/{table}.xml` for every contract, replacing
the prior column-stub changelogs with real `CREATE TABLE IF NOT EXISTS
... USING DELTA LOCATION '...'` change-sets derived verbatim from the
contract.

Invocation:

    python scripts/gen_liquibase_from_contracts.py \
        [--contracts-dir contracts] \
        [--changelog-dir ddl/liquibase/changelogs] \
        [--env dev] \
        [--warehouse-root warehouse]

Idempotent: the generator is deterministic (stable column order from the
contract file, no timestamps in output, stable `id`/`author`). Running it
twice produces byte-identical XML files.

Failure modes raise non-zero exit so `make bootstrap-uc` halts before
Liquibase runs:

  exit 2  --  a YAML type cannot be mapped to a SQL/Delta type
  exit 3  --  required contract field is missing (`columns`, `schema`,
              `layer`, or the table name)
  exit 4  --  contracts directory is empty or missing

Per Decision 17, runtime writers stay path-based via DeltaCatalog and are
FORBIDDEN from calling `CREATE TABLE` — UC visibility is a deploy-time
invariant maintained exclusively by this generator + `liquibase-apply.sh`.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import yaml

logger = logging.getLogger("gen_liquibase_from_contracts")

# Map the contract YAML `type` vocabulary to the Delta-on-Spark SQL form
# accepted inside `CREATE TABLE ... USING DELTA`. Lower-cased keys; the
# input is normalised before lookup. Parametrised types (VARCHAR(100),
# DECIMAL(12,2)) are preserved verbatim from the contract — Delta/Spark
# accepts them as STRING / DECIMAL precision-hints respectively.
_TYPE_MAP: dict[str, str] = {
    "string": "STRING",
    "varchar": "STRING",
    "text": "STRING",
    "integer": "INT",
    "int": "INT",
    "bigint": "BIGINT",
    "long": "BIGINT",
    "smallint": "SMALLINT",
    "tinyint": "TINYINT",
    "double": "DOUBLE",
    "float": "FLOAT",
    "decimal": "DECIMAL",
    "numeric": "DECIMAL",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "binary": "BINARY",
}

# Domain inference per LLD §3.2. Used only when `domain:` is absent from
# the contract — most Bronze contracts omit it. Falls back to the table
# prefix when no rule matches (e.g. `synthea_*` -> `synthea`).
_DOMAIN_PREFIXES: dict[str, str] = {
    "synthea_": "synthea",
    "clinical_": "clinical",
    "reference_": "reference",
    "billing_": "billing",
    "patient_": "patient",
}


def _map_type(raw_type: str, table: str, column: str) -> str:
    """Map a contract YAML type to a Delta SQL type.

    Parametrised forms are preserved only for types Delta actually
    parametrises (DECIMAL(p,s)). VARCHAR(N) / STRING(N) collapse to
    bare STRING since Delta does not enforce string length.
    """
    if not raw_type:
        raise SystemExit(
            f"[gen-liquibase] CRITICAL: contract '{table}' column '{column}' "
            "has no `type` field."
        )
    parsed = raw_type.strip()
    # Common contract bug: bare flow-mapping `{type: DECIMAL(9,6)}` --
    # YAML splits the unquoted comma into two keys, leaving `type` set
    # to `DECIMAL(9` with no closing paren. Catch and explain.
    if parsed.count("(") != parsed.count(")"):
        raise SystemExit(
            f"[gen-liquibase] CRITICAL: contract '{table}' column '{column}' "
            f"has unbalanced parens in type '{raw_type}'. Likely a YAML "
            "flow-mapping bug -- quote the type: `type: \"DECIMAL(9,6)\"`."
        )
    m = re.match(r"^([A-Za-z]+)(\s*\(.*\))?$", parsed)
    if not m:
        # Complex / unknown form (e.g. array<string>) -- pass through.
        return parsed.upper()
    base, params = m.group(1).lower(), m.group(2) or ""
    if base not in _TYPE_MAP:
        raise SystemExit(
            f"[gen-liquibase] CRITICAL: contract '{table}' column '{column}' has "
            f"unmappable type '{raw_type}'. Add it to _TYPE_MAP in "
            "scripts/gen_liquibase_from_contracts.py."
        )
    delta_type = _TYPE_MAP[base]
    # Delta only parametrises DECIMAL/NUMERIC. Strip params from
    # length-only string types so the emitted DDL parses cleanly.
    if delta_type == "DECIMAL":
        return f"DECIMAL{params}"
    return delta_type


def _infer_domain(contract: dict[str, Any], table: str) -> str:
    """Resolve domain: explicit `domain:` wins; else prefix; else table name."""
    if contract.get("domain"):
        return str(contract["domain"]).strip()
    for prefix, domain in _DOMAIN_PREFIXES.items():
        if table.startswith(prefix):
            return domain
    return table


def _render_change_log(
    *,
    table: str,
    schema: str,
    layer: str,
    domain: str,
    columns: list[dict[str, Any]],
    location: str,
) -> str:
    """Render a single `<databaseChangeLog>` XML document. Deterministic."""
    column_lines: list[str] = []
    for col in columns:
        name = col.get("name")
        raw_type = col.get("type")
        if not name:
            raise SystemExit(
                f"[gen-liquibase] CRITICAL: contract '{table}' has a "
                "column entry missing `name`."
            )
        sql_type = _map_type(raw_type, table, name)
        nullable = col.get("nullable", True)
        null_clause = "" if nullable else " NOT NULL"
        column_lines.append(f"    {name} {sql_type}{null_clause}")

    # Bronze ingestion-control columns are appended by the runner --
    # changelog only contains the contract's declared schema. The runner
    # is responsible for `ds`, `_ingested_at`, `_source_batch_id`,
    # `_source_file` on the Bronze layer (LLD §5.1). The Delta table
    # tolerates Spark adding those at write time without DDL drift.
    columns_sql = ",\n".join(column_lines)

    change_set_id = f"create-{layer}-{table}"
    statement = (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"{columns_sql}\n"
        f") USING DELTA\n"
        f"LOCATION '{location}'"
    )

    # `escape` only handles &<>; CDATA already isolates the SQL body so
    # no per-statement escape is needed. We escape attribute values only.
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<databaseChangeLog\n'
        '    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"\n'
        '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        '    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog\n'
        '        http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.20.xsd">\n'
        "\n"
        f'  <changeSet id="{escape(change_set_id)}" author="patient_360">\n'
        '    <sql splitStatements="false"><![CDATA[\n'
        f"{statement}\n"
        "]]></sql>\n"
        "    <rollback>\n"
        f"      <sql>DROP TABLE IF EXISTS {schema}.{table}</sql>\n"
        "    </rollback>\n"
        "  </changeSet>\n"
        "\n"
        "</databaseChangeLog>\n"
    )


def _load_contract(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise SystemExit(
            f"[gen-liquibase] CRITICAL: contract '{path}' does not parse to a dict."
        )
    for required in ("table", "schema", "layer"):
        if not raw.get(required):
            raise SystemExit(
                f"[gen-liquibase] CRITICAL: contract '{path}' missing "
                f"required field `{required}`."
            )
    # `columns:` may legitimately be empty for Silver/Gold contracts that
    # have not yet been populated by the create-silver / create-gold
    # skills. Those are skipped (status SKIP-EMPTY) so the generator
    # remains usable while the project is still under construction.
    return raw


def generate(
    *,
    contracts_dir: Path,
    changelog_dir: Path,
    env: str,
    warehouse_root: str,
) -> list[tuple[str, str]]:
    """Generate one changelog per contract. Returns a list of (table, status)."""
    if not contracts_dir.is_dir():
        raise SystemExit(
            f"[gen-liquibase] CRITICAL: contracts dir '{contracts_dir}' does not exist."
        )
    contract_files = sorted(p for p in contracts_dir.glob("*.yml") if p.is_file())
    if not contract_files:
        raise SystemExit(
            f"[gen-liquibase] CRITICAL: no `*.yml` contracts found under '{contracts_dir}'."
        )

    changelog_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, str]] = []

    for cpath in contract_files:
        contract = _load_contract(cpath)
        table = str(contract["table"]).strip()
        schema = str(contract["schema"]).strip()
        layer = str(contract["layer"]).strip()
        domain = _infer_domain(contract, table)

        columns = contract.get("columns") or []
        if not isinstance(columns, list) or not columns:
            # Silver/Gold contracts not yet populated by create-silver /
            # create-gold. Leave the existing stub changelog intact.
            results.append((table, "SKIP-EMPTY"))
            logger.info(
                "skipping table %s -- contract %s has no `columns:` populated yet",
                table,
                cpath,
            )
            continue

        location = f"{warehouse_root.rstrip('/')}/{env}/{layer}/{domain}/{table}/"
        xml = _render_change_log(
            table=table,
            schema=schema,
            layer=layer,
            domain=domain,
            columns=columns,
            location=location,
        )
        out_path = changelog_dir / f"{table}.xml"
        prior = out_path.read_text() if out_path.exists() else None
        if prior == xml:
            results.append((table, "MATCH"))
        else:
            out_path.write_text(xml)
            results.append((table, "WROTE" if prior is None else "REWROTE"))
        logger.info("registered table %s -> %s", table, out_path)

    return results


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--contracts-dir",
        default="contracts",
        help="Directory containing per-table contracts (default: contracts/).",
    )
    p.add_argument(
        "--changelog-dir",
        default="ddl/liquibase/changelogs",
        help="Output directory for per-table changelogs.",
    )
    p.add_argument(
        "--env",
        default="dev",
        help="Environment selector embedded into the LOCATION path (default: dev).",
    )
    p.add_argument(
        "--warehouse-root",
        default="warehouse",
        help=(
            "Warehouse root prefix used to build the per-table LOCATION "
            "(default: warehouse). Resolved relative to the project root "
            "unless given as an absolute path."
        ),
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Emit INFO logs (one line per registered table).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    results = generate(
        contracts_dir=Path(args.contracts_dir),
        changelog_dir=Path(args.changelog_dir),
        env=args.env,
        warehouse_root=args.warehouse_root,
    )
    for table, status in results:
        print(f"{status:<7} {table}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
