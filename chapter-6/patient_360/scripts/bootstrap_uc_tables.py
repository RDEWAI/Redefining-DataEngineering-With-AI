"""Bootstrap Unity Catalog OSS tables from ``contracts/*.yml``.

Per LLD v1.18 §13 Decision 17 (Revised 2026-05-23 second pivot) —
deploy-time UC table registration via a **pure-Python REST client**.

This script supersedes the v1.17 catalog-binding approach which proved
unbuildable on the project's Spark 4.x stack (binary-incompat connector
on Maven Central as of 2026-05-23). The UC OSS REST API is the only
integration path that works today.

Hard rules:

  * This script talks plain HTTP to the UC OSS REST API and nothing
    else. It uses ``httpx`` (with a stdlib ``urllib.request`` fallback)
    and does not import any Spark or database client library.
  * Runtime DAG tasks continue to use ``DeltaCatalog`` per LLD §13
    Decision 12 — this script does not touch the runtime catalog.
  * Every operation is GET-before-POST, so re-runs are idempotent.
  * Runtime writers stay path-based via ``DeltaCatalog`` and are
    FORBIDDEN from calling ``CREATE TABLE`` (STORY-03-001 AC8-AC10).
    UC visibility is exclusively this script's responsibility.
  * Failures are accumulated and surfaced at the end with a non-zero
    exit code — every contract is attempted, no first-failure abort.

Invocation:

    python scripts/bootstrap_uc_tables.py [--env dev|stage|prod]

Contracts: any ``contracts/*.yml`` with a populated ``columns:`` list is
registered. Contracts with ``columns: []`` are SKIPPED with a warning —
nothing to register yet.

Warehouse path layout (LLD §3.2 + §9.1):

    <warehouse_root>/<env>/<layer>/<domain>/<table>/

Where:
    warehouse_root = ${PATIENT360_WAREHOUSE_ROOT}
                     (default: ${PATIENT360_PROJECT_ROOT}/warehouse;
                      fallback: ./warehouse)
    env            = --env arg (lowercased)
    layer          = contract.layer (bronze | silver | gold)
    domain         = contract.domain  OR  the prefix of the table name
                     up to the first underscore (synthea_patients
                     -> "synthea"; clinical_patients -> "clinical";
                     patient_summary -> "patient";
                     reference_organizations -> "reference";
                     billing_claims -> "billing")
    table          = contract.table

Env-var overrides (LLD v1.18 §7.1 catalog block):

    UC_BOOTSTRAP_CATALOG_NAME (default: ``unity``) — UC catalog name
        every schema/table is registered under.
    UC_BOOTSTRAP_URI (default: ``http://localhost:8080``) — UC OSS
        REST endpoint base URL. DEV default is ``localhost`` because
        host-side ``make bootstrap-uc`` invocations cannot resolve the
        compose-internal hostname ``unity-catalog`` (would fail with
        ``UnresolvedAddressException``). STAGING/PROD may set
        ``http://unity-catalog:8080`` if invoked from inside the
        compose network.
    UC_BOOTSTRAP_TIMEOUT_SECONDS (default: ``30``) — per-request HTTP
        timeout passed to the client.
    PATIENT360_WAREHOUSE_ROOT — absolute warehouse root for
        ``storage_location`` (default: ``${PATIENT360_PROJECT_ROOT}/warehouse``,
        falling back to ``./warehouse``).
    PATIENT360_PROJECT_ROOT — project anchor used to resolve
        ``contracts/`` and the default warehouse root.

Exit codes:

  0   --  Every populated contract registered (or already present).
  2   --  No populated contracts found under ``contracts/``.
  3   --  At least one schema or table registration failed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("bootstrap_uc_tables")

DEFAULT_UC_BOOTSTRAP_CATALOG_NAME = "unity"
# DEV default = host-reachable URL. Host-side `make bootstrap-uc`
# invocations cannot resolve the compose-internal hostname
# `unity-catalog` (UnresolvedAddressException). STAGING/PROD may override
# to `http://unity-catalog:8080` if run from inside the compose network.
DEFAULT_UC_BOOTSTRAP_URI = "http://localhost:8080"
DEFAULT_UC_BOOTSTRAP_TIMEOUT_SECONDS = 30

# UC OSS REST API path prefixes (v2.1 per UC OSS 0.4.x).
SCHEMAS_PATH = "/api/2.1/unity-catalog/schemas"
TABLES_PATH = "/api/2.1/unity-catalog/tables"


# DuckDB / contract type vocabulary -> UC column type spec. UC OSS column
# `type_name` follows the Spark logical-type vocabulary. Kept narrow on
# purpose — anything outside this list trips an explicit error so the
# operator sees an unmapped type instead of a silent guess.
_TYPE_MAP: dict[str, dict[str, Any]] = {
    "string":       {"type_name": "STRING"},
    "varchar":      {"type_name": "STRING"},
    "text":         {"type_name": "STRING"},
    "int":          {"type_name": "INT"},
    "integer":      {"type_name": "INT"},
    "long":         {"type_name": "LONG"},
    "bigint":       {"type_name": "LONG"},
    "short":        {"type_name": "SHORT"},
    "smallint":     {"type_name": "SHORT"},
    "byte":         {"type_name": "BYTE"},
    "tinyint":      {"type_name": "BYTE"},
    "float":        {"type_name": "FLOAT"},
    "double":       {"type_name": "DOUBLE"},
    "boolean":      {"type_name": "BOOLEAN"},
    "bool":         {"type_name": "BOOLEAN"},
    "date":         {"type_name": "DATE"},
    "timestamp":    {"type_name": "TIMESTAMP"},
    "timestamp_ntz": {"type_name": "TIMESTAMP_NTZ"},
    "binary":       {"type_name": "BINARY"},
    "bytes":        {"type_name": "BINARY"},
}


def _resolve_project_root() -> Path:
    """Project root = script's parent directory (script lives in scripts/)."""
    env_root = os.environ.get("PATIENT360_PROJECT_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parent.parent


def _resolve_warehouse_root(project_root: Path) -> Path:
    env_root = os.environ.get("PATIENT360_WAREHOUSE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return (project_root / "warehouse").resolve()


def _column_type_spec(raw: str) -> dict[str, Any]:
    """Resolve a contract column type to a UC REST column type spec.

    UC OSS REST API expects each column to carry both `type_name`
    (logical type) and `type_text` (the textual rendering). For
    parameterized types like DECIMAL(p,s) or VARCHAR(n), we expand
    them into the correct logical form.

    Returns a dict with `type_name`, `type_text`, and (for DECIMAL)
    `type_precision` + `type_scale`.
    """
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("empty column type")
    # Parameterized SQL standard types — pass through uppercased.
    if "(" in cleaned and cleaned.endswith(")"):
        base = cleaned.split("(", 1)[0].strip().upper()
        params = cleaned.split("(", 1)[1][:-1]
        if base in {"VARCHAR", "CHAR"}:
            return {"type_name": "STRING", "type_text": "string"}
        if base in {"DECIMAL", "NUMERIC"}:
            try:
                precision_s, scale_s = (p.strip() for p in params.split(","))
                precision = int(precision_s)
                scale = int(scale_s)
            except ValueError as exc:
                raise ValueError(
                    f"unparseable DECIMAL spec '{raw}'"
                ) from exc
            return {
                "type_name": "DECIMAL",
                "type_text": f"decimal({precision},{scale})",
                "type_precision": precision,
                "type_scale": scale,
            }
    key = cleaned.lower()
    if key in _TYPE_MAP:
        spec = dict(_TYPE_MAP[key])
        spec["type_text"] = spec["type_name"].lower()
        return spec
    # Last-resort passthrough for already-uppercase logical types.
    upper = cleaned.upper()
    if upper in {
        "STRING", "INT", "LONG", "SHORT", "BYTE", "FLOAT", "DOUBLE",
        "BOOLEAN", "DATE", "TIMESTAMP", "TIMESTAMP_NTZ", "BINARY",
    }:
        return {"type_name": upper, "type_text": upper.lower()}
    raise ValueError(
        f"unmapped column type '{raw}'. "
        f"Add a mapping in bootstrap_uc_tables._TYPE_MAP."
    )


def _derive_domain(contract: dict[str, Any]) -> str:
    """Resolve <domain> for the warehouse path.

    Priority:
      1. ``contract['domain']`` if explicitly set.
      2. Prefix of the table name up to the first underscore. This
         matches every Phase-1 table family:
         ``synthea_*``  -> synthea
         ``clinical_*`` -> clinical
         ``reference_*`` -> reference
         ``billing_*``  -> billing
         ``patient_*``  -> patient
    """
    explicit = contract.get("domain")
    if explicit:
        return str(explicit).strip()
    table = str(contract["table"]).strip()
    if "_" not in table:
        return table
    return table.split("_", 1)[0]


def _load_contract(path: Path) -> dict[str, Any] | None:
    """Load a contract YAML; return None if it has no populated columns."""
    with path.open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    if not isinstance(doc, dict):
        logger.warning("%s: top-level YAML is not a mapping; skipping", path)
        return None
    cols = doc.get("columns") or []
    if not cols:
        return None
    required = ("table", "layer", "schema")
    missing = [k for k in required if not doc.get(k)]
    if missing:
        logger.warning(
            "%s: missing required fields %s; skipping", path, ",".join(missing)
        )
        return None
    return doc


def _build_columns_payload(columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a contract `columns` list to the UC REST `columns` payload.

    UC OSS REST API column spec fields (per UC OSS 0.4.x):
      - name              (str)
      - type_name         (logical type — STRING / LONG / DECIMAL / ...)
      - type_text         (textual rendering — string / long / decimal(38,18) / ...)
      - type_json         (JSON schema for the type — kept minimal here)
      - nullable          (bool)
      - position          (zero-based ordinal)
    """
    out: list[dict[str, Any]] = []
    for idx, col in enumerate(columns):
        name = str(col["name"]).strip()
        if not name:
            raise ValueError("column with empty name")
        spec = _column_type_spec(str(col.get("type", "")))
        nullable = bool(col.get("nullable", True))
        entry: dict[str, Any] = {
            "name": name,
            "type_name": spec["type_name"],
            "type_text": spec["type_text"],
            "type_json": json.dumps(
                {
                    "name": name,
                    "type": spec["type_text"],
                    "nullable": nullable,
                    "metadata": {},
                }
            ),
            "nullable": nullable,
            "position": idx,
        }
        if spec["type_name"] == "DECIMAL":
            entry["type_precision"] = spec["type_precision"]
            entry["type_scale"] = spec["type_scale"]
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Minimal HTTP client.  Prefers httpx (project dep); falls back to stdlib
# urllib.request so the script keeps working in any Python 3.12 env.
# ---------------------------------------------------------------------------


class _RestClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._httpx = self._try_import_httpx()
        if self._httpx is not None:
            self._client = self._httpx.Client(timeout=timeout)
        else:
            self._client = None

    @staticmethod
    def _try_import_httpx() -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover - env-specific
            return None
        return httpx

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[int, Any]:
        url = self.base_url + path
        if self._httpx is not None:
            resp = self._client.get(url, params=params or {})
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            return resp.status_code, body
        # stdlib fallback
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError

        if params:
            url = f"{url}?{urlencode(params)}"
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = raw.decode("utf-8", errors="replace")
        return status, body

    def post(self, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
        url = self.base_url + path
        if self._httpx is not None:
            resp = self._client.post(url, json=payload)
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            return resp.status_code, body
        # stdlib fallback
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError

        data = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = raw.decode("utf-8", errors="replace")
        return status, body


# ---------------------------------------------------------------------------
# Registration logic — GET-before-POST per object for idempotence.
# ---------------------------------------------------------------------------


def _list_schemas(client: _RestClient, catalog_name: str) -> set[str]:
    status, body = client.get(
        SCHEMAS_PATH, params={"catalog_name": catalog_name}
    )
    if status >= 400:
        raise RuntimeError(
            f"GET {SCHEMAS_PATH}?catalog_name={catalog_name} -> {status}: {body}"
        )
    items = (body or {}).get("schemas") if isinstance(body, dict) else None
    return {str(s.get("name")) for s in (items or [])}


def _list_tables(
    client: _RestClient, catalog_name: str, schema_name: str
) -> set[str]:
    status, body = client.get(
        TABLES_PATH,
        params={"catalog_name": catalog_name, "schema_name": schema_name},
    )
    if status >= 400:
        raise RuntimeError(
            f"GET {TABLES_PATH}?catalog_name={catalog_name}"
            f"&schema_name={schema_name} -> {status}: {body}"
        )
    items = (body or {}).get("tables") if isinstance(body, dict) else None
    return {str(t.get("name")) for t in (items or [])}


def _create_schema(
    client: _RestClient, catalog_name: str, schema_name: str
) -> None:
    payload = {"name": schema_name, "catalog_name": catalog_name}
    status, body = client.post(SCHEMAS_PATH, payload)
    if status >= 400:
        raise RuntimeError(
            f"POST {SCHEMAS_PATH} {payload} -> {status}: {body}"
        )


def _create_table(
    client: _RestClient,
    *,
    catalog_name: str,
    schema_name: str,
    table_name: str,
    columns: list[dict[str, Any]],
    storage_location: str,
) -> None:
    payload = {
        "name": table_name,
        "catalog_name": catalog_name,
        "schema_name": schema_name,
        "table_type": "EXTERNAL",
        "data_source_format": "DELTA",
        "columns": columns,
        "storage_location": storage_location,
    }
    status, body = client.post(TABLES_PATH, payload)
    if status >= 400:
        raise RuntimeError(
            f"POST {TABLES_PATH} name={table_name} -> {status}: {body}"
        )


def _register_contracts(
    *,
    client: _RestClient,
    contracts: list[dict[str, Any]],
    catalog_name: str,
    warehouse_root: Path,
    env: str,
) -> tuple[int, int]:
    """Register every contract. Returns (n_ok, n_fail). Accumulates errors."""
    n_ok = 0
    n_fail = 0
    # Cache per-schema table listings to avoid GET-per-table-in-same-schema.
    schemas_present: set[str] = _list_schemas(client, catalog_name)
    tables_present: dict[str, set[str]] = {}

    for contract in contracts:
        table = str(contract["table"])
        layer = str(contract["layer"])
        schema = str(contract["schema"])
        domain = _derive_domain(contract)

        # 1. Ensure schema exists.
        if schema not in schemas_present:
            try:
                _create_schema(client, catalog_name, schema)
                schemas_present.add(schema)
                logger.info(
                    "POST schema created catalog=%s schema=%s",
                    catalog_name,
                    schema,
                )
            except Exception as exc:
                logger.error(
                    "POST schema failed catalog=%s schema=%s: %s",
                    catalog_name,
                    schema,
                    exc,
                )
                n_fail += 1
                continue
        else:
            logger.info(
                "schema present (skip) catalog=%s schema=%s",
                catalog_name,
                schema,
            )

        # 2. Ensure table exists.
        if schema not in tables_present:
            try:
                tables_present[schema] = _list_tables(
                    client, catalog_name, schema
                )
            except Exception as exc:
                logger.error(
                    "GET tables failed catalog=%s schema=%s: %s",
                    catalog_name,
                    schema,
                    exc,
                )
                n_fail += 1
                continue

        if table in tables_present[schema]:
            logger.info(
                "table present (skip) catalog=%s schema=%s table=%s",
                catalog_name,
                schema,
                table,
            )
            n_ok += 1
            continue

        try:
            columns_payload = _build_columns_payload(
                contract.get("columns") or []
            )
            storage_location = (
                f"{warehouse_root}/{env}/{layer}/{domain}/{table}/"
            )
            _create_table(
                client,
                catalog_name=catalog_name,
                schema_name=schema,
                table_name=table,
                columns=columns_payload,
                storage_location=storage_location,
            )
            tables_present[schema].add(table)
            n_ok += 1
            logger.info(
                "POST table created catalog=%s schema=%s table=%s "
                "storage_location=%s",
                catalog_name,
                schema,
                table,
                storage_location,
            )
        except Exception as exc:
            logger.error(
                "POST table failed catalog=%s schema=%s table=%s: %s",
                catalog_name,
                schema,
                table,
                exc,
            )
            n_fail += 1
    return n_ok, n_fail


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--env",
        default="dev",
        choices=("dev", "stage", "prod"),
        help="Environment selector (default: dev).",
    )
    p.add_argument(
        "--contracts-dir",
        default=None,
        help="Override contracts directory (default: <project_root>/contracts).",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Emit INFO logs (default: WARNING).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    project_root = _resolve_project_root()
    warehouse_root = _resolve_warehouse_root(project_root)
    contracts_dir = (
        Path(args.contracts_dir).resolve()
        if args.contracts_dir
        else project_root / "contracts"
    )
    if not contracts_dir.is_dir():
        logger.error(
            "contracts/ directory not found at %s "
            "(set PATIENT360_PROJECT_ROOT or pass --contracts-dir)",
            contracts_dir,
        )
        return 2

    catalog_name = os.environ.get(
        "UC_BOOTSTRAP_CATALOG_NAME", DEFAULT_UC_BOOTSTRAP_CATALOG_NAME
    )
    uc_uri = os.environ.get("UC_BOOTSTRAP_URI", DEFAULT_UC_BOOTSTRAP_URI)
    timeout = float(
        os.environ.get(
            "UC_BOOTSTRAP_TIMEOUT_SECONDS",
            DEFAULT_UC_BOOTSTRAP_TIMEOUT_SECONDS,
        )
    )

    logger.info(
        "bootstrap-uc start: env=%s catalog=%s uri=%s timeout=%ss "
        "warehouse_root=%s contracts_dir=%s",
        args.env,
        catalog_name,
        uc_uri,
        timeout,
        warehouse_root,
        contracts_dir,
    )

    contracts: list[dict[str, Any]] = []
    for path in sorted(contracts_dir.glob("*.yml")):
        doc = _load_contract(path)
        if doc is None:
            continue
        contracts.append(doc)

    if not contracts:
        logger.error(
            "No contracts under %s have a populated `columns:` list. "
            "Run sync_bronze_contracts.py first or populate Silver/Gold "
            "columns from the DMS.",
            contracts_dir,
        )
        return 2

    logger.info("registering %d contract(s) via UC REST API", len(contracts))

    client = _RestClient(base_url=uc_uri, timeout=timeout)
    try:
        n_ok, n_fail = _register_contracts(
            client=client,
            contracts=contracts,
            catalog_name=catalog_name,
            warehouse_root=warehouse_root,
            env=args.env.lower(),
        )
    finally:
        client.close()

    logger.info("bootstrap-uc done: ok=%d fail=%d", n_ok, n_fail)
    if n_fail:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
