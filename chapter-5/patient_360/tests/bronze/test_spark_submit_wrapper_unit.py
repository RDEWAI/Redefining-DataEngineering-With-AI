"""Unit tests for ``spark_submit_wrapper.build_spark_submit_task``.

Most assertions skip when the airflow Spark provider isn't installed —
the contract under test is "the wrapper injects spark conf + jars +
runner module + --config-path argument" (LLD §2.3 / Decision 9).
"""

from __future__ import annotations

import pytest

from patient_360.bronze import spark_submit_wrapper as W


def test_default_constants():
    assert W.DEFAULT_RUNNER_MODULE == "patient_360.bronze.ingestion_runner"
    assert "delta" in W.DEFAULT_DELTA_PACKAGES.lower()
    assert (
        W.DEFAULT_SPARK_CONF["spark.sql.catalog.spark_catalog"]
        == "org.apache.spark.sql.delta.catalog.DeltaCatalog"
    )


def test_ingestion_runner_path_resolves():
    p = W.ingestion_runner_path()
    assert p.name == "ingestion_runner.py"
    assert p.is_file()


def test_build_spark_submit_task_injects_args():
    airflow = pytest.importorskip("airflow")
    if not hasattr(airflow, "DAG"):  # pragma: no cover
        pytest.skip("airflow.DAG not importable in this env")
    from datetime import datetime

    dag = airflow.DAG("p360_wrap", start_date=datetime(2026, 1, 1), schedule=None, catchup=False)
    op = W.build_spark_submit_task(
        task_id="t",
        config_path="/opt/airflow/configs/patients.yml",
        ds="2026-04-27",
        env="DEV",
        dag=dag,
    )
    args = op.application_args
    assert "--config-path" in args
    assert "/opt/airflow/configs/patients.yml" in args
    assert "--env" in args and "DEV" in args
    assert "--ds" in args and "2026-04-27" in args
    # spark conf includes Delta extensions + DeltaCatalog
    assert (
        op.conf["spark.sql.catalog.spark_catalog"]
        == "org.apache.spark.sql.delta.catalog.DeltaCatalog"
    )
