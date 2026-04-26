#!/usr/bin/env python3
"""Bootstrap a Unity Catalog OSS instance with a catalog and medallion schemas.

This script is project-agnostic. It reads target host / catalog / schemas
from environment variables (or `--` flags), POSTs them to the UC OSS REST
API, and treats "already exists" as success so the script is idempotent.

Defaults match the cookiecutter-template `make dev-up` flow:

    UC_HOST    = http://localhost:8080
    UC_CATALOG = unity
    UC_SCHEMAS = bronze,silver,gold

Usage:
    python scripts/uc_init.py
    python scripts/uc_init.py --host http://localhost:8080 \\
        --catalog unity --schemas bronze,silver,gold

Exit codes:
    0 — catalog + every schema is registered (created or pre-existing).
    1 — UC API unreachable or returned an unexpected error.
    2 — bad arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _post(host: str, path: str, body: dict) -> tuple[int, str]:
    url = host.rstrip("/") + path
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"ERROR: cannot reach {url} ({e.reason})", file=sys.stderr)
        sys.exit(1)


def _is_already_exists(status: int, body: str) -> bool:
    if status == 409:
        return True
    if status >= 400 and "already exists" in body.lower():
        return True
    return False


def create_catalog(host: str, catalog: str) -> bool:
    status, body = _post(host, "/api/2.1/unity-catalog/catalogs", {"name": catalog})
    if 200 <= status < 300:
        print(f"  created catalog: {catalog}")
        return True
    if _is_already_exists(status, body):
        print(f"  catalog exists: {catalog}")
        return True
    print(f"  FAILED to create catalog {catalog!r}: {status} {body}", file=sys.stderr)
    return False


def create_schema(host: str, catalog: str, schema: str) -> bool:
    status, body = _post(
        host,
        "/api/2.1/unity-catalog/schemas",
        {"name": schema, "catalog_name": catalog},
    )
    if 200 <= status < 300:
        print(f"  created schema: {catalog}.{schema}")
        return True
    if _is_already_exists(status, body):
        print(f"  schema exists: {catalog}.{schema}")
        return True
    print(
        f"  FAILED to create schema {catalog}.{schema}: {status} {body}",
        file=sys.stderr,
    )
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--host",
        default=os.environ.get("UC_HOST", "http://localhost:8080"),
        help="UC OSS REST API base URL (default: http://localhost:8080)",
    )
    ap.add_argument(
        "--catalog",
        default=os.environ.get("UC_CATALOG", "unity"),
        help="Catalog name (default: unity)",
    )
    ap.add_argument(
        "--schemas",
        default=os.environ.get("UC_SCHEMAS", "bronze,silver,gold"),
        help="Comma-separated schema names (default: bronze,silver,gold)",
    )
    args = ap.parse_args()

    schema_list = [s.strip() for s in args.schemas.split(",") if s.strip()]
    if not schema_list:
        print("ERROR: no schemas provided", file=sys.stderr)
        return 2

    print(f"Initializing UC OSS at {args.host}")
    print(f"  catalog: {args.catalog}")
    print(f"  schemas: {', '.join(schema_list)}")

    ok = create_catalog(args.host, args.catalog)
    for schema in schema_list:
        ok = create_schema(args.host, args.catalog, schema) and ok

    if ok:
        print("UC bootstrap complete.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
