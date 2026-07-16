"""STORY-02-005 -- Integration test: se_runner loads each rules YAML and
runs it against a synthetic DataFrame.

This is the AC4 evidence for STORY-02-005 and the LLD §8.6.1 smoke for
:func:`patient_360.utils.se_runner.run_dq`. Marked ``integration`` because
it spins up a local SparkSession with Delta + Spark-Expectations -- it
will be skipped when ``pyspark`` or ``spark_expectations`` are absent.

For each of the 13 Bronze tables we:

1. Locate ``dq_rules/synthea_<table>.yml`` (and assert it parses).
2. Build a synthetic DataFrame whose columns cover every ``column_name``
   referenced by ``row_dq`` rules, populated with PROD-valid values so
   the run is a green-path smoke (not a rule-coverage exhaustion).
3. Call :func:`se_runner.run_dq` with ``env=DEV`` (the SE ``DEV`` env in
   each YAML uses ``action_if_failed: ignore`` so the smoke is
   non-flaky regardless of synthetic data nuances).
4. Assert the returned DataFrame is non-empty and round-trips at least
   one row through SE without raising.

We do not assert on SE error-table content -- this test is a load +
run smoke, not a rule-correctness test.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

# Skip the whole module if pyspark or spark_expectations are unavailable.
pytest.importorskip("pyspark", reason="pyspark not installed")
if importlib.util.find_spec("spark_expectations") is None:  # pragma: no cover
    pytest.skip("spark_expectations not installed", allow_module_level=True)

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DQ_RULES_DIR = PROJECT_ROOT / "dq_rules"

LLD_BRONZE_STEMS: tuple[str, ...] = (
    "patients",
    "encounters",
    "conditions",
    "medications",
    "observations",
    "allergies",
    "immunizations",
    "procedures",
    "claims",
    "careplans",
    "organizations",
    "providers",
    "payers",
)


@pytest.fixture(scope="module")
def spark(tmp_path_factory):
    """Local SparkSession with Delta + a temp warehouse.

    Sized for a single-row smoke; no Unity Catalog dependency.
    """
    from pyspark.sql import SparkSession

    # configure_spark_with_delta_pip resolves the delta-spark Maven jar so
    # the path-based SE writers (`format("delta").save(<warehouse path>)`,
    # LLD §13 Decision 12/15) can find the `delta` data source. Without it
    # the extension/catalog conf is set but `delta.DefaultSource` is absent
    # from the classpath and `.save()` raises DATA_SOURCE_NOT_FOUND.
    delta = pytest.importorskip("delta", reason="delta-spark not installed")

    warehouse = tmp_path_factory.mktemp("se-warehouse")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("dq-rules-se-smoke")
        .config("spark.sql.warehouse.dir", str(warehouse))
        .config(
            "spark.sql.extensions",
            "io.delta.sql.DeltaSparkSessionExtension",
        )
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    spark = delta.configure_spark_with_delta_pip(builder).getOrCreate()
    yield spark
    spark.stop()


# Operators that imply the column participates in an arithmetic / numeric
# comparison, so the synthetic value must be a number (not a string stub) or
# Spark's implicit cast to the numeric target type raises CAST_INVALID_INPUT.
_NUMERIC_EXPR = re.compile(r"(>=|<=|>|<|\+|-|\*|/)")


def _columns_referenced(rules: list[dict]) -> set[str]:
    """Return every non-empty ``column_name`` referenced by row_dq rules."""
    cols: set[str] = set()
    for r in rules:
        if r.get("rule_type") == "row_dq":
            col = (r.get("column_name") or "").strip()
            if col:
                cols.add(col)
    # SE stats tables expect the audit columns regardless of the rule set.
    cols.update({"ds", "_ingested_at", "_source_batch_id"})
    return cols


def _numeric_columns(rules: list[dict]) -> set[str]:
    """Columns whose row_dq expectation does a numeric comparison.

    A string stub assigned to such a column forces Spark to cast it to the
    numeric target of the comparison (e.g. ``BASE_COST >= 0`` -> BIGINT),
    which fails with CAST_INVALID_INPUT. Populate these with a number.
    """
    cols: set[str] = set()
    for r in rules:
        if r.get("rule_type") != "row_dq":
            continue
        col = (r.get("column_name") or "").strip()
        expr = str(r.get("expectation") or "")
        if col and col in expr and _NUMERIC_EXPR.search(expr):
            cols.add(col)
    return cols


def _synthetic_row(columns: set[str], numeric: set[str] | None = None) -> dict:
    """PROD-valid sample populated for every column the YAML references.

    Uses a permissive value strategy: strings for unknown columns; sentinel
    dates / numerics for the well-known synthea ranges (BIRTHDATE, START,
    etc.); and ``0.0`` for any column whose row_dq expectation does a numeric
    comparison (``numeric`` set). The DEV env in every YAML uses
    ``action_if_failed: ignore`` so this row only has to keep ``NOT NULL``
    checks green.
    """
    numeric = numeric or set()
    today = date.today()
    row: dict = {}
    for col in columns:
        upper = col.upper()
        if upper in {"DS"} or col == "ds":
            row[col] = today.isoformat()
        elif col == "_ingested_at":
            row[col] = datetime.utcnow()
        elif col == "_source_batch_id":
            row[col] = "batch-smoke-0001"
        elif upper in {"BIRTHDATE", "DEATHDATE", "START", "STOP", "DATE"}:
            row[col] = today.isoformat()
        elif upper in {"GENDER"}:
            row[col] = "M"
        elif upper in {"MARITAL"}:
            row[col] = "S"
        elif upper in {"ENCOUNTERCLASS"}:
            row[col] = "ambulatory"
        elif upper in {"BASE_ENCOUNTER_COST", "AMOUNT", "TOTAL_CLAIM_COST"}:
            row[col] = 0.0
        elif col in numeric:
            row[col] = 0.0
        else:
            row[col] = f"smoke-{col}"
    return row


@pytest.mark.parametrize("stem", LLD_BRONZE_STEMS)
def test_se_runner_loads_and_runs_rules_against_synthetic_df(
    spark, stem: str, tmp_path, monkeypatch
) -> None:
    """AC4 -- run_dq loads dq_rules/synthea_<stem>.yml + returns a DataFrame."""
    from patient_360.utils import se_runner

    # UC 0.5.0 managed SE audit tables (LLD §2.3 item 3 v1.20 / §13 Decision
    # 12 corrected). No live UC server in this hermetic smoke, so qualify the
    # SE target into the local DeltaCatalog (`spark_catalog`) and pre-create
    # the `bronze` schema so SE's managed `saveAsTable` for `<target>_stats` /
    # `<target>_error` resolves.
    monkeypatch.setenv("SE_UC_CATALOG", "spark_catalog")
    monkeypatch.setenv("SE_UC_BRONZE_SCHEMA", "bronze")
    spark.sql("CREATE SCHEMA IF NOT EXISTS spark_catalog.bronze")

    rules_path = DQ_RULES_DIR / f"synthea_{stem}.yml"
    assert rules_path.is_file(), f"missing rules: {rules_path}"

    cfg = yaml.safe_load(rules_path.read_text())
    all_rules = cfg.get("rules") or []

    # AC4 smoke validates the INLINE row_dq/agg_dq rules against a single
    # synthetic DataFrame. `query_dq` rules are cross-table reconciliation
    # checks (e.g. `FROM synthea.<t>` vs `FROM bronze.synthea_<t>`); they
    # reference sibling catalog tables that do not exist in this hermetic
    # session and are exercised by the reconciliation layer, not here. Run
    # the smoke over the inline rule subset by writing a filtered temp YAML
    # and pointing run_dq at it (per-table convention preserved).
    rules = [r for r in all_rules if r.get("rule_type") in {"row_dq", "agg_dq"}]
    assert rules, f"synthea_{stem}: no row_dq/agg_dq rules to smoke"

    # This is a load+run smoke (AC4), not a threshold-correctness test. A
    # single synthetic row can never satisfy production agg_dq row-count bands
    # (e.g. `count(*) > 5494`), and a per-rule `action_if_failed: fail`
    # overrides the DEV env's `ignore`, so SE would raise SparkExpectOrFail.
    # Downgrade per-rule `fail`/`drop` to `ignore` for the smoke copy so the
    # rules still LOAD and EXECUTE without aborting on synthetic data.
    rules = [
        {**r, "action_if_failed": "ignore"} if r.get("action_if_failed") in {"fail", "drop"} else r
        for r in rules
    ]

    smoke_dir = tmp_path / "dq_rules"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    smoke_cfg = dict(cfg)
    smoke_cfg["rules"] = rules
    # The shipped rules carry an FQN `table_name` (`unity.bronze.synthea_<s>`)
    # which `_qualify_target_table` passes through verbatim — but there is no
    # live `unity` catalog in this hermetic smoke. Rewrite the DEV env
    # `table_name` to a BARE name so the SE_UC_CATALOG override qualifies it to
    # `spark_catalog.bronze.synthea_<s>` (resolvable in the local DeltaCatalog).
    smoke_dq_env = {k: dict(v) for k, v in (smoke_cfg.get("dq_env") or {}).items()}
    if "DEV" in smoke_dq_env:
        smoke_dq_env["DEV"]["table_name"] = f"synthea_{stem}"
    smoke_cfg["dq_env"] = smoke_dq_env
    (smoke_dir / f"synthea_{stem}.yml").write_text(yaml.safe_dump(smoke_cfg))

    cols = _columns_referenced(rules)
    numeric = _numeric_columns(rules)

    row = _synthetic_row(cols, numeric=numeric)
    # SE prefers string columns for free-text values; let Spark infer dtype.
    df = spark.createDataFrame([row])

    quarantine = tmp_path / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)

    out = se_runner.run_dq(
        df,
        table=f"synthea_{stem}",
        env="DEV",
        dq_rules_dir=smoke_dir,
        action_if_failed="ignore",
        quarantine_path=str(quarantine),
    )

    # The wrapped DataFrame must round-trip non-empty for the smoke.
    assert out is not None
    assert out.count() >= 1, (
        f"synthea_{stem}: run_dq returned 0 rows for a synthetic green-path row"
    )
