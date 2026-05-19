"""Pipeline configuration loader.

Reads `_infra/cd/config/{env}.yaml` per LLD §7.2 and applies env overrides.
The template profile is `_infra/cd/config/template.yaml`; env-specific
profiles (`DEV.yaml`, `STAGING.yaml`, `PROD.yaml`) override values from the
template at the same dotted-key path.

LLD references: §2.1 (utility module placement), §7 (configuration schema),
§7.2 (environment overrides).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

VALID_ENVS: tuple[str, ...] = ("DEV", "STAGING", "PROD")


@dataclass(frozen=True)
class PipelineConfig:
    """Frozen view of the resolved pipeline configuration.

    Carries the resolved environment label and the merged config tree.
    The merged tree is the source of truth — callers should read via
    :py:meth:`get` rather than mutating ``raw``.
    """

    env: str
    raw: dict[str, Any]

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Look up a dotted-key path (e.g. ``compute.spark_driver_memory``)."""
        node: Any = self.raw
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def _project_root() -> Path:
    """Return the patient_360 project root (parent of ``src/``)."""
    # __file__ -> src/patient_360/utils/pipeline_config.py
    return Path(__file__).resolve().parents[3]


def _config_dir() -> Path:
    """Return the env-config directory under ``_infra/cd/config/``.

    Override via the ``PIPELINE_CONFIG_DIR`` env var (used by tests).
    """
    override = os.environ.get("PIPELINE_CONFIG_DIR")
    if override:
        return Path(override)
    return _project_root() / "_infra" / "cd" / "config"


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` into ``base``, returning a new dict."""
    out: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(env: str) -> PipelineConfig:
    """Load and merge the pipeline config for ``env``.

    Args:
        env: One of ``DEV``, ``STAGING``, ``PROD`` (case-insensitive).

    Returns:
        Frozen ``PipelineConfig`` with the template profile overlaid by
        the env-specific profile.

    Raises:
        ValueError: if ``env`` is not a recognised profile.
        FileNotFoundError: if neither template nor env profile is on disk.
    """
    norm_env = env.upper()
    if norm_env not in VALID_ENVS:
        raise ValueError(f"Unknown env {env!r}; expected one of {VALID_ENVS}")

    cfg_dir = _config_dir()
    template_path = cfg_dir / "template.yaml"
    env_path = cfg_dir / f"{norm_env}.yaml"

    if not env_path.exists():
        raise FileNotFoundError(f"Config file not found: {env_path}")

    base: dict[str, Any] = {}
    if template_path.exists():
        with template_path.open("r", encoding="utf-8") as fh:
            base = yaml.safe_load(fh) or {}

    with env_path.open("r", encoding="utf-8") as fh:
        overlay = yaml.safe_load(fh) or {}

    merged = _deep_merge(base, overlay)
    merged["env"] = norm_env
    return PipelineConfig(env=norm_env, raw=merged)
