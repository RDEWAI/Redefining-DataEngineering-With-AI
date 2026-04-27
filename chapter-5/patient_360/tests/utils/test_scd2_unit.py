"""Unit tests for :mod:`patient_360.utils.scd2`.

These tests exercise hash construction and merge-statement assembly
without requiring a live SparkSession. Live MERGE execution is covered
by integration tests under ``tests/silver/`` once the Silver layer ships.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from patient_360.utils import scd2


def test_build_hash_expr_uses_sha2_256():
    expr = scd2._build_hash_expr(["FIRST", "LAST"])
    assert "sha2(" in expr
    assert ", 256)" in expr
    assert "`FIRST`" in expr
    assert "`LAST`" in expr


def test_build_hash_expr_rejects_empty():
    with pytest.raises(ValueError):
        scd2._build_hash_expr([])


def test_apply_scd2_issues_merge_with_keys_and_hash():
    spark = MagicMock()
    source = MagicMock()
    staged = MagicMock()
    source.selectExpr.return_value = staged

    result = scd2.apply_scd2(
        spark=spark,
        target="unity.silver.dim_patient",
        source=source,
        key_cols=["patient_id"],
        hash_cols=["first_name", "last_name"],
    )

    # Source is staged via selectExpr and registered as a temp view
    source.selectExpr.assert_called_once()
    staged.createOrReplaceTempView.assert_called_once_with("_scd2_staging")

    # MERGE issued
    spark.sql.assert_called_once()
    merge_sql = spark.sql.call_args[0][0]
    assert "MERGE INTO unity.silver.dim_patient" in merge_sql
    assert "t.`patient_id` = s.`patient_id`" in merge_sql
    assert "WHEN MATCHED" in merge_sql
    assert "WHEN NOT MATCHED" in merge_sql
    assert result["target"] == "unity.silver.dim_patient"
    assert result["merge_sql"] == merge_sql


def test_apply_scd2_validates_inputs():
    with pytest.raises(ValueError):
        scd2.apply_scd2(
            spark=MagicMock(),
            target="t",
            source=MagicMock(),
            key_cols=[],
            hash_cols=["x"],
        )
    with pytest.raises(ValueError):
        scd2.apply_scd2(
            spark=MagicMock(),
            target="",
            source=MagicMock(),
            key_cols=["k"],
            hash_cols=["x"],
        )
