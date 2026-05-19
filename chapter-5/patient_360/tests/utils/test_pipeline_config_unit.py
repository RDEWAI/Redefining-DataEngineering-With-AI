"""Unit tests for patient_360.utils.pipeline_config."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from patient_360.utils.pipeline_config import (
    VALID_ENVS,
    PipelineConfig,
    load_config,
)


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point pipeline_config at a temp config dir with synthetic YAML."""
    (tmp_path / "template.yaml").write_text(
        textwrap.dedent(
            """
            compute:
              spark_driver_memory: "2g"
              spark_driver_cores: 1
            storage:
              base_path: "warehouse/template"
            """
        ).strip()
    )
    (tmp_path / "DEV.yaml").write_text(
        textwrap.dedent(
            """
            compute:
              spark_driver_memory: "2g"
            storage:
              base_path: "warehouse/dev"
            """
        ).strip()
    )
    (tmp_path / "STAGING.yaml").write_text(
        textwrap.dedent(
            """
            compute:
              spark_driver_memory: "4g"
              spark_driver_cores: 2
            storage:
              base_path: "warehouse/stage"
            """
        ).strip()
    )
    (tmp_path / "PROD.yaml").write_text(
        textwrap.dedent(
            """
            compute:
              spark_driver_memory: "8g"
            storage:
              base_path: "warehouse/prod"
            """
        ).strip()
    )
    monkeypatch.setenv("PIPELINE_CONFIG_DIR", str(tmp_path))
    return tmp_path


class TestLoadConfig:
    def test_dev_profile_merges_over_template(self, tmp_config_dir: Path) -> None:
        cfg = load_config("DEV")
        assert isinstance(cfg, PipelineConfig)
        assert cfg.env == "DEV"
        assert cfg.get("compute.spark_driver_memory") == "2g"
        # Inherited from template
        assert cfg.get("compute.spark_driver_cores") == 1
        # Overridden in DEV
        assert cfg.get("storage.base_path") == "warehouse/dev"

    def test_staging_profile_overrides_template(self, tmp_config_dir: Path) -> None:
        cfg = load_config("STAGING")
        assert cfg.env == "STAGING"
        assert cfg.get("compute.spark_driver_memory") == "4g"
        assert cfg.get("compute.spark_driver_cores") == 2

    def test_prod_profile_loads(self, tmp_config_dir: Path) -> None:
        cfg = load_config("PROD")
        assert cfg.env == "PROD"
        assert cfg.get("compute.spark_driver_memory") == "8g"

    def test_case_insensitive_env(self, tmp_config_dir: Path) -> None:
        cfg = load_config("dev")
        assert cfg.env == "DEV"

    def test_unknown_env_raises(self, tmp_config_dir: Path) -> None:
        with pytest.raises(ValueError):
            load_config("QA")

    def test_missing_env_file_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIPELINE_CONFIG_DIR", str(tmp_path))
        with pytest.raises(FileNotFoundError):
            load_config("DEV")

    def test_get_returns_default_for_missing_key(self, tmp_config_dir: Path) -> None:
        cfg = load_config("DEV")
        assert cfg.get("not.a.real.key", default="fallback") == "fallback"

    def test_valid_envs_constant(self) -> None:
        assert VALID_ENVS == ("DEV", "STAGING", "PROD")
