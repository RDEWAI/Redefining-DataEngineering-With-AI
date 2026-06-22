"""Silver-layer pytest fixtures for patient_360."""

import pytest


@pytest.fixture(scope="session")
def layer() -> str:
    return "silver"
