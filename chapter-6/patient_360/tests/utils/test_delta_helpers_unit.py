"""Unit tests for patient_360.utils.delta_helpers.

These tests assert module-level invariants without booting Spark — booting
a SparkSession lives under tests/integration/ per learnings L-001.

# updated: 2026-05-20 — UCSingleCatalog removed from the runtime path
# per LLD §13 Decision 12 (revoked & replaced 2026-05-12). Catalog
# wiring is now DeltaCatalog + Derby Hive metastore.
"""

from __future__ import annotations

from patient_360.utils import delta_helpers


def test_delta_catalog_class_is_pinned() -> None:
    # LLD §13 Decision 12 (2026-05-12 pivot) — the Spark catalog is
    # DeltaCatalog backed by a Derby Hive metastore. UCSingleCatalog is
    # intentionally absent from the runtime path.
    assert (
        delta_helpers.DELTA_CATALOG_CLASS
        == "org.apache.spark.sql.delta.catalog.DeltaCatalog"
    )


def test_delta_sql_extensions_is_pinned() -> None:
    assert (
        delta_helpers.DELTA_SQL_EXTENSIONS
        == "io.delta.sql.DeltaSparkSessionExtension"
    )


def test_ucsinglecatalog_is_not_re_exported() -> None:
    """UCSingleCatalog wiring is forbidden in the runtime helpers."""
    assert not hasattr(delta_helpers, "UC_CATALOG_CLASS")


def test_build_spark_session_function_is_exported() -> None:
    assert callable(delta_helpers.build_spark_session)


def test_replace_where_write_function_is_exported() -> None:
    assert callable(delta_helpers.replace_where_write)
