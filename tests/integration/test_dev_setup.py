"""Integration tests for dev-setup Makefile target.

Tests verify that the dev-setup target:
1. Executes successfully with proper exit codes
2. Creates .venv directory with correct structure
3. Installs all required packages (DuckDB, SQLMesh, Superset, pytest)
4. Makes packages importable in the virtual environment

These tests assume prerequisites (UV, Python) are already met.
"""

import os
import subprocess
from pathlib import Path

import pytest


# Repository root is two levels up from this test file
REPO_ROOT = Path(__file__).parent.parent.parent
VENV_PATH = REPO_ROOT / ".venv"
VENV_PYTHON = VENV_PATH / "bin" / "python"


@pytest.fixture(scope="module")
def cleanup_venv():
    """Fixture to ensure clean state before and after tests."""
    # Clean before tests
    if VENV_PATH.exists():
        subprocess.run(["rm", "-rf", str(VENV_PATH)], check=False)

    yield

    # Note: We don't clean up after tests to allow inspection
    # Use 'make clean' manually if needed


class TestDevSetupExecution:
    """Test that dev-setup target executes successfully."""

    def test_dev_setup_executes_successfully(self, cleanup_venv):
        """Test T024: Verify dev-setup target runs without errors."""
        result = subprocess.run(
            ["make", "dev-setup"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        # Assert successful exit code
        assert result.returncode == 0, (
            f"dev-setup failed with exit code {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        # Verify success message appears in output
        assert "Development environment setup complete" in result.stdout
        assert "[1/4] Checking prerequisites" in result.stdout
        assert "[2/4] Creating virtual environment" in result.stdout
        assert "[3/4] Installing dependencies" in result.stdout
        assert "[4/4] Validating environment" in result.stdout

    def test_dev_setup_with_missing_uv(self):
        """Test that dev-setup fails gracefully when UV is not installed."""
        # Skip this test if we can't temporarily hide UV
        # This would require PATH manipulation which is complex in pytest
        pytest.skip("Testing missing UV requires PATH manipulation")


class TestVenvCreation:
    """Test T025: Verify .venv directory is created correctly."""

    def test_venv_directory_exists(self):
        """Verify .venv directory is created."""
        assert VENV_PATH.exists(), ".venv directory should exist after dev-setup"
        assert VENV_PATH.is_dir(), ".venv should be a directory"

    def test_venv_python_exists(self):
        """Verify Python executable exists in .venv/bin/."""
        assert VENV_PYTHON.exists(), "Python executable should exist in .venv/bin/"
        assert os.access(VENV_PYTHON, os.X_OK), "Python should be executable"

    def test_venv_has_site_packages(self):
        """Verify site-packages directory exists for installed packages."""
        # Find site-packages directory
        lib_path = VENV_PATH / "lib"
        assert lib_path.exists(), "lib directory should exist in .venv"

        # Should have at least one pythonX.Y directory
        python_dirs = list(lib_path.glob("python*"))
        assert len(python_dirs) > 0, (
            "Should have at least one python* directory in lib/"
        )

        # Check site-packages exists
        site_packages = python_dirs[0] / "site-packages"
        assert site_packages.exists(), "site-packages should exist"


class TestPackageImports:
    """Test T026: Verify all required packages are importable."""

    def test_duckdb_importable(self):
        """Verify DuckDB is installed and importable."""
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import duckdb; print(duckdb.__version__)"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed to import duckdb:\n{result.stderr}"
        assert result.stdout.strip(), "DuckDB version should be printed"

    def test_sqlmesh_importable(self):
        """Verify SQLMesh is installed and importable."""
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import sqlmesh; print('SQLMesh imported')"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed to import sqlmesh:\n{result.stderr}"
        assert "SQLMesh imported" in result.stdout

    def test_superset_importable(self):
        """Verify Apache Superset is installed and importable."""
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import superset; print('Superset imported')"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed to import superset:\n{result.stderr}"
        assert "Superset imported" in result.stdout

    def test_pytest_importable(self):
        """Verify pytest is installed and importable."""
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import pytest; print(pytest.__version__)"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed to import pytest:\n{result.stderr}"
        assert result.stdout.strip(), "pytest version should be printed"

    def test_all_packages_together(self):
        """Verify all packages can be imported together without conflicts."""
        import_script = """
import duckdb
import sqlmesh
import superset
import pytest

print(f"DuckDB: {duckdb.__version__}")
print(f"pytest: {pytest.__version__}")
print("All packages imported successfully!")
"""

        result = subprocess.run(
            [str(VENV_PYTHON), "-c", import_script],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"Failed to import all packages together:\n{result.stderr}"
        )
        assert "All packages imported successfully" in result.stdout
        assert "DuckDB:" in result.stdout
        assert "pytest:" in result.stdout


class TestDevSetupIdempotency:
    """Test that dev-setup can be run multiple times safely."""

    def test_dev_setup_is_idempotent(self):
        """Verify running dev-setup twice doesn't cause errors."""
        # First run (already done in cleanup_venv fixture)

        # Second run - should succeed
        result = subprocess.run(
            ["make", "dev-setup"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"Second dev-setup run failed:\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
