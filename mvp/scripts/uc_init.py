"""
Bootstrap Unity Catalog OSS with the schemas needed by the pipeline.

Run once after `make uc-start` (called automatically by the Makefile target):
    uv run python scripts/uc_init.py

The UC server creates a default `unity` catalog on first start.
This script creates the bronze, silver, gold schemas under that catalog.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

UC_BASE = "http://localhost:8080/api/2.1/unity-catalog"
# UCSingleCatalog maps the Spark catalog name directly to a UC catalog with the same name.
# We use "spark_catalog" so all existing 2-part table names (bronze.patients) work unchanged.
CATALOG_NAME = "spark_catalog"
SCHEMAS = ["bronze", "silver", "gold"]


def _post(path: str, body: dict) -> dict | None:
    """POST to UC REST API. Returns None if resource already exists (409)."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{UC_BASE}/{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 409:  # already exists — idempotent
            return None
        raise


def _verify_reachable(retries: int = 18, delay: float = 5.0) -> None:
    """
    Wait until the UC server responds to the catalogs list endpoint.

    Retries up to `retries` times with `delay` seconds between attempts
    (default: 18 × 5 s = 90 s max wait). Raises RuntimeError if the server
    never becomes ready.
    """
    url = f"{UC_BASE}/catalogs"
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="GET")):
                return  # server ready
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            reason = exc.code if isinstance(exc, urllib.error.HTTPError) else exc.reason
            print(f"  waiting for UC server (attempt {attempt}/{retries}): {reason}")
            if attempt < retries:
                time.sleep(delay)
    raise RuntimeError(f"UC server at {UC_BASE} did not become ready after {retries} attempts")


def main() -> None:
    print(f"Connecting to Unity Catalog at {UC_BASE} ...")
    _verify_reachable()
    print(f"  server reachable — using default catalog '{CATALOG_NAME}'")

    # Create the spark_catalog catalog in UC.
    # (The UC server auto-creates "unity" on first start, but not "spark_catalog".)
    result = _post("catalogs", {"name": CATALOG_NAME})
    if result is None:
        print(f"  catalog '{CATALOG_NAME}' already exists")
    else:
        print(f"  created catalog '{CATALOG_NAME}'")

    for schema in SCHEMAS:
        result = _post("schemas", {"name": schema, "catalog_name": CATALOG_NAME})
        if result is None:
            print(f"  schema '{CATALOG_NAME}.{schema}' already exists")
        else:
            print(f"  created schema '{CATALOG_NAME}.{schema}'")

    print("Unity Catalog bootstrap complete.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        print("  Is the server running? Try: make uc-start")
        sys.exit(1)
