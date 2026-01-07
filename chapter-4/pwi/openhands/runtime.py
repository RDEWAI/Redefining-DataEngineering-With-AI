"""OpenHands runtime setup for PWI.

This module provides runtime initialization and management for
OpenHands agents in the PWI framework.

Supports three runtime modes:
- "sdk": Uses OpenHands SDK Conversation class (recommended)
- "local": Uses local execution without sandboxing
- "docker": Uses Docker-based sandboxed runtime
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pwi.openhands.config import OpenHandsConfig, OpenHandsRuntimeConfig
from pwi.utils.logging import get_logger

if TYPE_CHECKING:
    from openhands.sdk import Agent, Conversation

logger = get_logger("openhands.runtime")


class PWIRuntime:
    """Runtime manager for PWI OpenHands integration.

    This class manages the OpenHands runtime lifecycle, including
    initialization, execution, and cleanup.

    Supports three modes:
    - SDK: Uses OpenHands SDK Conversation for agent execution
    - Local: Executes commands directly on host (no sandbox)
    - Docker: Uses Docker container for sandboxed execution
    """

    def __init__(
        self,
        config: OpenHandsConfig,
        workspace_path: Path | None = None,
    ) -> None:
        """Initialize the PWI runtime.

        Args:
            config: OpenHands configuration.
            workspace_path: Override workspace path.
        """
        self.config = config
        self.workspace_path = workspace_path or config.runtime.workspace_base
        self._runtime = None  # Docker runtime instance
        self._conversation: Conversation | None = None  # SDK conversation
        self._agent: Agent | None = None  # SDK agent
        self._initialized = False
        self._runtime_type = config.runtime.runtime_type

    async def initialize(self) -> None:
        """Initialize the OpenHands runtime.

        This sets up the runtime environment based on configuration.
        For SDK runtime, this prepares for Conversation use.
        For local runtime, this is minimal setup.
        For Docker runtime, this creates the container.
        """
        if self._initialized:
            logger.debug("Runtime already initialized")
            return

        logger.info(
            "Initializing OpenHands runtime",
            extra={
                "runtime_type": self._runtime_type,
                "workspace": str(self.workspace_path),
            },
        )

        # Ensure workspace directory exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)

        if self._runtime_type == "sdk":
            await self._initialize_sdk_runtime()
        elif self._runtime_type == "docker":
            await self._initialize_docker_runtime()
        else:
            await self._initialize_local_runtime()

        self._initialized = True
        logger.info(f"OpenHands runtime initialized successfully (type: {self._runtime_type})")

    async def _initialize_local_runtime(self) -> None:
        """Initialize local runtime (no sandboxing)."""
        logger.debug("Using local runtime (no Docker sandbox)")
        # Local runtime doesn't need special initialization
        # Agent actions will execute directly on the host

    async def _initialize_sdk_runtime(self) -> None:
        """Initialize SDK-based runtime using OpenHands Conversation.

        This is the recommended runtime that uses the official SDK
        pattern with Agent and Conversation classes.
        """
        logger.debug("Initializing SDK runtime")
        try:
            from pwi.openhands.agents.factory import create_llm

            # Create default LLM from config
            llm_config = {
                "model": self.config.llm.model,
                "temperature": self.config.llm.temperature,
                "max_tokens": self.config.llm.max_tokens,
            }
            if self.config.llm.api_key:
                llm_config["api_key"] = self.config.llm.api_key
            if self.config.llm.base_url:
                llm_config["base_url"] = self.config.llm.base_url

            # Store LLM config for later agent creation
            self._llm_config = llm_config
            logger.debug("SDK runtime prepared with LLM config")

        except ImportError as e:
            logger.warning(
                f"SDK runtime initialization failed: {e}. Falling back to local runtime."
            )
            self._runtime_type = "local"
            await self._initialize_local_runtime()

    async def _initialize_docker_runtime(self) -> None:
        """Initialize Docker-based sandboxed runtime."""
        logger.debug("Initializing Docker runtime")
        try:
            # Import OpenHands runtime components
            # Note: These imports may fail if OpenHands is not installed
            from openhands.runtime.client import DockerRuntime

            sandbox_config = {
                "timeout": self.config.runtime.sandbox_timeout,
                "workspace_base": str(self.workspace_path),
            }

            self._runtime = DockerRuntime(
                config=sandbox_config,
                sid=f"pwi-{id(self)}",
            )
            await self._runtime.connect()

        except ImportError as e:
            logger.warning(
                f"Docker runtime not available: {e}. Falling back to local runtime."
            )
            await self._initialize_local_runtime()
        except Exception as e:
            logger.error(f"Failed to initialize Docker runtime: {e}")
            raise

    async def execute_action(self, action: dict) -> dict:
        """Execute an action in the runtime.

        Args:
            action: Action dictionary with type and parameters.

        Returns:
            Observation dictionary with results.
        """
        if not self._initialized:
            await self.initialize()

        action_type = action.get("type", "unknown")
        logger.debug(f"Executing action: {action_type}")

        if self._runtime is not None:
            # Use Docker runtime
            return await self._execute_docker_action(action)
        else:
            # Use local runtime
            return await self._execute_local_action(action)

    async def _execute_docker_action(self, action: dict) -> dict:
        """Execute action in Docker runtime."""
        from openhands.events.action import CmdRunAction, FileReadAction

        action_type = action.get("type")

        if action_type == "run":
            cmd_action = CmdRunAction(command=action.get("command", ""))
            observation = await self._runtime.run_action(cmd_action)
            return {
                "type": "cmd_output",
                "content": observation.content,
                "exit_code": observation.exit_code,
            }

        elif action_type == "read":
            read_action = FileReadAction(path=action.get("path", ""))
            observation = await self._runtime.run_action(read_action)
            return {
                "type": "file_content",
                "content": observation.content,
            }

        else:
            return {"type": "error", "content": f"Unknown action type: {action_type}"}

    async def _execute_local_action(self, action: dict) -> dict:
        """Execute action locally (no sandbox)."""
        action_type = action.get("type")

        if action_type == "run":
            command = action.get("command", "")
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.workspace_path),
                )
                stdout, stderr = await process.communicate()
                return {
                    "type": "cmd_output",
                    "content": stdout.decode() + stderr.decode(),
                    "exit_code": process.returncode,
                }
            except Exception as e:
                return {
                    "type": "error",
                    "content": str(e),
                    "exit_code": 1,
                }

        elif action_type == "read":
            file_path = Path(action.get("path", ""))
            if not file_path.is_absolute():
                file_path = self.workspace_path / file_path
            try:
                content = file_path.read_text()
                return {
                    "type": "file_content",
                    "content": content,
                }
            except Exception as e:
                return {
                    "type": "error",
                    "content": str(e),
                }

        else:
            return {"type": "error", "content": f"Unknown action type: {action_type}"}

    async def cleanup(self) -> None:
        """Clean up runtime resources."""
        if self._conversation is not None:
            logger.info("Cleaning up SDK conversation")
            try:
                self._conversation.close()
            except Exception as e:
                logger.warning(f"Error during conversation cleanup: {e}")
            self._conversation = None
            self._agent = None

        if self._runtime is not None:
            logger.info("Cleaning up Docker runtime")
            try:
                await self._runtime.close()
            except Exception as e:
                logger.warning(f"Error during runtime cleanup: {e}")
            self._runtime = None

        self._initialized = False

    # =========================================================================
    # SDK Runtime Methods
    # =========================================================================

    def create_conversation(
        self,
        agent_type: str,
        callbacks: list | None = None,
    ) -> "Conversation":
        """Create an SDK Conversation for the specified agent type.

        This is the recommended way to run agents using the OpenHands SDK.

        Args:
            agent_type: Type of PWI agent (e.g., 'data_analyst', 'data_architect').
            callbacks: Optional list of event callback functions.

        Returns:
            Configured Conversation instance.

        Raises:
            RuntimeError: If runtime is not SDK type or not initialized.
        """
        if self._runtime_type != "sdk":
            raise RuntimeError(
                f"create_conversation requires SDK runtime, but got {self._runtime_type}"
            )

        if not self._initialized:
            raise RuntimeError("Runtime not initialized. Call initialize() first.")

        from pwi.openhands.agents.factory import (
            create_pwi_agent,
            create_pwi_conversation,
        )

        # Create agent for this type
        self._agent = create_pwi_agent(
            agent_type=agent_type,
            llm_config=getattr(self, "_llm_config", None),
        )

        # Create conversation
        self._conversation = create_pwi_conversation(
            agent=self._agent,
            workspace=self.workspace_path,
            callbacks=callbacks,
        )

        logger.info(
            f"Created SDK conversation for {agent_type} agent",
            extra={"workspace": str(self.workspace_path)},
        )

        return self._conversation

    async def run_agent_task(
        self,
        agent_type: str,
        message: str,
        context: dict[str, str] | None = None,
        callbacks: list | None = None,
    ) -> str:
        """Run a complete agent task using SDK Conversation.

        This is a convenience method that creates a conversation,
        sends the message, runs the agent, and returns the result.

        Args:
            agent_type: Type of PWI agent.
            message: Task message/prompt.
            context: Optional context from previous agents.
            callbacks: Optional event callbacks.

        Returns:
            Agent's response or "Task completed".
        """
        if not self._initialized:
            await self.initialize()

        if self._runtime_type == "sdk":
            conversation = self.create_conversation(agent_type, callbacks)

            # Build message with context
            full_message = message
            if context:
                context_str = "\n\n".join(
                    f"## {key.upper()}\n{value}" for key, value in context.items()
                )
                full_message = f"{message}\n\n## Context from Previous Agents:\n{context_str}"

            conversation.send_message(full_message)
            conversation.run()

            return "Task completed"  # TODO: Extract actual content
        else:
            # Fallback for non-SDK runtimes
            logger.warning("run_agent_task called with non-SDK runtime, using legacy path")
            return await self._run_legacy_agent_task(agent_type, message, context)

    async def _run_legacy_agent_task(
        self,
        agent_type: str,
        message: str,
        context: dict[str, str] | None = None,
    ) -> str:
        """Run agent task using legacy local/docker runtime."""
        # This is a placeholder for legacy runtime support
        # The actual implementation would use the execute_action methods
        logger.debug(f"Running legacy agent task: {agent_type}")
        return "Legacy task execution not fully implemented"

    async def __aenter__(self) -> PWIRuntime:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.cleanup()


def create_runtime(
    config: OpenHandsConfig | None = None,
    runtime_type: str | None = None,
    workspace_path: Path | None = None,
) -> PWIRuntime:
    """Factory function to create a PWI runtime.

    Args:
        config: Optional OpenHands configuration. Uses defaults if not provided.
        runtime_type: Override runtime type ("sdk", "local", "docker").
        workspace_path: Override workspace path.

    Returns:
        Configured PWIRuntime instance.

    Example:
        # Create SDK runtime (recommended)
        runtime = create_runtime(runtime_type="sdk")

        # Create with custom config
        config = OpenHandsConfig.from_env()
        runtime = create_runtime(config, workspace_path=Path("/my/workspace"))

        # Use runtime
        async with runtime:
            conversation = runtime.create_conversation("data_analyst")
            conversation.send_message("Analyze the data")
            conversation.run()
    """
    if config is None:
        config = OpenHandsConfig.from_env()

    # Override runtime type if specified
    if runtime_type is not None:
        if runtime_type not in ("sdk", "local", "docker"):
            raise ValueError(f"Invalid runtime_type: {runtime_type}")
        config.runtime.runtime_type = runtime_type  # type: ignore[assignment]

    return PWIRuntime(config, workspace_path=workspace_path)
