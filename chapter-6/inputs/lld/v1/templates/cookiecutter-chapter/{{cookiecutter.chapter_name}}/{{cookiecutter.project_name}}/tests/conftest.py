"""Shared pytest fixtures for {{cookiecutter.project_name}} tests."""

import pytest


@pytest.fixture(scope="session")
def project_name() -> str:
    return "{{cookiecutter.project_name}}"
