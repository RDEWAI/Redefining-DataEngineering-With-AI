"""Unit tests for patient_360.utils.delta_helpers.

These tests assert module-level invariants without booting Spark — booting
a SparkSession lives under tests/integration/ per learnings L-001.
"""

from __future__ import annotations

from patient_360.utils import delta_helpers


def test_uc_catalog_class_is_pinned() -> None:
    # LLD §13 Decision 12 — UCSingleCatalog is the only acceptable catalog
    # implementation for Bronze writes against UC OSS.
    assert delta_helpers.UC_CATALOG_CLASS == "io.unitycatalog.spark.UCSingleCatalog"


def test_default_uc_uri_is_local() -> None:
    assert delta_helpers.DEFAULT_UC_URI == "http://localhost:8080"


def test_build_spark_session_function_is_exported() -> None:
    assert callable(delta_helpers.build_spark_session)


def test_replace_where_write_function_is_exported() -> None:
    assert callable(delta_helpers.replace_where_write)
