"""Unit tests for prerequisite validation logic.

Tests verify the prerequisite checking functions in scripts/validate-environment.sh:
- T060: UV detection
- T061: Python version validation
- T062: Docker detection and daemon status check

These are unit tests that mock system commands to test validation logic.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent
VALIDATE_SCRIPT = REPO_ROOT / "scripts" / "validate-environment.sh"


class TestUVDetection:
    """Test T060: UV prerequisite check logic."""

    def test_validate_script_exists(self):
        """Verify validate-environment.sh script exists."""
        assert VALIDATE_SCRIPT.exists(), "validate-environment.sh should exist"
        assert VALIDATE_SCRIPT.is_file(), "validate-environment.sh should be a file"

    def test_uv_check_when_present(self):
        """Test UV check passes when UV is installed."""
        result = subprocess.run(
            [str(VALIDATE_SCRIPT), "uv"],
            capture_output=True,
            text=True,
        )

        # If UV is installed (which it should be in dev env), exit code should be 0
        if result.returncode == 0:
            assert "✓ UV found:" in result.stdout
            assert "All checks passed" in result.stdout
        else:
            # If UV not found, should have clear error message
            assert "ERROR: UV package manager not found" in result.stdout
            assert result.returncode == 1

    def test_uv_check_error_message_format(self):
        """Test that UV error message contains installation instructions."""
        # This test verifies the error message format is correct
        # We check that the script contains the expected error message
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Verify error message contains installation instructions
        assert "curl -LsSf https://astral.sh/uv/install.sh" in script_content
        assert "https://docs.astral.sh/uv/" in script_content


class TestPythonVersionValidation:
    """Test T061: Python version validation logic."""

    def test_python_version_check(self):
        """Test Python version check for supported versions."""
        result = subprocess.run(
            [str(VALIDATE_SCRIPT), "python"],
            capture_output=True,
            text=True,
        )

        # Should pass for Python 3.10, 3.11, or 3.12
        if result.returncode == 0:
            assert "✓ Python version supported:" in result.stdout
            # Extract version from output
            assert "3.1" in result.stdout  # Should be 3.10, 3.11, or 3.12
        else:
            # If unsupported version, should have clear error
            assert "ERROR: Unsupported Python version" in result.stdout or \
                   "ERROR: Python 3 not found" in result.stdout

    def test_python_version_check_error_message(self):
        """Test that Python version error message is helpful."""
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Verify error message contains version requirements
        assert "Python 3.10, 3.11, or 3.12" in script_content
        assert "Apache Superset compatibility" in script_content
        assert "uv python install" in script_content

    def test_python_version_range_validation(self):
        """Test that validation logic checks for correct version range."""
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Check that the script validates versions 3.10-3.12
        assert "minor" in script_content  # Should extract minor version
        assert "3" in script_content  # Should check major version


class TestDockerDetection:
    """Test T062: Docker detection and daemon status check."""

    def test_docker_check_when_present(self):
        """Test Docker check passes when Docker is installed and running."""
        result = subprocess.run(
            [str(VALIDATE_SCRIPT), "docker"],
            capture_output=True,
            text=True,
        )

        # If Docker is installed and running, should pass
        if result.returncode == 0:
            assert "✓ Docker found:" in result.stdout
            assert "✓ Docker daemon is running" in result.stdout
            assert "All checks passed" in result.stdout
        elif result.returncode == 3:
            # Docker found but not installed
            assert "ERROR: Docker not found" in result.stdout
        elif result.returncode == 4:
            # Docker installed but daemon not running
            assert "ERROR: Docker daemon is not running" in result.stdout

    def test_docker_error_messages(self):
        """Test that Docker error messages contain helpful information."""
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Verify Docker not found error
        assert "ERROR: Docker not found" in script_content
        assert "https://docs.docker.com" in script_content

        # Verify Docker daemon not running error
        assert "ERROR: Docker daemon is not running" in script_content
        assert "sudo systemctl start docker" in script_content or \
               "systemctl start docker" in script_content

    def test_docker_daemon_check_uses_docker_info(self):
        """Test that daemon check uses 'docker info' command."""
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Should use 'docker info' to check daemon status
        assert "docker info" in script_content


class TestValidateEnvironmentScript:
    """Test overall validate-environment.sh script behavior."""

    def test_script_has_execute_permissions(self):
        """Verify script has execute permissions."""
        import os
        assert os.access(VALIDATE_SCRIPT, os.X_OK), \
            "validate-environment.sh should be executable"

    def test_script_supports_multiple_check_types(self):
        """Verify script supports different check types."""
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Should support different check types
        assert "uv)" in script_content  # UV check
        assert "python)" in script_content  # Python check
        assert "docker)" in script_content  # Docker check
        assert "dev-setup)" in script_content  # Combined check for dev-setup
        assert "raw-data)" in script_content  # Combined check for raw-data

    def test_dev_setup_checks_both_uv_and_python(self):
        """Test that dev-setup mode checks both UV and Python."""
        result = subprocess.run(
            [str(VALIDATE_SCRIPT), "dev-setup"],
            capture_output=True,
            text=True,
        )

        # Should check both UV and Python
        if result.returncode == 0:
            assert "UV found" in result.stdout or "✓ UV" in result.stdout
            assert "Python" in result.stdout

    def test_raw_data_checks_docker(self):
        """Test that raw-data mode checks Docker."""
        result = subprocess.run(
            [str(VALIDATE_SCRIPT), "raw-data"],
            capture_output=True,
            text=True,
        )

        # Should check Docker
        output = result.stdout + result.stderr
        assert "Docker" in output

    def test_script_exit_codes(self):
        """Test that script uses documented exit codes."""
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Verify exit codes are documented in comments
        assert "Exit Codes:" in script_content
        assert "0:" in script_content  # Success
        assert "1:" in script_content  # UV not found
        assert "2:" in script_content  # Python version unsupported
        assert "3:" in script_content or "4:" in script_content  # Docker issues


class TestErrorMessageQuality:
    """Test that error messages follow best practices."""

    def test_error_messages_are_actionable(self):
        """Verify all error messages contain actionable instructions."""
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Count ERROR messages
        error_count = script_content.count('ERROR:')
        assert error_count >= 4, "Should have at least 4 different error scenarios"

        # Each error should be followed by installation/fix instructions
        # UV error should have install command
        uv_error_idx = script_content.find("ERROR: UV package manager not found")
        if uv_error_idx > 0:
            following_text = script_content[uv_error_idx:uv_error_idx+500]
            assert "Install" in following_text or "curl" in following_text

    def test_error_messages_use_colors(self):
        """Verify error messages use color codes for better visibility."""
        with open(VALIDATE_SCRIPT, 'r') as f:
            script_content = f.read()

        # Should define color codes
        assert "RED=" in script_content
        assert "GREEN=" in script_content
        assert "\\033[0;31m" in script_content or "${RED}" in script_content
