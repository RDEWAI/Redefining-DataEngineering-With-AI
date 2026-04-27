"""Tests for :mod:`patient_360.utils.pipeline_config`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from patient_360.utils import pipeline_config


@pytest.fixture()
def fake_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = {
        "compute": {"spark_driver_memory": "2g", "spark_executor_cores": 2},
        "storage": {"base_path": "warehouse/dev"},
        "scheduling": {"cron": "0 * * * *"},
    }
    (tmp_path / "dev.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setenv("PIPELINE_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_load_config_returns_frozen_config(fake_config_dir: Path) -> None:
    cfg = pipeline_config.load_config("dev")
    assert cfg.env == "dev"
    assert cfg.get("compute.spark_driver_memory") == "2g"
    assert cfg.get("storage.base_path") == "warehouse/dev"


def test_dotted_path_default_when_missing(fake_config_dir: Path) -> None:
    cfg = pipeline_config.load_config("dev")
    assert cfg.get("nonexistent.key", default="fallback") == "fallback"


def test_require_raises_for_missing_key(fake_config_dir: Path) -> None:
    cfg = pipeline_config.load_config("dev")
    with pytest.raises(KeyError):
        cfg.require("does.not.exist")


def test_overrides_deep_merge(fake_config_dir: Path) -> None:
    cfg = pipeline_config.load_config(
        "dev",
        overrides={"compute": {"spark_driver_memory": "8g"}},
    )
    assert cfg.get("compute.spark_driver_memory") == "8g"
    # Untouched leaves are preserved
    assert cfg.get("compute.spark_executor_cores") == 2
    assert cfg.get("storage.base_path") == "warehouse/dev"


def test_missing_config_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_CONFIG_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        pipeline_config.load_config("prod")


def test_empty_env_rejected() -> None:
    with pytest.raises(ValueError):
        pipeline_config.load_config("")
