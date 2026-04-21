"""Invokes the developer-plugin validator and asserts the project passes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECT_ROOT = REPO_ROOT / "chapter-5" / "patient_360"
VALIDATOR = (
    REPO_ROOT
    / "chapter-5"
    / "developer-plugin"
    / "skills"
    / "ingestion"
    / "validate-ingestion"
    / "scripts"
    / "validate_ingestion.py"
)
LLD_DIR = REPO_ROOT / "chapter-5" / "inputs" / "lld" / "v1"


def _latest_lld() -> Path:
    candidates = sorted(p for p in LLD_DIR.glob("LLD-*.md") if p.suffix == ".md")
    assert candidates, f"no LLD markdown found under {LLD_DIR}"
    return candidates[-1]


def test_validator_passes_on_current_project() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--project-root", str(PROJECT_ROOT),
            "--lld", str(_latest_lld()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"validator failed (exit {result.returncode}):\nSTDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    assert "Result: PASS" in result.stdout
    assert "CRITICAL: 0 issue(s)" in result.stdout


def test_validator_flags_missing_runtime_dep(tmp_path: Path) -> None:
    """Scaffold a minimal copy of the project without pyspark and confirm the
    validator raises the runtime-dep CRITICAL."""
    fake_project = tmp_path / "fake"
    (fake_project / "src" / "patient_360" / "bronze").mkdir(parents=True)
    (fake_project / "airflow" / "configs").mkdir(parents=True)
    (fake_project / "contracts").mkdir()
    (fake_project / "dq_rules").mkdir()
    (fake_project / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="0"\ndependencies=["pyyaml>=6.0"]\n',
        encoding="utf-8",
    )
    for mod in ("ingestion_runner.py", "ingestion_factory.py", "spark_submit_wrapper.py"):
        (fake_project / "src" / "patient_360" / "bronze" / mod).write_text(
            '"""stub."""\n', encoding="utf-8"
        )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--project-root", str(fake_project),
            "--lld", str(_latest_lld()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "pyspark" in result.stdout
    assert "delta-spark" in result.stdout
    assert "spark-expectations" in result.stdout
