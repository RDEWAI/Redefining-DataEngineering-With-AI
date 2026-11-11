"""Unit tests for utils/scd2.py — generic SCD Type 2 merge (STORY-01-003).

Exercises the three change-detection paths against a real NAMED Delta table
(LLD §13 Decision 12 — the target is a pre-created named table resolved via
DeltaTable.forName, never a filesystem path):

* new record (no match) -> insert as open version
* changed record (match + hash differs), current version started earlier
  -> close old + insert new
* changed record, current version started on effective_date -> overwrite in
  place (LLD v1.27 §2.3 same-day overwrite contract, §13 Decision 18)
* unchanged record (match + hash equal) -> no-op

The helper NEVER creates the table; the test pre-creates an empty named Delta
table (mirroring the Liquibase deploy-time pre-create) before each merge.

Also asserts the DQ contract (LLD §5.4): apply_scd2 NEVER calls run_dq — it
trusts every row it receives.

The refresh tests implement the required list in the LLD v1.26 §2.3 in-place
refresh contract (§13 Decision 17). The same-day tests implement the required
list in the LLD v1.27 §2.3 same-day overwrite contract (§13 Decision 18). The
backfill and hash-list tests implement the required lists in the LLD v1.28
§2.3 backfill skip contract (§13 Decision 19) and hash-list change contract
(§13 Decision 20).
"""

from __future__ import annotations

import datetime as dt
import uuid

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
    assert metrics == {
        "rows_inserted": 2,
        "rows_closed": 0,
        "rows_unchanged": 0,
        "rows_overwritten": 0,
        "rows_skipped_backfill": 0,
        "rows_rehashed": 0,
    }
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
    assert metrics == {
        "rows_inserted": 0,
        "rows_closed": 0,
        "rows_unchanged": 1,
        "rows_overwritten": 0,
        "rows_skipped_backfill": 0,
        "rows_rehashed": 0,
    }
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


# --------------------------------------------------------------------------
# LLD §2.3 in-place refresh contract (Decision 17)
# --------------------------------------------------------------------------
REFRESH_COLUMNS = ["calculated_age"]
PROTECTED_COLUMNS = ["effective_from", "effective_to", "is_current", "_record_hash"]
T1 = dt.datetime(2026, 6, 1, 1, 0, 0)
T2 = dt.datetime(2026, 6, 2, 1, 0, 0)


def _refresh_df(spark, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("patient_id", T.StringType(), False),
            T.StructField("first_name", T.StringType(), True),
            T.StructField("city", T.StringType(), True),
            T.StructField("calculated_age", T.IntegerType(), True),
            T.StructField("_ingested_at", T.TimestampType(), True),
        ]
    )
    return spark.createDataFrame(rows, schema)


def _merge(spark, table, rows, effective_date="2026-06-02", refresh_columns=None):
    return scd2.apply_scd2(
        _refresh_df(spark, rows),
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date=effective_date,
        refresh_columns=REFRESH_COLUMNS if refresh_columns is None else refresh_columns,
    )


def _seeded_table(spark, age=30):
    """Create a uniquely named table in the temp warehouse with one open p1 row."""
    table = f"default.scd2_refresh_{uuid.uuid4().hex}"
    spark.sql(
        f"""
        CREATE TABLE {table} (
            patient_id STRING,
            first_name STRING,
            city STRING,
            calculated_age INT,
            _ingested_at TIMESTAMP,
            _record_hash STRING,
            effective_from DATE,
            effective_to DATE,
            is_current BOOLEAN
        ) USING DELTA
        """
    )
    _merge(spark, table, [("p1", "John", "Boston", age, T1)], effective_date="2026-06-01")
    return table


def _version_count(spark, table):
    return spark.sql(f"DESCRIBE HISTORY {table}").count()


def _current_age(spark, table):
    rows = _read(spark, table).where("is_current = true").collect()
    assert len(rows) == 1
    return rows[0]["calculated_age"]


def test_refresh_updates_value_in_place(spark):
    table = _seeded_table(spark, age=30)
    before = _read(spark, table).collect()[0]

    metrics = _merge(spark, table, [("p1", "John", "Boston", 31, T2)])

    # A refreshed row also counts in rows_unchanged (LLD §2.3 step 7).
    assert metrics == {
        "rows_inserted": 0,
        "rows_closed": 0,
        "rows_unchanged": 1,
        "rows_overwritten": 0,
        "rows_skipped_backfill": 0,
        "rows_rehashed": 0,
        "rows_refreshed": 1,
    }
    rows = _read(spark, table).collect()
    assert len(rows) == 1
    after = rows[0]
    assert after["calculated_age"] == 31
    for column in PROTECTED_COLUMNS:
        assert after[column] == before[column]
    # Decision 17: a refresh does not update provenance columns.
    assert after["_ingested_at"] == T1


def test_refresh_duplicate_keys_latest_ingested_at_wins(spark):
    table = _seeded_table(spark, age=30)
    # The older row holds the larger value, so a sort on value alone would fail.
    metrics = _merge(
        spark,
        table,
        [("p1", "John", "Boston", 99, T1), ("p1", "John", "Boston", 31, T2)],
    )
    assert metrics["rows_refreshed"] == 1
    assert _read(spark, table).count() == 1
    assert _current_age(spark, table) == 31


def test_refresh_duplicate_tie_uses_refresh_column_descending_nulls_last(spark):
    table = _seeded_table(spark, age=30)
    metrics = _merge(
        spark,
        table,
        [
            ("p1", "John", "Boston", None, T2),
            ("p1", "John", "Boston", 31, T2),
            ("p1", "John", "Boston", 32, T2),
        ],
    )
    assert metrics["rows_refreshed"] == 1
    assert _current_age(spark, table) == 32


def test_refresh_repeat_run_adds_no_delta_version(spark):
    table = _seeded_table(spark, age=30)
    _merge(spark, table, [("p1", "John", "Boston", 31, T2)])
    versions = _version_count(spark, table)

    metrics = _merge(spark, table, [("p1", "John", "Boston", 31, T2)])

    assert metrics["rows_refreshed"] == 0
    assert metrics["rows_unchanged"] == 1
    assert _version_count(spark, table) == versions


@pytest.mark.parametrize(
    ("stored", "incoming", "refreshed"),
    [
        (None, 31, 1),  # NULL to value
        (30, None, 1),  # value to NULL
        (None, None, 0),  # NULL to NULL
    ],
)
def test_refresh_null_transitions(spark, stored, incoming, refreshed):
    table = _seeded_table(spark, age=stored)
    versions = _version_count(spark, table)

    metrics = _merge(spark, table, [("p1", "John", "Boston", incoming, T2)])

    assert metrics["rows_refreshed"] == refreshed
    assert _current_age(spark, table) == incoming
    if not refreshed:
        assert _version_count(spark, table) == versions


def test_refresh_version_closed_in_same_run_keeps_value(spark):
    table = _seeded_table(spark, age=30)

    # p1 moves city (hash changes) and the age also differs.
    metrics = _merge(spark, table, [("p1", "John", "Cambridge", 31, T2)])

    assert metrics["rows_closed"] == 1
    assert metrics["rows_inserted"] == 1
    assert metrics["rows_refreshed"] == 0
    closed = _read(spark, table).where("is_current = false").collect()
    assert len(closed) == 1
    assert closed[0]["city"] == "Boston"
    assert closed[0]["calculated_age"] == 30
    assert _current_age(spark, table) == 31


def test_refresh_does_not_match_closed_version_with_same_hash(spark):
    """Boston -> Cambridge -> Boston leaves a closed and a current row with one hash."""
    table = _seeded_table(spark, age=30)
    _merge(spark, table, [("p1", "John", "Cambridge", 31, T2)], effective_date="2026-06-02")
    _merge(spark, table, [("p1", "John", "Boston", 32, T2)], effective_date="2026-06-03")

    metrics = _merge(spark, table, [("p1", "John", "Boston", 33, T2)], effective_date="2026-06-04")

    assert metrics["rows_refreshed"] == 1
    assert _current_age(spark, table) == 33
    closed = _read(spark, table).where("is_current = false").collect()
    assert {(r["city"], r["calculated_age"]) for r in closed} == {("Boston", 30), ("Cambridge", 31)}


@pytest.mark.parametrize("refresh_columns", ["omit", None, []])
def test_no_refresh_columns_returns_six_keys_and_no_refresh(spark, refresh_columns):
    table = _seeded_table(spark, age=30)
    versions = _version_count(spark, table)
    kwargs = {} if refresh_columns == "omit" else {"refresh_columns": refresh_columns}

    metrics = scd2.apply_scd2(
        _refresh_df(spark, [("p1", "John", "Boston", 31, T2)]),
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date="2026-06-02",
        **kwargs,
    )

    assert metrics == {
        "rows_inserted": 0,
        "rows_closed": 0,
        "rows_unchanged": 1,
        "rows_overwritten": 0,
        "rows_skipped_backfill": 0,
        "rows_rehashed": 0,
    }
    assert _current_age(spark, table) == 30
    assert _version_count(spark, table) == versions


@pytest.mark.parametrize(
    ("bad_column", "message"),
    [
        ("patient_id", "natural key"),
        ("first_name", "hash column"),
        ("effective_from", "metadata"),
        ("effective_to", "metadata"),
        ("is_current", "metadata"),
        ("_record_hash", "metadata"),
        ("in_neither", "not in the source"),
    ],
)
def test_invalid_refresh_column_raises_before_any_write(spark, bad_column, message):
    table = _seeded_table(spark, age=30)
    versions = _version_count(spark, table)

    # The city change would close and insert if validation did not run first.
    with pytest.raises(ValueError, match=message):
        _merge(spark, table, [("p1", "John", "Cambridge", 31, T2)], refresh_columns=[bad_column])

    assert _version_count(spark, table) == versions
    assert _read(spark, table).count() == 1


@pytest.mark.parametrize(
    ("change", "refresh_columns", "message"),
    [
        ("add_extra", ["extra"], "not in the target"),
        ("drop_age", ["calculated_age"], "not in the source"),
        ("drop_ingested_at", ["calculated_age"], "_ingested_at"),
    ],
)
def test_invalid_source_shape_raises_before_any_write(spark, change, refresh_columns, message):
    from pyspark.sql import functions as F

    table = _seeded_table(spark, age=30)
    versions = _version_count(spark, table)
    src = _refresh_df(spark, [("p1", "John", "Cambridge", 31, T2)])
    src = {
        "add_extra": src.withColumn("extra", F.lit(1)),
        "drop_age": src.drop("calculated_age"),
        "drop_ingested_at": src.drop("_ingested_at"),
    }[change]

    with pytest.raises(ValueError, match=message):
        scd2.apply_scd2(
            src,
            target_table=table,
            natural_keys=NATURAL_KEYS,
            hash_columns=HASH_COLUMNS,
            effective_date="2026-06-02",
            refresh_columns=refresh_columns,
        )

    assert _version_count(spark, table) == versions
    assert _read(spark, table).count() == 1


# --------------------------------------------------------------------------
# LLD §2.3 same-day overwrite contract (Decision 18)
# --------------------------------------------------------------------------
def _assert_invariants(spark, table):
    """LLD §2.3 same-day rule 5: the three SCD2 invariants hold after a call."""
    out = _read(spark, table)
    assert out.groupBy("patient_id", "effective_from").count().where("count > 1").count() == 0
    assert out.where("effective_to < effective_from").count() == 0
    current_per_key = out.where("is_current = true").groupBy("patient_id").count()
    assert current_per_key.where("count <> 1").count() == 0
    assert current_per_key.count() == out.select("patient_id").distinct().count()


def test_same_day_changes_overwrite_current_version(spark):
    table = _seeded_table(spark, age=30)  # p1 Boston opened on 2026-06-01
    _assert_invariants(spark, table)

    first = _merge(spark, table, [("p1", "John", "Cambridge", 30, T1)], effective_date="2026-06-02")
    assert first["rows_closed"] == 1
    assert first["rows_inserted"] == 1
    assert first["rows_overwritten"] == 0
    _assert_invariants(spark, table)

    # Second hash change on the same effective_date: overwrite, no new version.
    second = _merge(spark, table, [("p1", "Johnny", "Salem", 31, T2)], effective_date="2026-06-02")
    assert second["rows_overwritten"] == 1
    assert second["rows_closed"] == 0
    assert second["rows_inserted"] == 0
    assert second["rows_unchanged"] == 0
    _assert_invariants(spark, table)

    versions = _read(spark, table).where("effective_from = DATE '2026-06-02'").collect()
    assert len(versions) == 1
    row = versions[0]
    assert row["effective_to"] == dt.date(9999, 12, 31)
    assert row["is_current"] is True
    assert (row["first_name"], row["city"], row["calculated_age"]) == ("Johnny", "Salem", 31)
    assert row["_ingested_at"] == T2
    expected_hash = scd2.compute_record_hash_python(
        {"first_name": "Johnny", "city": "Salem"}, HASH_COLUMNS
    )
    assert row["_record_hash"] == expected_hash
    # The version closed by the first call is untouched.
    closed = _read(spark, table).where("is_current = false").collect()
    assert [(r["city"], r["effective_to"]) for r in closed] == [("Boston", dt.date(2026, 6, 1))]


def test_same_day_overwrite_without_refresh_columns(spark):
    """rows_overwritten is returned also when refresh_columns is omitted."""
    table = "default.scd2_same_day_plain"
    _precreate(spark, table)
    kwargs = dict(
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date="2026-06-01",
    )
    scd2.apply_scd2(_df(spark, [("p1", "John", "Boston")]), **kwargs)

    metrics = scd2.apply_scd2(_df(spark, [("p1", "John", "Cambridge")]), **kwargs)

    assert metrics == {
        "rows_inserted": 0,
        "rows_closed": 0,
        "rows_unchanged": 0,
        "rows_overwritten": 1,
        "rows_skipped_backfill": 0,
        "rows_rehashed": 0,
    }
    rows = _read(spark, table).collect()
    assert len(rows) == 1
    assert rows[0]["city"] == "Cambridge"
    assert rows[0]["effective_from"] == dt.date(2026, 6, 1)
    _assert_invariants(spark, table)
    spark.sql(f"DROP TABLE IF EXISTS {table}")


def test_later_day_change_after_same_day_overwrite_closes_and_inserts(spark):
    table = _seeded_table(spark, age=30)
    # Same-day change on 2026-06-01 overwrites the version opened that day.
    overwrite = _merge(
        spark, table, [("p1", "John", "Cambridge", 30, T1)], effective_date="2026-06-01"
    )
    assert overwrite["rows_overwritten"] == 1
    _assert_invariants(spark, table)

    metrics = _merge(spark, table, [("p1", "John", "Salem", 30, T2)], effective_date="2026-06-02")

    assert metrics["rows_closed"] == 1
    assert metrics["rows_inserted"] == 1
    assert metrics["rows_overwritten"] == 0
    _assert_invariants(spark, table)
    closed = _read(spark, table).where("is_current = false").collect()
    assert len(closed) == 1
    assert closed[0]["city"] == "Cambridge"
    assert closed[0]["effective_from"] == dt.date(2026, 6, 1)
    assert closed[0]["effective_to"] == dt.date(2026, 6, 1)  # effective_date - 1 day
    current = _read(spark, table).where("is_current = true").collect()
    assert [(r["city"], r["effective_from"]) for r in current] == [("Salem", dt.date(2026, 6, 2))]


def test_earlier_day_change_still_closes_and_inserts(spark):
    table = _seeded_table(spark, age=30)  # p1 opened on 2026-06-01

    metrics = _merge(
        spark, table, [("p1", "John", "Cambridge", 30, T2)], effective_date="2026-06-05"
    )

    assert metrics["rows_closed"] == 1
    assert metrics["rows_inserted"] == 1
    assert metrics["rows_overwritten"] == 0
    _assert_invariants(spark, table)
    closed = _read(spark, table).where("is_current = false").collect()
    assert [(r["city"], r["effective_to"]) for r in closed] == [("Boston", dt.date(2026, 6, 4))]


def test_same_day_overwrite_not_counted_as_refresh(spark):
    table = _seeded_table(spark, age=30)  # opened on 2026-06-01

    # Hash and refresh column both change on the same effective_date.
    metrics = _merge(
        spark, table, [("p1", "John", "Cambridge", 31, T2)], effective_date="2026-06-01"
    )

    assert metrics == {
        "rows_inserted": 0,
        "rows_closed": 0,
        "rows_unchanged": 0,
        "rows_overwritten": 1,
        "rows_skipped_backfill": 0,
        "rows_rehashed": 0,
        "rows_refreshed": 0,
    }
    assert _read(spark, table).count() == 1
    assert _current_age(spark, table) == 31
    _assert_invariants(spark, table)


# --------------------------------------------------------------------------
# LLD v1.28 §2.3 backfill skip contract (Decision 19)
# --------------------------------------------------------------------------
_ALL_COLUMNS = [
    "patient_id",
    "first_name",
    "city",
    "calculated_age",
    "_ingested_at",
    *PROTECTED_COLUMNS,
]


def _snapshot(spark, table):
    return sorted(tuple(r[c] for c in _ALL_COLUMNS) for r in _read(spark, table).collect())


def _assert_buckets(metrics, incoming):
    """LLD §2.3 same-day rule 6: every incoming row is in exactly one bucket."""
    assert (
        metrics["rows_skipped_backfill"]
        + metrics["rows_overwritten"]
        + metrics["rows_closed"]
        + metrics["rows_unchanged"]
        + (metrics["rows_inserted"] - metrics["rows_closed"])
    ) == incoming


@pytest.mark.parametrize(
    "incoming",
    [
        ("p1", "John", "Cambridge", 30, T2),  # hash differs
        ("p1", "John", "Boston", 30, T2),  # hash equal
        ("p1", "John", "Boston", 31, T2),  # refresh column would change
    ],
    ids=["hash-differs", "hash-equal", "refresh-differs"],
)
def test_backfill_skip_writes_nothing(spark, incoming):
    table = _seeded_table(spark, age=30)  # p1 Boston opened on 2026-06-01
    before = _snapshot(spark, table)
    versions = _version_count(spark, table)

    metrics = _merge(spark, table, [incoming], effective_date="2026-05-30")

    assert metrics == {
        "rows_inserted": 0,
        "rows_closed": 0,
        "rows_unchanged": 0,
        "rows_overwritten": 0,
        "rows_skipped_backfill": 1,
        "rows_rehashed": 0,
        "rows_refreshed": 0,
    }
    assert _snapshot(spark, table) == before
    assert _version_count(spark, table) == versions
    _assert_invariants(spark, table)


def test_backfill_skip_with_mixed_input(spark):
    table = _seeded_table(spark, age=30)  # p1 opened on 2026-06-01
    _merge(spark, table, [("p3", "Ann", "Salem", 40, T1)], effective_date="2026-05-01")

    incoming = [
        ("p1", "John", "Cambridge", 30, T2),  # skipped: p1 starts after 2026-05-15
        ("p2", "Jane", "Lynn", 20, T2),  # new key
        ("p3", "Ann", "Salem", 40, T2),  # unchanged
    ]
    metrics = _merge(spark, table, incoming, effective_date="2026-05-15")

    assert metrics["rows_skipped_backfill"] == 1
    assert metrics["rows_inserted"] == 1
    assert metrics["rows_unchanged"] == 1
    assert metrics["rows_closed"] == 0
    assert metrics["rows_overwritten"] == 0
    _assert_buckets(metrics, len(incoming))
    _assert_invariants(spark, table)
    p1 = _read(spark, table).where("patient_id = 'p1'").collect()
    assert [(r["city"], r["effective_from"]) for r in p1] == [("Boston", dt.date(2026, 6, 1))]


def test_backfill_warning_logs_count_only_when_skipped(spark, caplog):
    import logging

    table = _seeded_table(spark, age=30)  # p1 opened on 2026-06-01
    caplog.set_level(logging.WARNING, logger=scd2.logger.name)

    no_skip = _merge(spark, table, [("p1", "John", "Boston", 30, T2)])
    assert no_skip["rows_skipped_backfill"] == 0
    assert [r for r in caplog.records if r.name == scd2.logger.name] == []

    skip = _merge(spark, table, [("p1", "John", "Boston", 30, T2)], effective_date="2026-05-30")
    assert skip["rows_skipped_backfill"] == 1
    warnings = [r for r in caplog.records if r.name == scd2.logger.name]
    assert len(warnings) == 1
    assert warnings[0].levelno == logging.WARNING
    message = warnings[0].getMessage()
    assert table in message
    assert "skipped 1 natural keys" in message
    assert "2026-05-30" in message
    assert "p1" not in message  # no natural-key values in the log


# --------------------------------------------------------------------------
# LLD v1.28 §2.3 hash-list change contract (Decision 20)
# --------------------------------------------------------------------------
# The v1.5 clinical_patients hash list. v1.6 adds death_date, patient_status.
V15_PATIENT_HASH = [
    "first_name",
    "last_name",
    "maiden_name",
    "address",
    "city",
    "state",
    "county",
    "zip",
    "marital_status",
    "healthcare_expenses",
    "healthcare_coverage",
    "income",
]


def _v16_patient_hash():
    from patient_360.silver import transform_patients

    hash_columns = transform_patients.HASH_COLUMNS
    assert hash_columns == [*V15_PATIENT_HASH, "death_date", "patient_status"]
    return hash_columns


def _patient_df(spark, rows):
    from decimal import Decimal

    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("patient_id", T.StringType(), False),
            *[T.StructField(c, T.StringType(), True) for c in V15_PATIENT_HASH[:9]],
            T.StructField("healthcare_expenses", T.DecimalType(12, 2), True),
            T.StructField("healthcare_coverage", T.DecimalType(12, 2), True),
            T.StructField("income", T.IntegerType(), True),
            T.StructField("death_date", T.DateType(), True),
            T.StructField("patient_status", T.StringType(), True),
        ]
    )
    full = []
    for patient_id, city, death_date in rows:
        status = "ALIVE" if death_date is None else "DECEASED"
        names = ["John", "Doe", None, "1 Main St", city, "MA", "Suffolk", "02110", "M"]
        full.append(
            (patient_id, *names, Decimal("100.50"), Decimal("50.25"), 40000, death_date, status)
        )
    return spark.createDataFrame(full, schema)


def _patient_table(spark):
    """Seed p1 (one closed + one current version) and p2 with the v1.5 hash list."""
    table = f"default.scd2_hashlist_{uuid.uuid4().hex}"
    spark.sql(
        f"""
        CREATE TABLE {table} (
            patient_id STRING,
            first_name STRING, last_name STRING, maiden_name STRING,
            address STRING, city STRING, state STRING, county STRING, zip STRING,
            marital_status STRING,
            healthcare_expenses DECIMAL(12,2), healthcare_coverage DECIMAL(12,2),
            income INT, death_date DATE, patient_status STRING,
            _record_hash STRING, effective_from DATE, effective_to DATE, is_current BOOLEAN
        ) USING DELTA
        """
    )
    for effective_date, p1_city in [("2026-06-01", "Boston"), ("2026-06-02", "Cambridge")]:
        scd2.apply_scd2(
            _patient_df(spark, [("p1", p1_city, None), ("p2", "Lynn", None)]),
            target_table=table,
            natural_keys=NATURAL_KEYS,
            hash_columns=V15_PATIENT_HASH,
            effective_date=effective_date,
        )
    assert _read(spark, table).count() == 3
    return table


def _merge_v16(spark, table, rows, effective_date="2026-06-03"):
    return scd2.apply_scd2(
        _patient_df(spark, rows),
        target_table=table,
        natural_keys=NATURAL_KEYS,
        hash_columns=_v16_patient_hash(),
        effective_date=effective_date,
    )


def _assert_stored_hash_matches(spark, table, hash_columns):
    for row in _read(spark, table).collect():
        assert row["_record_hash"] == scd2.compute_record_hash_python(row.asDict(), hash_columns)


def test_hash_list_change_unchanged_values_creates_no_version(spark):
    table = _patient_table(spark)

    metrics = _merge_v16(spark, table, [("p1", "Cambridge", None), ("p2", "Lynn", None)])

    assert metrics == {
        "rows_inserted": 0,
        "rows_closed": 0,
        "rows_unchanged": 2,
        "rows_overwritten": 0,
        "rows_skipped_backfill": 0,
        "rows_rehashed": 3,  # both current versions and the closed p1 version
    }
    assert _read(spark, table).count() == 3
    _assert_stored_hash_matches(spark, table, _v16_patient_hash())
    _assert_invariants(spark, table)


def test_hash_list_change_real_death_date_change_creates_one_version(spark):
    table = _patient_table(spark)

    metrics = _merge_v16(
        spark, table, [("p1", "Cambridge", None), ("p2", "Lynn", dt.date(2026, 6, 2))]
    )

    assert metrics["rows_closed"] == 1
    assert metrics["rows_inserted"] == 1
    assert metrics["rows_unchanged"] == 1
    assert metrics["rows_overwritten"] == 0
    assert metrics["rows_rehashed"] == 3
    _assert_buckets(metrics, 2)
    _assert_invariants(spark, table)
    p2 = _read(spark, table).where("patient_id = 'p2'").orderBy("effective_from").collect()
    assert [(r["patient_status"], r["is_current"]) for r in p2] == [
        ("ALIVE", False),
        ("DECEASED", True),
    ]
    assert p2[0]["effective_to"] == dt.date(2026, 6, 2)
    assert p2[1]["effective_from"] == dt.date(2026, 6, 3)
    # p1 keeps its two versions.
    assert _read(spark, table).where("patient_id = 'p1'").count() == 2
    _assert_stored_hash_matches(spark, table, _v16_patient_hash())


def test_hash_list_change_second_run_adds_no_commit(spark):
    table = _patient_table(spark)
    rows = [("p1", "Cambridge", None), ("p2", "Lynn", None)]
    first = _merge_v16(spark, table, rows)
    assert first["rows_rehashed"] == 3
    versions = _version_count(spark, table)

    second = _merge_v16(spark, table, rows, effective_date="2026-06-04")

    assert second["rows_rehashed"] == 0
    assert second["rows_unchanged"] == 2
    assert _version_count(spark, table) == versions


def test_hash_list_change_skipped_key_is_not_rehashed(spark):
    table = _patient_table(spark)  # p1 current starts 2026-06-02, p2 starts 2026-06-01
    p1_before = sorted(
        (r["effective_from"], r["_record_hash"])
        for r in _read(spark, table).where("patient_id = 'p1'").collect()
    )

    metrics = _merge_v16(
        spark, table, [("p1", "Cambridge", None), ("p2", "Lynn", None)], effective_date="2026-06-01"
    )

    assert metrics["rows_skipped_backfill"] == 1
    assert metrics["rows_unchanged"] == 1
    assert metrics["rows_rehashed"] == 1  # p2 only
    p1_after = sorted(
        (r["effective_from"], r["_record_hash"])
        for r in _read(spark, table).where("patient_id = 'p1'").collect()
    )
    assert p1_after == p1_before


def test_type_alignment_equal_value_is_unchanged(spark):
    from decimal import Decimal

    from pyspark.sql import types as T

    table = f"default.scd2_types_{uuid.uuid4().hex}"
    spark.sql(
        f"""
        CREATE TABLE {table} (
            patient_id STRING, amount DECIMAL(18,2),
            _record_hash STRING, effective_from DATE, effective_to DATE, is_current BOOLEAN
        ) USING DELTA
        """
    )

    def run(value, data_type, effective_date):
        schema = T.StructType(
            [
                T.StructField("patient_id", T.StringType(), False),
                T.StructField("amount", data_type, True),
            ]
        )
        return scd2.apply_scd2(
            spark.createDataFrame([("p1", value)], schema),
            target_table=table,
            natural_keys=NATURAL_KEYS,
            hash_columns=["amount"],
            effective_date=effective_date,
        )

    run(Decimal("10.50"), T.DecimalType(18, 2), "2026-06-01")
    versions = _version_count(spark, table)

    metrics = run(10.5, T.DoubleType(), "2026-06-02")

    assert metrics["rows_unchanged"] == 1
    assert metrics["rows_closed"] == 0
    assert metrics["rows_inserted"] == 0
    assert metrics["rows_rehashed"] == 0
    assert _read(spark, table).count() == 1
    assert _version_count(spark, table) == versions
