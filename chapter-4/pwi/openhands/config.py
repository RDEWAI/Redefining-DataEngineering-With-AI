"""OpenHands configuration adapter for PWI.

This module adapts the existing PWI configuration to work with
the OpenHands SDK configuration system.

Supports three runtime types:
- "sdk": Uses OpenHands SDK Conversation class (recommended)
- "local": Uses local execution without sandboxing
- "docker": Uses Docker-based sandboxed runtime
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

# Runtime type literal for type safety
RuntimeType = Literal["sdk", "local", "docker"]


class OpenHandsLLMConfig(BaseModel):
    """LLM configuration for OpenHands agents."""

    model: str = Field(
        default="anthropic/claude-3-5-sonnet",
        description="Model identifier (provider/model format for litellm)",
    )
    api_key: str | None = Field(
        default=None,
        description="API key (defaults to LLM_API_KEY env var)",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for API (defaults to LLM_BASE_URL env var)",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for generation",
    )
    max_tokens: int = Field(
        default=4096,
        ge=100,
        le=128000,
        description="Maximum tokens to generate",
    )

    def model_post_init(self, __context: Any) -> None:
        """Set defaults from environment variables."""
        if self.api_key is None:
            self.api_key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY"))
        if self.base_url is None:
            self.base_url = os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL"))


class OpenHandsRuntimeConfig(BaseModel):
    """Runtime configuration for OpenHands agents."""

    runtime_type: RuntimeType = Field(
        default="sdk",
        description="Runtime type: 'sdk' (recommended), 'local', or 'docker'",
    )
    workspace_base: Path = Field(
        default=Path("./workspace"),
        description="Base directory for agent workspace",
    )
    sandbox_timeout: int = Field(
        default=300,
        description="Sandbox timeout in seconds",
    )
    max_iterations: int = Field(
        default=100,
        description="Maximum agent iterations per task",
    )


class OpenHandsAgentConfig(BaseModel):
    """Configuration for a single OpenHands agent."""

    name: str = Field(description="Agent name identifier")
    agent_type: str = Field(
        default="CodeActAgent",
        description="OpenHands agent type to use",
    )
    model: str | None = Field(
        default=None,
        description="Model override for this agent (uses default if None)",
    )
    temperature: float | None = Field(
        default=None,
        description="Temperature override for this agent",
    )
    max_tokens: int | None = Field(
        default=None,
        description="Max tokens override for this agent",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="List of tool names to enable for this agent",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="List of skill/microagent names to enable",
    )


class OpenHandsConfig(BaseModel):
    """Main OpenHands configuration for PWI.

    This configuration adapts PWI settings to OpenHands SDK format.
    """

    llm: OpenHandsLLMConfig = Field(
        default_factory=OpenHandsLLMConfig,
        description="LLM configuration",
    )
    runtime: OpenHandsRuntimeConfig = Field(
        default_factory=OpenHandsRuntimeConfig,
        description="Runtime configuration",
    )
    agents: dict[str, OpenHandsAgentConfig] = Field(
        default_factory=dict,
        description="Per-agent configurations",
    )
    feature_flag_enabled: bool = Field(
        default=False,
        description="Feature flag to enable OpenHands mode",
    )
    microagents_dir: Path = Field(
        default=Path(".openhands/microagents"),
        description="Directory containing skill/microagent definitions",
    )

    @classmethod
    def from_env(cls) -> OpenHandsConfig:
        """Create configuration from environment variables.

        Supported environment variables:
        - USE_OPENHANDS: Enable OpenHands mode (default: false)
        - OPENHANDS_RUNTIME: Runtime type - "sdk", "local", or "docker" (default: sdk)
        - LLM_API_KEY: API key for LLM provider
        - LLM_BASE_URL: Base URL for LLM API
        - LLM_MODEL: Model identifier (default: anthropic/claude-sonnet-4-5-20250929)
        """
        # Get runtime type from env, default to "sdk"
        runtime_type_str = os.getenv("OPENHANDS_RUNTIME", "sdk").lower()
        if runtime_type_str not in ("sdk", "local", "docker"):
            runtime_type_str = "sdk"

        return cls(
            feature_flag_enabled=os.getenv("USE_OPENHANDS", "false").lower() == "true",
            llm=OpenHandsLLMConfig(
                api_key=os.getenv("LLM_API_KEY"),
                base_url=os.getenv("LLM_BASE_URL"),
                model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929"),
            ),
            runtime=OpenHandsRuntimeConfig(
                runtime_type=runtime_type_str,  # type: ignore[arg-type]
            ),
        )

    @classmethod
    def from_pwi_config(cls, pwi_config: Any) -> OpenHandsConfig:
        """Create OpenHands config from existing PWI config.

        Args:
            pwi_config: Existing PWI configuration object.

        Returns:
            OpenHandsConfig adapted from PWI settings.
        """
        # Extract LLM config from PWI
        llm_config = OpenHandsLLMConfig(
            api_key=getattr(pwi_config.llm, "api_key", None),
            base_url=getattr(pwi_config.llm, "base_url", None),
            model=getattr(pwi_config.llm, "default_model", "anthropic/claude-3-5-sonnet"),
        )

        # Create agent configs from PWI agent configs
        agents: dict[str, OpenHandsAgentConfig] = {}
        if hasattr(pwi_config, "agents"):
            for agent_name, agent_cfg in pwi_config.agents.items():
                agents[agent_name] = OpenHandsAgentConfig(
                    name=agent_name,
                    model=getattr(agent_cfg, "model", None),
                    temperature=getattr(agent_cfg, "temperature", None),
                    max_tokens=getattr(agent_cfg, "max_tokens", None),
                )

        return cls(
            llm=llm_config,
            agents=agents,
            feature_flag_enabled=os.getenv("USE_OPENHANDS", "false").lower() == "true",
        )

    def get_agent_config(self, agent_name: str) -> OpenHandsAgentConfig:
        """Get configuration for a specific agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Agent configuration (creates default if not found).
        """
        if agent_name not in self.agents:
            self.agents[agent_name] = OpenHandsAgentConfig(name=agent_name)
        return self.agents[agent_name]
