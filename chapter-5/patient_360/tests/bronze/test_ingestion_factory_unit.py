"""Unit tests for ``ingestion_factory.build_bronze_taskgroup``.

Asserts the factory creates exactly one task per YAML in the configs
directory (LLD §4.2 / Decision 8).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patient_360.bronze import ingestion_factory as IF

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "airflow" / "configs"


def test_resolve_configs_dir_explicit(tmp_path):
    assert IF._resolve_configs_dir(tmp_path) == tmp_path


def test_resolve_configs_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AIRFLOW_CONFIGS_DIR", str(tmp_path))
    assert IF._resolve_configs_dir(None) == tmp_path


def test_resolve_configs_dir_default(monkeypatch):
    monkeypatch.delenv("AIRFLOW_CONFIGS_DIR", raising=False)
    assert IF._resolve_configs_dir(None) == Path("/opt/airflow/configs")


def test_load_configs_returns_thirteen():
    configs = IF._load_configs(CONFIGS_DIR)
    assert len(configs) == 13
    # every config has a `table` and the injected `__path__`
    for c in configs:
        assert "table" in c and "__path__" in c


def test_list_bronze_tables():
    tables = IF.list_bronze_tables(CONFIGS_DIR)
    assert len(tables) == 13
    # configs use bare table names; UC target prefixes synthea_
    assert set(tables) == {
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
    }


def test_load_configs_missing_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        IF._load_configs(tmp_path / "nope")


def test_build_bronze_taskgroup_task_count():
    """Factory must create exactly one task per config file (AC4)."""
    airflow = pytest.importorskip("airflow")
    if not hasattr(airflow, "DAG"):  # pragma: no cover -- stubbed airflow
        pytest.skip("airflow.DAG not importable in this env")
    from datetime import datetime

    dag = airflow.DAG("p360_test", start_date=datetime(2026, 1, 1), schedule=None, catchup=False)
    tg = IF.build_bronze_taskgroup(dag, CONFIGS_DIR, env="DEV")
    # tg.children maps task_id -> task / sub-group
    assert len(tg.children) == 13
