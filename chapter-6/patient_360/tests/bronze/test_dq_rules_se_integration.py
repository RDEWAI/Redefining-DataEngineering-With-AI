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

    warehouse = tmp_path_factory.mktemp("se-warehouse")
    spark = (
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
        .getOrCreate()
    )
    yield spark
    spark.stop()


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


def _synthetic_row(columns: set[str]) -> dict:
    """PROD-valid sample populated for every column the YAML references.

    Uses a permissive value strategy: strings for unknown columns; sentinel
    dates / numerics for the well-known synthea ranges (BIRTHDATE, START,
    etc.). The DEV env in every YAML uses ``action_if_failed: ignore``
    so this row only has to keep ``NOT NULL`` checks green.
    """
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
        else:
            row[col] = f"smoke-{col}"
    return row


@pytest.mark.parametrize("stem", LLD_BRONZE_STEMS)
def test_se_runner_loads_and_runs_rules_against_synthetic_df(
    spark, stem: str, tmp_path
) -> None:
    """AC4 -- run_dq loads dq_rules/synthea_<stem>.yml + returns a DataFrame."""
    from patient_360.utils import se_runner

    rules_path = DQ_RULES_DIR / f"synthea_{stem}.yml"
    assert rules_path.is_file(), f"missing rules: {rules_path}"

    cfg = yaml.safe_load(rules_path.read_text())
    rules = cfg.get("rules") or []
    cols = _columns_referenced(rules)

    row = _synthetic_row(cols)
    # SE prefers string columns for free-text values; let Spark infer dtype.
    df = spark.createDataFrame([row])

    quarantine = tmp_path / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)

    out = se_runner.run_dq(
        df,
        table=f"synthea_{stem}",
        env="DEV",
        dq_rules_dir=DQ_RULES_DIR,
        action_if_failed="ignore",
        quarantine_path=str(quarantine),
    )

    # The wrapped DataFrame must round-trip non-empty for the smoke.
    assert out is not None
    assert out.count() >= 1, (
        f"synthea_{stem}: run_dq returned 0 rows for a synthetic green-path row"
    )
