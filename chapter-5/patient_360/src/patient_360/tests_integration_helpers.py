"""Helpers shared by the Bronze integration test and its unit-level checks.

Lives under the importable package so tests can do
``from patient_360.tests_integration_helpers import ...``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable


def build_tables_url(catalog: str, schema: str, base: str | None = None) -> str:
    base = base or os.environ.get("UC_URI", "http://localhost:8080")
    return f"{base}/api/2.1/unity-catalog/tables" f"?catalog_name={catalog}&schema_name={schema}"


def assert_tables_present(payload: dict, expected: Iterable[str]) -> None:
    names = {t["name"] for t in payload.get("tables", [])}
    missing = set(expected) - names
    assert not missing, f"missing UC tables: {sorted(missing)}"
