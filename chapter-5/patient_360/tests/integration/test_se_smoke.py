"""Spark-Expectations smoke test (LLD §8.6.1).

Marked ``integration`` — requires the local docker stack (UC OSS,
Spark 4.0.0 in airflow) to be up. Skipped automatically when the
``RUN_SE_SMOKE`` env var is not set so unit-collection runs stay fast.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def smoke_run_id() -> str:
    return os.environ.get("SE_SMOKE_RUN_ID", "smoke-local")


@pytest.mark.skipif(
    os.environ.get("RUN_SE_SMOKE") != "1",
    reason="SE smoke requires local docker stack; set RUN_SE_SMOKE=1 to enable",
)
def test_se_stats_populated(smoke_run_id: str) -> None:
    """``bronze_se_stats`` has ≥1 row whose ``meta_dq_run_id`` matches the smoke run.

    Driven by ``make smoke-se`` which:
        1. Stands up Spark 4.0.0 inside the airflow container.
        2. Calls ``with_expectations(...)`` against a tiny sample DataFrame.
        3. Writes stats to the Unity Catalog ``unity.bronze.bronze_se_stats`` table.
    """
    pyspark = pytest.importorskip("pyspark")
    se = pytest.importorskip("spark_expectations.core.expectations")
    from pyspark.sql import SparkSession  # type: ignore[import-not-found]

    spark = SparkSession.builder.master("local[2]").appName("se-smoke").getOrCreate()
    try:
        rows = spark.sql(
            "SELECT meta_dq_run_id FROM unity.bronze.bronze_se_stats "
            f"WHERE meta_dq_run_id = '{smoke_run_id}'"
        ).collect()
        assert rows, f"no SE stats rows for run_id={smoke_run_id}"
    finally:
        spark.stop()
    # Reference the imported names so static analyzers don't flag unused imports
    assert pyspark is not None and se is not None
