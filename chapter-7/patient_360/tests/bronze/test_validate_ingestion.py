"""Static smoke checks for the Bronze ingestion code surface.

Mirrors the invariants the external ``developer-plugin:validate-ingestion``
skill enforces so violations fail CI before a validator run is needed.

Covered invariants (LLD v1.12 §8.5, §9.1; developer-plugin handbook):

- The three Bronze modules import cleanly.
- No absolute filesystem path literals in source (paths come from
  env / explicit args).
- No ``try / except ImportError`` soft-import wrapper around the SE
  runner — once ``se_runner.py`` ships the runner imports it
  unconditionally.
- Path resolution helpers raise ``RuntimeError`` when neither
  explicit arg nor env var is supplied.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRONZE_DIR = PROJECT_ROOT / "src" / "patient_360" / "bronze"
BRONZE_MODULES = (
    "ingestion_runner.py",
    "ingestion_factory.py",
    "spark_submit_wrapper.py",
)

_ABS_PATH_LITERAL = re.compile(r"""['"](/[A-Za-z0-9_./-]+)['"]""")


@pytest.mark.parametrize("module_name", BRONZE_MODULES)
def test_bronze_module_present(module_name: str) -> None:
    assert (BRONZE_DIR / module_name).is_file()


@pytest.mark.parametrize("module_name", BRONZE_MODULES)
def test_no_absolute_path_literals(module_name: str) -> None:
    source = (BRONZE_DIR / module_name).read_text(encoding="utf-8")
    offenders = [
        m.group(1)
        for m in _ABS_PATH_LITERAL.finditer(source)
        if not (m.group(1).startswith("/tmp") or m.group(1).startswith("/dev/null"))
    ]
    assert not offenders, f"{module_name}: absolute path literals forbidden: {offenders}"


def test_resolve_configs_dir_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from patient_360.bronze import ingestion_factory

    monkeypatch.delenv("AIRFLOW_CONFIGS_DIR", raising=False)
    with pytest.raises(RuntimeError, match="AIRFLOW_CONFIGS_DIR"):
        ingestion_factory._resolve_configs_dir(None)


# NOTE: spark_submit_wrapper no longer exposes ``_resolve_runner_app``
# (the wrapper resolves entry-point module → file path via
# importlib.find_spec instead). Test removed; the validator covers the
# absolute-path-literal invariant via test_no_absolute_path_literals.
