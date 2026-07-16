"""Unit tests for utils/scd2.py — generic SCD Type 2 merge (STORY-01-003).

Exercises the three change-detection paths against a real NAMED Delta table
(LLD §13 Decision 12 — the target is a pre-created named table resolved via
DeltaTable.forName, never a filesystem path):

* new record (no match) -> insert as open version
* changed record (match + hash differs) -> close old + insert new
* unchanged record (match + hash equal) -> no-op

The helper NEVER creates the table; the test pre-creates an empty named Delta
table (mirroring the Liquibase deploy-time pre-create) before each merge.

Also asserts the DQ contract (LLD §5.4): apply_scd2 NEVER calls run_dq — it
trusts every row it receives.
"""

from __future__ import annotations

import datetime as dt

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.utils import scd2  # noqa: E402

NATURAL_KEYS = ["patient_id"]
HASH_COLUMNS = ["first_name", "city"]


@pytest.fixture(scope="module")
def spark(tmp_path_factory):
    from pyspark.sql import SparkSession

    # configure_spark_with_delta_pip resolves the delta-spark Maven jar that
    # matches the installed pip package onto the JVM classpath — required for
    # DeltaTable.forName / MERGE to work in a bare local session.
    delta = pytest.importorskip("delta", reason="delta-spark not installed")

    warehouse = tmp_path_factory.mktemp("scd2-warehouse")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("test_scd2")
        .config("spark.sql.warehouse.dir", str(warehouse))
        .config("spark.sql.shuffle.partitions", "4")
        .config(
            "spark.sql.extensions",
            "io.delta.sql.DeltaSparkSessionExtension",
        )
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    try:
        s = delta.configure_spark_with_delta_pip(builder).getOrCreate()
    except Exception as exc:  # pragma: no cover - offline / no-jar env
        pytest.skip(f"could not provision Delta JVM jars: {exc}")
    yield s
    s.stop()


def _df(spark, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("patient_id", T.StringType(), False),
            T.StructField("first_name", T.StringType(), True),
            T.StructField("city", T.StringType(), True),
        ]
    )
    return spark.createDataFrame(rows, schema)


def _precreate(spark, table):
    """Pre-create the empty named SCD2 Delta table (Liquibase deploy-time twin).

    The helper resolves this table via DeltaTable.forName and merges into it;
    it never issues CREATE TABLE itself.
    """
    spark.sql(f"DROP TABLE IF EXISTS {table}")
    spark.sql(
        f"""
        CREATE TABLE {table} (
            patient_id STRING,
            first_name STRING,
            city STRING,
            _record_hash STRING,
            effective_from DATE,
            effective_to DATE,
            is_current BOOLEAN
        ) USING DELTA
        """
    )


def _read(spark, table):
    return spark.read.table(table)


def test_first_run_inserts_open_versions(spark):
    table = "default.scd2_first_run"
    _precreate(spark, table)
    src = _df(spark, [("p1", "John", "Boston"), ("p2", "Jane", "Lynn")])
    metrics = scd2.apply_scd2(
        src,
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date="2026-06-01",
    )
    assert metrics == {"rows_inserted": 2, "rows_closed": 0, "rows_unchanged": 0}
    out = _read(spark, table)
    assert out.count() == 2
    assert out.where("is_current = true").count() == 2
    r = out.where("patient_id = 'p1'").collect()[0]
    assert r["effective_from"] == dt.date(2026, 6, 1)
    assert r["effective_to"] == dt.date(9999, 12, 31)
    assert r["is_current"] is True
    assert r["_record_hash"] is not None
    spark.sql(f"DROP TABLE IF EXISTS {table}")


def test_changed_record_closes_old_and_inserts_new(spark):
    table = "default.scd2_changed"
    _precreate(spark, table)
    scd2.apply_scd2(
        _df(spark, [("p1", "John", "Boston")]),
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date="2026-06-01",
    )
    # p1 moves city -> hash differs.
    metrics = scd2.apply_scd2(
        _df(spark, [("p1", "John", "Cambridge")]),
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date="2026-06-02",
    )
    assert metrics["rows_closed"] == 1
    assert metrics["rows_inserted"] == 1
    assert metrics["rows_unchanged"] == 0

    out = _read(spark, table)
    assert out.count() == 2  # one closed + one open
    closed = out.where("is_current = false").collect()[0]
    assert closed["city"] == "Boston"
    assert closed["effective_to"] == dt.date(2026, 6, 1)  # effective_date - 1
    current = out.where("is_current = true").collect()[0]
    assert current["city"] == "Cambridge"
    assert current["effective_from"] == dt.date(2026, 6, 2)
    spark.sql(f"DROP TABLE IF EXISTS {table}")


def test_unchanged_record_is_noop(spark):
    table = "default.scd2_unchanged"
    _precreate(spark, table)
    scd2.apply_scd2(
        _df(spark, [("p1", "John", "Boston")]),
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date="2026-06-01",
    )
    metrics = scd2.apply_scd2(
        _df(spark, [("p1", "John", "Boston")]),  # identical
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date="2026-06-02",
    )
    assert metrics == {"rows_inserted": 0, "rows_closed": 0, "rows_unchanged": 1}
    out = _read(spark, table)
    assert out.count() == 1
    assert out.where("is_current = true").count() == 1
    spark.sql(f"DROP TABLE IF EXISTS {table}")


def test_hash_is_deterministic_across_runs(spark):
    """Same business values -> identical _record_hash (IL-006: stable keys)."""
    h1 = scd2._compute_record_hash(_df(spark, [("p1", "John", "Boston")]), HASH_COLUMNS).collect()[
        0
    ]["_record_hash"]
    h2 = scd2._compute_record_hash(_df(spark, [("p1", "John", "Boston")]), HASH_COLUMNS).collect()[
        0
    ]["_record_hash"]
    assert h1 == h2


def test_apply_scd2_never_calls_run_dq(spark, monkeypatch):
    """DQ contract (LLD §5.4): the helper trusts its input — caller runs DQ."""
    import sys

    called = {"n": 0}
    # If se_runner is importable in this env, spy on run_dq. The assertion is
    # that apply_scd2's code path never reaches it.
    if "patient_360.utils.se_runner" in sys.modules:
        monkeypatch.setattr(
            sys.modules["patient_360.utils.se_runner"],
            "run_dq",
            lambda *a, **k: called.__setitem__("n", called["n"] + 1),
            raising=False,
        )
    table = "default.scd2_no_dq"
    _precreate(spark, table)
    scd2.apply_scd2(
        _df(spark, [("p1", "John", "Boston")]),
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date="2026-06-01",
    )
    assert called["n"] == 0
    spark.sql(f"DROP TABLE IF EXISTS {table}")
