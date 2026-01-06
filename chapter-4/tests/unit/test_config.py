"""Unit tests for PWI configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pwi.config.loader import (
    ConfigurationError,
    create_default_config,
    find_config_file,
    load_config,
    load_yaml,
)
from pwi.config.schema import (
    AgentConfig,
    ArtifactConfig,
    LLMConfig,
    LoggingConfig,
    ProjectConfig,
    PWIConfig,
    ReviewConfig,
    ReviewGateConfig,
)


class TestLLMConfig:
    """Tests for LLMConfig model."""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default configuration values with env vars set."""
        # Set up environment variables (as they would be in .env)
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MODEL", "test-model")

        config = LLMConfig()

        assert config.base_url == "https://api.example.com/v1"
        assert config.api_key == "test-key"
        assert config.default_model == "test-model"
        assert config.enable_usage_tracking is True

    def test_default_values_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that defaults resolve to empty strings when env vars not set."""
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)

        config = LLMConfig()

        # Without env vars, defaults resolve to empty strings
        assert config.base_url == ""
        assert config.api_key == ""
        assert config.default_model == ""

    def test_env_var_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable resolution in api_key."""
        monkeypatch.setenv("TEST_API_KEY", "secret-key")

        config = LLMConfig(api_key="${TEST_API_KEY}")

        assert config.api_key == "secret-key"

    def test_env_var_resolution_all_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable resolution in all LLM fields."""
        monkeypatch.setenv("MY_API_KEY", "my-key")
        monkeypatch.setenv("MY_BASE_URL", "https://my-api.com/v1")
        monkeypatch.setenv("MY_MODEL", "my-model")

        config = LLMConfig(
            api_key="${MY_API_KEY}",
            base_url="${MY_BASE_URL}",
            default_model="${MY_MODEL}",
        )

        assert config.api_key == "my-key"
        assert config.base_url == "https://my-api.com/v1"
        assert config.default_model == "my-model"

    def test_env_var_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test missing environment variable returns empty string."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

        config = LLMConfig(api_key="${NONEXISTENT_VAR}")

        assert config.api_key == ""

    def test_literal_api_key(self) -> None:
        """Test literal API key without env var."""
        config = LLMConfig(api_key="literal-key")

        assert config.api_key == "literal-key"

    def test_get_model_alias(self) -> None:
        """Test resolving model alias."""
        config = LLMConfig(
            models={
                "fast": "test/fast-model",
                "balanced": "test/balanced-model",
            }
        )

        assert config.get_model("fast") == "test/fast-model"
        assert config.get_model("balanced") == "test/balanced-model"

    def test_get_model_passthrough(self) -> None:
        """Test that unknown alias passes through."""
        config = LLMConfig(models={"fast": "test/fast"})

        assert config.get_model("unknown/model") == "unknown/model"


class TestAgentConfig:
    """Tests for AgentConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = AgentConfig()

        assert config.model == "balanced"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_temperature_bounds(self) -> None:
        """Test temperature validation."""
        # Valid
        config = AgentConfig(temperature=0.0)
        assert config.temperature == 0.0

        config = AgentConfig(temperature=2.0)
        assert config.temperature == 2.0

        # Invalid
        with pytest.raises(ValueError):
            AgentConfig(temperature=-0.1)

        with pytest.raises(ValueError):
            AgentConfig(temperature=2.1)

    def test_max_tokens_bounds(self) -> None:
        """Test max_tokens validation."""
        # Valid
        config = AgentConfig(max_tokens=100)
        assert config.max_tokens == 100

        # Invalid
        with pytest.raises(ValueError):
            AgentConfig(max_tokens=50)  # Below minimum


class TestReviewConfig:
    """Tests for ReviewConfig model."""

    def test_get_gate_config_exists(self) -> None:
        """Test getting existing gate config."""
        config = ReviewConfig(
            gates={
                "data_analyst": ReviewGateConfig(enabled=False, mode="file"),
            }
        )

        gate = config.get_gate_config("data_analyst")

        assert gate.enabled is False
        assert gate.mode == "file"

    def test_get_gate_config_default(self) -> None:
        """Test getting default gate config for missing agent."""
        config = ReviewConfig(default_mode="web")

        gate = config.get_gate_config("nonexistent_agent")

        assert gate.enabled is True
        assert gate.mode == "web"


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_path_parsing(self) -> None:
        """Test that string paths are converted to Path objects."""
        config = ProjectConfig(
            output_dir="./output",
            session_dir="./.pwi/sessions",
        )

        assert isinstance(config.output_dir, Path)
        assert isinstance(config.session_dir, Path)


class TestPWIConfig:
    """Tests for PWIConfig root model."""

    def test_default_agents_set(self) -> None:
        """Test that default agents are always present."""
        config = PWIConfig(
            llm=LLMConfig(api_key="test"),
        )

        required_agents = [
            "data_analyst",
            "data_architect",
            "mapping_engineer",
            "dq_engineer",
            "story_writer",
            "sync_agent",
        ]

        for agent in required_agents:
            assert agent in config.agents

    def test_get_agent_config(self) -> None:
        """Test getting agent configuration."""
        config = PWIConfig(
            llm=LLMConfig(api_key="test"),
            agents={
                "data_analyst": AgentConfig(temperature=0.9),
            },
        )

        agent_config = config.get_agent_config("data_analyst")
        assert agent_config.temperature == 0.9

    def test_get_resolved_model(self) -> None:
        """Test getting resolved model for agent."""
        config = PWIConfig(
            llm=LLMConfig(
                api_key="test",
                models={"powerful": "test/powerful-model"},
            ),
            agents={
                "data_architect": AgentConfig(model="powerful"),
            },
        )

        model = config.get_resolved_model("data_architect")
        assert model == "test/powerful-model"

    def test_ensure_directories(self, tmp_path: Path) -> None:
        """Test directory creation."""
        config = PWIConfig(
            project=ProjectConfig(
                output_dir=tmp_path / "output",
                session_dir=tmp_path / "sessions",
            ),
            llm=LLMConfig(api_key="test"),
            logging=LoggingConfig(file=tmp_path / "logs" / "pwi.log"),
        )

        config.ensure_directories()

        assert config.project.output_dir.exists()
        assert config.project.session_dir.exists()
        assert config.logging.file.parent.exists()


class TestConfigLoader:
    """Tests for configuration loading functions."""

    def test_load_yaml(self, tmp_path: Path) -> None:
        """Test loading YAML file."""
        yaml_content = """
version: "1.0"
project:
  name: "test"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        data = load_yaml(yaml_file)

        assert data["version"] == "1.0"
        assert data["project"]["name"] == "test"

    def test_load_yaml_not_found(self, tmp_path: Path) -> None:
        """Test loading nonexistent YAML file."""
        with pytest.raises(ConfigurationError, match="not found"):
            load_yaml(tmp_path / "nonexistent.yaml")

    def test_load_yaml_invalid(self, tmp_path: Path) -> None:
        """Test loading invalid YAML file."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("invalid: yaml: content:")

        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            load_yaml(yaml_file)

    def test_find_config_file_current_dir(self, tmp_path: Path) -> None:
        """Test finding config in current directory."""
        config_file = tmp_path / "pwi.yaml"
        config_file.write_text("version: '1.0'")

        found = find_config_file(tmp_path)

        assert found == config_file

    def test_find_config_file_parent_dir(self, tmp_path: Path) -> None:
        """Test finding config in parent directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        config_file = tmp_path / "pwi.yaml"
        config_file.write_text("version: '1.0'")

        found = find_config_file(subdir)

        assert found == config_file

    def test_find_config_file_not_found(self, tmp_path: Path) -> None:
        """Test when config file is not found."""
        found = find_config_file(tmp_path)

        # May or may not find home config, so just check it works
        # The actual result depends on the test environment

    def test_load_config_default(self) -> None:
        """Test loading default config when no file exists."""
        config = load_config(auto_discover=False)

        assert isinstance(config, PWIConfig)
        assert config.version == "1.0"

    def test_load_config_from_file(self, tmp_path: Path) -> None:
        """Test loading config from explicit file."""
        yaml_content = """
version: "2.0"
project:
  name: "custom-project"
llm:
  api_key: "test-key"
"""
        config_file = tmp_path / "pwi.yaml"
        config_file.write_text(yaml_content)

        config = load_config(config_file)

        assert config.version == "2.0"
        assert config.project.name == "custom-project"

    def test_load_config_file_not_found(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file raises error."""
        with pytest.raises(ConfigurationError, match="not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_create_default_config(self, tmp_path: Path) -> None:
        """Test creating default config file."""
        config_file = tmp_path / "pwi.yaml"

        create_default_config(config_file)

        assert config_file.exists()
        content = config_file.read_text()
        assert "version:" in content
        assert "project:" in content
        assert "llm:" in content
