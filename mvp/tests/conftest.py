"""Shared pytest fixtures for mvp Spark pipeline tests."""

from __future__ import annotations

import pytest
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark(tmp_path_factory) -> SparkSession:
    """
    Session-scoped SparkSession for tests.

    Uses a temp directory as the Delta warehouse so tests are isolated
    and never touch the real warehouse/ directory.
    """
    warehouse = str(tmp_path_factory.mktemp("warehouse"))

    builder = (
        SparkSession.builder.appName("patient_360_tests")
        .master("local[2]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.warehouse.dir", warehouse)
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
    )

    session = configure_spark_with_delta_pip(builder).getOrCreate()
    session.sparkContext.setLogLevel("ERROR")

    # Create databases used across all tests
    session.sql("CREATE DATABASE IF NOT EXISTS bronze")
    session.sql("CREATE DATABASE IF NOT EXISTS silver")
    session.sql("CREATE DATABASE IF NOT EXISTS gold")

    yield session

    session.stop()


@pytest.fixture
def ds() -> str:
    """Default load date string for tests."""
    return "2026-03-06"
