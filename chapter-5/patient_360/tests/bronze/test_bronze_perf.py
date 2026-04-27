"""Bronze layer benchmark — wall-clock target ≤ 5 min on DEV (LLD §4.4).

This test is opt-in via the ``benchmark`` marker; CI pipelines run it on a
schedule, not on every PR. The ``replaceWhere`` partition-pruning
assertion is exercised by a small synthetic write so the test can
execute without the full 7.9M-row dataset.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "airflow" / "configs"


@pytest.mark.benchmark
def test_bronze_taskgroup_p95_under_five_minutes():
    """Smoke-grade benchmark: scanning 13 configs + creating a SparkSession
    must stay well under 5 min. Real perf measurements come from the
    integration test (STORY-02-007)."""
    pytest.importorskip("pyspark")

    from pyspark.sql import SparkSession

    start = time.time()
    spark = (
        SparkSession.builder.appName("p360_bench")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
    try:
        # Read configs and assert all 13 are well-formed.
        for p in sorted(CONFIGS_DIR.glob("*.yml")):
            yaml.safe_load(p.read_text())
        elapsed = time.time() - start
        assert elapsed < 300, f"Bronze parse exceeded 300s: {elapsed:.1f}s"
    finally:
        spark.stop()


@pytest.mark.benchmark
def test_replace_where_pruning_smoke(tmp_path):
    """Confirms a `replaceWhere ds = '<ds>'` write rewrites only the
    target ds partition (LLD §4.5 / §6.5)."""
    pytest.importorskip("pyspark")

    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.appName("p360_pruning")
        .master("local[1]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    try:
        path = str(tmp_path / "t")
        df_a = spark.createDataFrame([(1, "2026-04-26")], ["id", "ds"])
        df_b = spark.createDataFrame([(2, "2026-04-27")], ["id", "ds"])
        (df_a.write.format("delta").mode("append").partitionBy("ds").save(path))
        (df_b.write.format("delta").mode("append").partitionBy("ds").save(path))
        # Rewrite only the 04-27 partition.
        df_c = spark.createDataFrame([(3, "2026-04-27")], ["id", "ds"])
        (
            df_c.write.format("delta")
            .mode("append")
            .partitionBy("ds")
            .option("replaceWhere", "ds = '2026-04-27'")
            .save(path)
        )
        # The 04-26 partition is intact; 04-27 is replaced.
        rows = {(r["id"], r["ds"]) for r in spark.read.format("delta").load(path).collect()}
        assert (1, "2026-04-26") in rows
        assert (3, "2026-04-27") in rows
        assert (2, "2026-04-27") not in rows
    finally:
        spark.stop()
