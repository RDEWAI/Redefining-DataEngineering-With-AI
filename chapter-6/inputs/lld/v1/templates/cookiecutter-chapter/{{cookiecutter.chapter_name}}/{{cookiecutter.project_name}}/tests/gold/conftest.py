"""Gold-layer pytest fixtures for {{cookiecutter.project_name}}."""

import pytest


@pytest.fixture(scope="session")
def layer() -> str:
    return "gold"
