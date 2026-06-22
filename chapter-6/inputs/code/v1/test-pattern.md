---
Version: 1.0
Status: Approved
Topic: pytest layout, Spark + Delta + UC test fixtures, integration marker
---

# Test Pattern

## Purpose

Every module under `src/` has a mirrored test under `tests/`. Unit
tests run Spark in-process against a temp warehouse; integration tests
(real source data, real UC/Marquez) are marked and run separately.
`pytest` is the only runner; fixtures live in `tests/conftest.py` and
are parameterized for reuse.

## Pattern

- **Mirror layout** — `tests/{layer}/test_{module}.py` matches
  `src/{project}/{layer}/{module}.py`.
- **Module-level Spark session** — one `spark` fixture per test module
  (scope="session") using `DeltaCatalog` + a temp warehouse dir. Tests
  share the session; they clean schemas, not the session.
- **Temp warehouse per test run** — `tmp_path_factory` produces
  `warehouse/` and `metastore_db/`; each test run is isolated.
- **`@pytest.mark.integration`** — integration tests (UC running,
  Marquez receiving events) are skipped by default; run via
  `make test-integration` or `pytest -m integration`.
- **Factory-based test data** — small builders in
  `tests/factories.py` (`make_bronze_row`, `make_silver_fact`) keep
  fixtures terse and readable.
- **Assertions on DataFrames** — use `chispa` or a small
  `assert_df_equal` helper for ordered/unordered equality; never
  `df.collect() == expected` (order-dependent).

## Key APIs

- pytest 9.0.3 — `@pytest.fixture(scope="session")`, `tmp_path_factory`,
  `pytest.mark.integration`.
- pytest-mock 3.15.1 — `mocker.patch`.
- PySpark — `SparkSession.builder ... .enableHiveSupport()` + Delta
  extensions; no UC jar in unit tests.

## Illustrative snippet

```python
# tests/conftest.py
import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    warehouse = tmp_path_factory.mktemp("warehouse")
    spark = (SparkSession.builder
        .appName("{project}-tests")
        .master("local[2]")
        .config("spark.sql.warehouse.dir", str(warehouse))
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.extensions",
                "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.jars.packages",
                "io.delta:delta-spark_2.13:4.3.0")
        .getOrCreate())
    yield spark
    spark.stop()

@pytest.fixture()
def bronze_schema(spark):
    spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")
    yield
    spark.sql("DROP SCHEMA bronze CASCADE")
```

```python
# tests/bronze/test_ingest.py
import pytest
from {project}.bronze.ingest import ingest

def test_ingest_writes_with_audit_cols(spark, bronze_schema, tmp_path):
    src = tmp_path / "{table}.csv"
    src.write_text("{table}_id,name\n1,alice\n2,bob\n")
    cfg = {...}  # minimal config
    df = ingest(spark, cfg, ds="2026-04-24")
    assert {"ds", "ingested_at"}.issubset(df.columns)
    assert spark.table("bronze.{table}").count() == 2

@pytest.mark.integration
def test_ingest_end_to_end_against_uc(spark_with_uc):
    ...
```

## Common pitfalls

- New `SparkSession` per test — startup dominates runtime; use a
  session-scoped fixture.
- Sharing the same warehouse dir across test runs — stale Delta
  transaction logs leak between runs. Use `tmp_path_factory`.
- Comparing DataFrames by `collect()` without sort — order flips
  between Spark versions; always sort or use a DataFrame-equality
  helper.
- Importing the UC Spark jar in unit tests — pulls network at import
  time; leave UC to `@pytest.mark.integration`.
- `mocker.patch("spark.read")` instead of building a small real
  DataFrame — mocks drift from the PySpark API; prefer real
  lightweight DataFrames.

## References

- `/mvp/tests/conftest.py`
- `/mvp/tests/bronze/test_ingest.py`
- [`dependency-management.md`](dependency-management.md) (pytest pins)
- [`makefile-conventions.md`](makefile-conventions.md) (`test` /
  `test-integration` targets)
- pytest docs: https://docs.pytest.org/
