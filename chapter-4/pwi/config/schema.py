"""Pydantic configuration schemas for Planning with Intent.

This module defines the data models for validating and parsing
the pwi.yaml configuration file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LLMConfig(BaseModel):
    """LLM provider configuration.

    Follows OpenAI API specification - works with any OpenAI-compatible provider
    (OpenAI, OpenRouter, Azure, Ollama, vLLM, etc.)
    """

    # OpenAI API compatible settings
    base_url: str = "${LLM_BASE_URL}"
    api_key: str = "${LLM_API_KEY}"
    default_model: str = "${LLM_MODEL}"

    # Model aliases for convenience
    models: dict[str, str] = Field(default_factory=dict)

    # Optional: track token usage
    enable_usage_tracking: bool = True

    @staticmethod
    def _resolve_env_var(value: str) -> str:
        """Resolve environment variable references like ${VAR_NAME}."""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.environ.get(env_var, "")
        return value if isinstance(value, str) else ""

    @model_validator(mode="after")
    def resolve_env_vars(self) -> LLMConfig:
        """Resolve environment variables in all string fields."""
        # Use object.__setattr__ to bypass Pydantic's frozen model protection
        object.__setattr__(self, "base_url", self._resolve_env_var(self.base_url))
        object.__setattr__(self, "api_key", self._resolve_env_var(self.api_key))
        object.__setattr__(self, "default_model", self._resolve_env_var(self.default_model))

        # Also resolve env vars in model aliases
        resolved_models = {k: self._resolve_env_var(v) for k, v in self.models.items()}
        object.__setattr__(self, "models", resolved_models)

        return self

    def get_model(self, alias_or_name: str) -> str:
        """Resolve a model alias to its full name, or return as-is if not found."""
        return self.models.get(alias_or_name, alias_or_name)


class AgentConfig(BaseModel):
    """Individual agent configuration."""

    model: str = "balanced"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=100, le=128000)


class ReviewGateConfig(BaseModel):
    """Review gate configuration for a single agent."""

    enabled: bool = True
    mode: Literal["cli", "file", "web"] = "cli"


class ReviewConfig(BaseModel):
    """Review system configuration."""

    default_mode: Literal["cli", "file", "web"] = "cli"
    timeout_minutes: int = Field(60, ge=1, le=1440)
    gates: dict[str, ReviewGateConfig] = Field(default_factory=dict)

    def get_gate_config(self, agent_name: str) -> ReviewGateConfig:
        """Get review gate config for an agent, using defaults if not specified."""
        if agent_name in self.gates:
            return self.gates[agent_name]
        return ReviewGateConfig(enabled=True, mode=self.default_mode)


class ArtifactConfig(BaseModel):
    """Artifact generation configuration."""

    format: Literal["markdown", "csv", "yaml", "json"] = "markdown"
    template: str = ""


class ProjectConfig(BaseModel):
    """Project settings."""

    name: str = "pwi-project"
    type: Literal["data_engineering"] = "data_engineering"
    output_dir: Path = Path("./output")
    session_dir: Path = Path("./.pwi/sessions")

    @field_validator("output_dir", "session_dir", mode="before")
    @classmethod
    def parse_path(cls, v: Any) -> Path:
        """Convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v)
        if isinstance(v, Path):
            return v
        return Path(str(v))


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["json", "text"] = "json"
    file: Path | None = None

    @field_validator("file", mode="before")
    @classmethod
    def parse_file_path(cls, v: Any) -> Path | None:
        """Convert string paths to Path objects."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v)
        if isinstance(v, Path):
            return v
        return None


class PWIConfig(BaseModel):
    """Root configuration model for PWI.

    This is the main configuration object that represents the entire
    pwi.yaml configuration file.
    """

    version: str = "1.0"
    project: ProjectConfig = Field(default_factory=lambda: ProjectConfig())
    llm: LLMConfig = Field(default_factory=lambda: LLMConfig())
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    review: ReviewConfig = Field(
        default_factory=lambda: ReviewConfig(default_mode="cli", timeout_minutes=60)
    )
    artifacts: dict[str, ArtifactConfig] = Field(default_factory=dict)
    logging: LoggingConfig = Field(default_factory=lambda: LoggingConfig())

    @model_validator(mode="after")
    def set_default_agents(self) -> PWIConfig:
        """Ensure all required agents have configuration."""
        required_agents = [
            "data_analyst",
            "data_architect",
            "mapping_engineer",
            "dq_engineer",
            "story_writer",
            "sync_agent",
        ]
        for agent in required_agents:
            if agent not in self.agents:
                self.agents[agent] = AgentConfig(
                    model="balanced", temperature=0.7, max_tokens=4096
                )
        return self

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """Get configuration for a specific agent."""
        return self.agents.get(
            agent_name, AgentConfig(model="balanced", temperature=0.7, max_tokens=4096)
        )

    def get_resolved_model(self, agent_name: str) -> str:
        """Get the resolved model name for an agent."""
        agent_config = self.get_agent_config(agent_name)
        return self.llm.get_model(agent_config.model)

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.project.output_dir.mkdir(parents=True, exist_ok=True)
        self.project.session_dir.mkdir(parents=True, exist_ok=True)
        if self.logging.file:
            self.logging.file.parent.mkdir(parents=True, exist_ok=True)


# Default agent configurations
DEFAULT_AGENT_CONFIGS: dict[str, AgentConfig] = {
    "data_analyst": AgentConfig(model="balanced", temperature=0.7, max_tokens=4096),
    "data_architect": AgentConfig(model="powerful", temperature=0.5, max_tokens=8192),
    "mapping_engineer": AgentConfig(model="balanced", temperature=0.3, max_tokens=4096),
    "dq_engineer": AgentConfig(model="balanced", temperature=0.3, max_tokens=4096),
    "story_writer": AgentConfig(model="balanced", temperature=0.8, max_tokens=8192),
    "sync_agent": AgentConfig(model="fast", temperature=0.2, max_tokens=2048),
}
