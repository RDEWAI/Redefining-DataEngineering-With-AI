"""Pipeline configuration loader.

Loads environment-specific YAML configuration from
``_infra/cd/config/{env}.yaml`` and exposes nested values via dotted-path
lookup (e.g. ``cfg.get("compute.spark_executor_memory")``).

Per LLD §7.1 (Parameter Inventory) and §7.2 (Environment Overrides).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class PipelineConfig:
    """Frozen configuration object exposing dotted-path lookup."""

    env: str
    data: dict[str, Any] = field(default_factory=dict)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Resolve a dotted-path key (e.g. ``compute.spark_driver_memory``)."""
        node: Any = self.data
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def require(self, dotted_key: str) -> Any:
        """Like ``get`` but raises ``KeyError`` if the key is missing."""
        sentinel = object()
        value = self.get(dotted_key, default=sentinel)
        if value is sentinel:
            raise KeyError(f"Missing required config key: {dotted_key}")
        return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``override`` into ``base`` (override wins on leaf conflicts)."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _config_dir() -> Path:
    """Resolve the config directory (``_infra/cd/config``)."""
    override = os.environ.get("PIPELINE_CONFIG_DIR")
    if override:
        return Path(override)
    return _PROJECT_ROOT / "_infra" / "cd" / "config"


def load_config(env: str, *, overrides: dict[str, Any] | None = None) -> PipelineConfig:
    """Load configuration for ``env`` from ``_infra/cd/config/{env}.yaml``.

    Parameters
    ----------
    env:
        Environment name (``dev``, ``staging``, ``prod``).
    overrides:
        Optional in-memory dict deep-merged on top of the loaded YAML.

    Returns
    -------
    PipelineConfig
        Frozen configuration object.

    Raises
    ------
    FileNotFoundError
        When ``_infra/cd/config/{env}.yaml`` does not exist.
    """
    if not env:
        raise ValueError("env must be a non-empty string")
    config_path = _config_dir() / f"{env}.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"Pipeline config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle) or {}
    if overrides:
        data = _deep_merge(data, overrides)
    return PipelineConfig(env=env, data=data)
