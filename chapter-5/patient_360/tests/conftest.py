"""Shared pytest fixtures for patient_360 tests."""

import pytest


@pytest.fixture(scope="session")
def project_name() -> str:
    return "patient_360"
