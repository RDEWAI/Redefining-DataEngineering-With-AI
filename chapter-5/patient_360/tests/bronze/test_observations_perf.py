"""STORY-02-007 -- Performance benchmark for synthea_observations Bronze ingest.

LLD references: §4.4 (5-min target for ingest_observations on DEV),
§6.3 (shuffle.partitions=8 on DEV), §6.5 (observations -> 8 partitions).

The benchmark is opt-in (`pytest -m benchmark`) because it requires a full
local DuckDB warehouse and a running Spark + Unity Catalog OSS stack. When
those prerequisites are absent the tests skip cleanly so the default unit
suite stays fast and hermetic.

Two assertions are covered here:

* AC2 -- `synthea_observations` repartition honors `target_partitions: 8`
  from the per-table YAML before the Delta write.
* AC4 -- the full ingest of `synthea_observations` finishes in under 5
  minutes on DEV (1 executor, 2g) per LLD §4.4.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.benchmark

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBS_CONFIG = PROJECT_ROOT / "airflow" / "configs" / "observations.yml"
DEV_DUCKDB = PROJECT_ROOT / "data" / "raw.db"

# LLD §4.4 -- ingest_observations on DEV must complete in under 5 minutes.
MAX_RUNTIME_SECONDS = 5 * 60

# LLD §6.5 -- synthea_observations target partition count.
EXPECTED_TARGET_PARTITIONS = 8


def _load_obs_config() -> dict:
    return yaml.safe_load(OBS_CONFIG.read_text())


def test_observations_config_declares_target_partitions() -> None:
    """AC2 -- per-table YAML carries `target_partitions: 8` (LLD §6.5)."""
    cfg = _load_obs_config()
    assert cfg.get("target_partitions") == EXPECTED_TARGET_PARTITIONS, (
        f"observations.yml: target_partitions must be {EXPECTED_TARGET_PARTITIONS} "
        f"per LLD §6.5, got {cfg.get('target_partitions')!r}"
    )


def test_runner_applies_target_partitions(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2 -- the runner calls df.repartition(target_partitions) before write.

    Pure-Python harness: we stub Spark surfaces so the test never starts a
    real session yet still exercises the new branch in `run()`.
    """
    pytest.importorskip("pyspark", reason="pyspark not installed")
    from patient_360.bronze import ingestion_runner as runner

    repartition_calls: list[int] = []

    class _StubDF:
        def __init__(self) -> None:
            self.rdd = type("R", (), {"isEmpty": staticmethod(lambda: False)})()

        def repartition(self, n: int) -> "_StubDF":  # noqa: D401
            repartition_calls.append(int(n))
            return self

        # `add_metadata_columns` calls .withColumn; short-circuit.
        def withColumn(self, *_a, **_kw) -> "_StubDF":
            return self

    stub_df = _StubDF()

    class _StubSpark:
        def stop(self) -> None: ...

    cfg = {
        "table": "synthea_observations",
        "source": {"type": "duckdb", "database": "", "table": "x"},
        "contracts_dir": "contracts",
        "target_partitions": EXPECTED_TARGET_PARTITIONS,
        "catalog_bronze_catalog_name": "unity",
        "catalog_bronze_schema": "bronze",
        "dq_rules_dir": "dq_rules",
    }

    monkeypatch.setattr(runner, "load_yaml", lambda _p: cfg)
    monkeypatch.setattr(runner, "load_contract_schema", lambda *_a, **_kw: object())
    monkeypatch.setattr(runner, "build_spark", lambda **_kw: _StubSpark())
    monkeypatch.setattr(runner, "read_source", lambda *a, **kw: stub_df)
    monkeypatch.setattr(runner, "add_metadata_columns", lambda df, **_kw: df)
    monkeypatch.setattr(runner.se_runner, "run_dq", lambda df, **_kw: df)
    monkeypatch.setattr(runner, "write_bronze", lambda *a, **kw: None)

    import argparse

    rc = runner.run(
        argparse.Namespace(
            config_path="airflow/configs/observations.yml",
            ds="2026-05-11",
            env="DEV",
        )
    )
    assert rc == 0
    assert repartition_calls == [EXPECTED_TARGET_PARTITIONS], (
        f"runner did not repartition synthea_observations to "
        f"{EXPECTED_TARGET_PARTITIONS}; saw {repartition_calls}"
    )


@pytest.mark.skipif(
    not DEV_DUCKDB.exists(),
    reason=f"DEV DuckDB warehouse not found at {DEV_DUCKDB}; run `make load-raw-data` first",
)
def test_ingest_observations_under_five_minutes() -> None:
    """AC4 -- end-to-end DEV ingest of synthea_observations under 5 min.

    Requires `make load-raw-data` to have populated `data/raw.db` and a
    running Unity Catalog OSS / Delta warehouse. Otherwise skipped.
    """
    pytest.importorskip("pyspark", reason="pyspark not installed")
    from patient_360.bronze import ingestion_runner as runner

    import argparse

    args = argparse.Namespace(
        config_path=str(OBS_CONFIG),
        ds="2026-05-11",
        env="DEV",
    )
    started = time.monotonic()
    rc = runner.run(args)
    elapsed = time.monotonic() - started
    assert rc == 0, "ingest_observations runner returned non-zero"
    assert elapsed < MAX_RUNTIME_SECONDS, (
        f"ingest_observations took {elapsed:.1f}s; LLD §4.4 budget is "
        f"{MAX_RUNTIME_SECONDS}s on DEV"
    )
