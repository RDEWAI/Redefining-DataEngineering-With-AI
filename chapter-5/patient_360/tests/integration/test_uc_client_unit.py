"""Unit tests for the Unity Catalog REST client used by the integration test."""

from __future__ import annotations

import pytest


def test_uc_get_url_construction(monkeypatch):
    """The integration helper builds /api/2.1/unity-catalog/<path> URLs."""
    monkeypatch.setenv("UC_URI", "http://localhost:8080")
    pytest.importorskip("requests")

    from patient_360.tests_integration_helpers import (  # type: ignore[attr-defined]
        build_tables_url,
    )

    assert (
        build_tables_url("unity", "bronze")
        == "http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze"
    )


def test_assert_tables_present():
    from patient_360.tests_integration_helpers import (  # type: ignore[attr-defined]
        assert_tables_present,
    )

    payload = {"tables": [{"name": "synthea_patients"}, {"name": "synthea_encounters"}]}
    assert_tables_present(payload, ["synthea_patients"])
    with pytest.raises(AssertionError, match="missing"):
        assert_tables_present(payload, ["synthea_zzz"])
