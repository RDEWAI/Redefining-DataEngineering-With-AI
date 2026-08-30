"""Unit tests for patient_360.utils.delta_helpers.

These tests assert module-level invariants without booting Spark — booting
a SparkSession lives under tests/integration/ per learnings L-001.
"""

from __future__ import annotations

from patient_360.utils import delta_helpers


def test_uc_catalog_class_is_pinned() -> None:
    # LLD §13 Decision 12 (re-adopted 2026-06-18) — UCSingleCatalog backs the
    # NAMED side catalog `unity`, never spark_catalog.
    assert delta_helpers.UC_CATALOG_CLASS == "io.unitycatalog.spark.UCSingleCatalog"


def test_spark_catalog_is_delta_not_uc() -> None:
    # spark_catalog must stay bound to DeltaCatalog; UC is the side catalog.
    assert delta_helpers.DELTA_CATALOG_CLASS == "org.apache.spark.sql.delta.catalog.DeltaCatalog"


def test_uc_side_catalog_name_is_unity() -> None:
    # spark.sql.defaultCatalog=unity per LLD §13 Decision 12.
    assert delta_helpers.UC_CATALOG_NAME == "unity"


def test_default_uc_uri_is_local() -> None:
    assert delta_helpers.DEFAULT_UC_URI == "http://localhost:8080"


def test_warehouse_resolves_under_project_root(monkeypatch) -> None:
    # All path resolution anchors to ${PATIENT360_PROJECT_ROOT} per LLD §9.1.
    monkeypatch.delenv(delta_helpers.UC_WAREHOUSE_ENV, raising=False)
    monkeypatch.setenv(delta_helpers.PROJECT_ROOT_ENV, "/opt/p360")
    assert delta_helpers._resolve_uc_warehouse() == "/opt/p360/warehouse/dev"


def test_warehouse_env_override_wins(monkeypatch) -> None:
    monkeypatch.setenv(delta_helpers.UC_WAREHOUSE_ENV, "/data/wh")
    monkeypatch.setenv(delta_helpers.PROJECT_ROOT_ENV, "/opt/p360")
    assert delta_helpers._resolve_uc_warehouse() == "/data/wh"


def test_build_spark_session_function_is_exported() -> None:
    assert callable(delta_helpers.build_spark_session)
