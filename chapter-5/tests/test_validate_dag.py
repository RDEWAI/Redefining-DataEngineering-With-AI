"""Tests for developer-plugin/skills/validate-dag/scripts/validate_dag.py.

Covers all three regression rules introduced after spokane's first green
Bronze run: DAG-PATHS-001, DAG-PATHS-002, UC-WIRING-001.
"""
# ruff: noqa: E501

from __future__ import annotations

import sys
from pathlib import Path

VALIDATOR_DIR = (
    Path(__file__).resolve().parent.parent
    / "developer-plugin"
    / "skills"
    / "validate-dag"
    / "scripts"
)
sys.path.insert(0, str(VALIDATOR_DIR))

from validate_dag import Level, check_file, main  # noqa: E402


def _write(tmp_path: Path, name: str, body: str) -> Path:
    f = tmp_path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return f


# -- DAG-PATHS-001 -----------------------------------------------------------


class TestDagPaths001:
    """Reject literal `application="run_local.py"` in generated DAG files."""

    def test_relative_application_literal_rejected(self, tmp_path):
        dag = _write(
            tmp_path,
            "airflow/dags/sample_dag.py",
            'SparkSubmitOperator(task_id="x", application="run_local.py", conn_id="spark_default")\n',
        )
        findings = check_file(dag)
        assert any(f.rule == "DAG-PATHS-001" and f.level == Level.CRITICAL for f in findings)

    def test_env_var_resolution_passes(self, tmp_path):
        dag = _write(
            tmp_path,
            "airflow/dags/sample_dag.py",
            'import os\napp = os.environ.get("BRONZE_RUNNER_APP", "/opt/airflow/jobs/run_bronze_ingestion.py")\n'
            'SparkSubmitOperator(task_id="x", application=app, conn_id="spark_default")\n',
        )
        findings = check_file(dag)
        assert not any(f.rule == "DAG-PATHS-001" for f in findings)

    def test_anti_pattern_comment_skipped(self, tmp_path):
        """Documentation comments quoting the bad pattern are allowed."""
        dag = _write(
            tmp_path,
            "airflow/dags/sample_dag.py",
            '# NEVER use application="run_local.py" — relative paths break in containers.\n',
        )
        findings = check_file(dag)
        assert not any(f.rule == "DAG-PATHS-001" for f in findings)


# -- DAG-PATHS-002 -----------------------------------------------------------


class TestDagPaths002:
    """Reject literal `configs_dir="airflow/configs"` in generated DAG files."""

    def test_relative_configs_dir_literal_rejected(self, tmp_path):
        dag = _write(
            tmp_path,
            "airflow/dags/sample_dag.py",
            'build_bronze_taskgroup(dag, configs_dir="airflow/configs")\n',
        )
        findings = check_file(dag)
        assert any(f.rule == "DAG-PATHS-002" and f.level == Level.CRITICAL for f in findings)

    def test_env_var_resolution_passes(self, tmp_path):
        dag = _write(
            tmp_path,
            "airflow/dags/sample_dag.py",
            'configs_dir = os.environ.get("AIRFLOW_CONFIGS_DIR", "/opt/airflow/configs")\n',
        )
        findings = check_file(dag)
        assert not any(f.rule == "DAG-PATHS-002" for f in findings)


# -- UC-WIRING-001 -----------------------------------------------------------


class TestUcWiring001:
    """Reject path-based Bronze writes (`format("delta").save(...)`)."""

    def test_bronze_path_save_rejected(self, tmp_path):
        runner = _write(
            tmp_path,
            "src/patient_360/bronze/ingestion_runner.py",
            'df.write.format("delta").save("/tmp/uc-warehouse/DEV/bronze/synthea_patients/")\n',
        )
        findings = check_file(runner)
        assert any(f.rule == "UC-WIRING-001" and f.level == Level.CRITICAL for f in findings)

    def test_bronze_save_as_table_passes(self, tmp_path):
        runner = _write(
            tmp_path,
            "src/patient_360/bronze/ingestion_runner.py",
            'df.write.format("delta").mode("append").saveAsTable("unity.bronze.synthea_patients")\n',
        )
        findings = check_file(runner)
        assert not any(f.rule == "UC-WIRING-001" for f in findings)

    def test_silver_path_save_allowed(self, tmp_path):
        """Silver writers are out of scope for UC-WIRING-001."""
        runner = _write(
            tmp_path,
            "src/patient_360/silver/dim_runner.py",
            'df.write.format("delta").save("/tmp/uc-warehouse/DEV/silver/dim_patient/")\n',
        )
        findings = check_file(runner)
        assert not any(f.rule == "UC-WIRING-001" for f in findings)

    def test_bronze_anti_pattern_comment_skipped(self, tmp_path):
        runner = _write(
            tmp_path,
            "src/patient_360/bronze/ingestion_runner.py",
            '# NEVER `df.write.format("delta").save("/tmp/...")` — UC won\'t see it.\n',
        )
        findings = check_file(runner)
        assert not any(f.rule == "UC-WIRING-001" for f in findings)


# -- CLI -------------------------------------------------------------------


class TestCli:
    def test_clean_file_exits_zero(self, tmp_path, capsys):
        f = _write(tmp_path, "ok.py", "x = 1\n")
        assert main([str(f)]) == 0

    def test_critical_exits_one(self, tmp_path, capsys):
        f = _write(tmp_path, "airflow/dags/bad.py", 'application="run_local.py"\n')
        assert main([str(f)]) == 1

    def test_all_recurses(self, tmp_path):
        _write(tmp_path, "src/x/bronze/runner.py", 'df.write.format("delta").save("/tmp/x")\n')
        _write(tmp_path, "src/x/silver/runner.py", "ok = True\n")
        assert main(["--all", str(tmp_path)]) == 1

    def test_missing_path_exits_three(self, tmp_path):
        assert main([str(tmp_path / "nope.py")]) == 3
