"""Shared pytest fixtures for patient_360 tests."""

import os
import sys

import pytest

# Pin the PySpark worker interpreter to the test driver interpreter so Spark
# workers use the same venv Python as the driver. Without this, the uv venv
# driver (Python 3.12) and a stray system worker (Python 3.11) raise
# PYTHON_VERSION_MISMATCH. setdefault preserves an explicit env override.
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)


@pytest.fixture(scope="session")
def project_name() -> str:
    return "patient_360"
