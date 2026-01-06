"""OpenHands runtime setup for PWI.

This module provides runtime initialization and management for
OpenHands agents in the PWI framework.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from pwi.openhands.config import OpenHandsConfig, OpenHandsRuntimeConfig
from pwi.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("openhands.runtime")


class PWIRuntime:
    """Runtime manager for PWI OpenHands integration.

    This class manages the OpenHands runtime lifecycle, including
    initialization, execution, and cleanup.
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
        self._runtime = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the OpenHands runtime.

        This sets up the runtime environment based on configuration.
        For local runtime, this is minimal setup.
        For Docker runtime, this creates the container.
        """
        if self._initialized:
            logger.debug("Runtime already initialized")
            return

        logger.info(
            "Initializing OpenHands runtime",
            extra={
                "runtime_type": self.config.runtime.runtime_type,
                "workspace": str(self.workspace_path),
            },
        )

        # Ensure workspace directory exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)

        if self.config.runtime.runtime_type == "docker":
            await self._initialize_docker_runtime()
        else:
            await self._initialize_local_runtime()

        self._initialized = True
        logger.info("OpenHands runtime initialized successfully")

    async def _initialize_local_runtime(self) -> None:
        """Initialize local runtime (no sandboxing)."""
        logger.debug("Using local runtime (no Docker sandbox)")
        # Local runtime doesn't need special initialization
        # Agent actions will execute directly on the host

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
        if self._runtime is not None:
            logger.info("Cleaning up OpenHands runtime")
            try:
                await self._runtime.close()
            except Exception as e:
                logger.warning(f"Error during runtime cleanup: {e}")
            self._runtime = None
        self._initialized = False

    async def __aenter__(self) -> PWIRuntime:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.cleanup()


def create_runtime(config: OpenHandsConfig | None = None) -> PWIRuntime:
    """Factory function to create a PWI runtime.

    Args:
        config: Optional OpenHands configuration. Uses defaults if not provided.

    Returns:
        Configured PWIRuntime instance.
    """
    if config is None:
        config = OpenHandsConfig.from_env()
    return PWIRuntime(config)
