"""Base tool definitions and registry for PWI OpenHands agents.

.. deprecated:: 0.8.0
    This module uses the legacy litellm tool format. New tools should
    use the OpenHands SDK pattern with ToolDefinition and register_tool.

    Migration guide:
    - Replace `create_tool()` with SDK `ToolDefinition` class
    - Replace `ToolRegistry` with SDK `register_tool()` function
    - Replace `ChatCompletionToolParam` with `Action` and `Observation` schemas

    See `pwi/openhands/tools/duckdb_tool.py` for the SDK pattern example.

This module provides the foundation for custom tool definitions using
the litellm ChatCompletionToolParam format.
"""

from __future__ import annotations

import warnings
from typing import Any, Callable

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.base")

# Emit deprecation warning when module is imported
warnings.warn(
    "pwi.openhands.tools.base is deprecated. Use OpenHands SDK ToolDefinition pattern instead. "
    "See docs/OPENHANDS_SDK_REFERENCE.md for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)


class ToolRegistry:
    """Registry for custom PWI tools.

    This class manages tool definitions and their executor functions,
    allowing agents to discover and use tools dynamically.
    """

    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, ChatCompletionToolParam] = {}
        self._executors: dict[str, Callable[..., Any]] = {}

    def register(
        self,
        tool: ChatCompletionToolParam,
        executor: Callable[..., Any],
    ) -> None:
        """Register a tool with its executor function.

        Args:
            tool: Tool definition in ChatCompletionToolParam format.
            executor: Function to execute when tool is called.
        """
        tool_name = tool["function"]["name"]
        self._tools[tool_name] = tool
        self._executors[tool_name] = executor
        logger.debug(f"Registered tool: {tool_name}")

    def get_tool(self, name: str) -> ChatCompletionToolParam | None:
        """Get a tool definition by name.

        Args:
            name: Tool name.

        Returns:
            Tool definition or None if not found.
        """
        return self._tools.get(name)

    def get_executor(self, name: str) -> Callable[..., Any] | None:
        """Get a tool executor by name.

        Args:
            name: Tool name.

        Returns:
            Executor function or None if not found.
        """
        return self._executors.get(name)

    def get_tools(self, names: list[str] | None = None) -> list[ChatCompletionToolParam]:
        """Get multiple tool definitions.

        Args:
            names: List of tool names to get. If None, returns all tools.

        Returns:
            List of tool definitions.
        """
        if names is None:
            return list(self._tools.values())
        return [self._tools[n] for n in names if n in self._tools]

    def execute(self, name: str, **kwargs: Any) -> Any:
        """Execute a tool by name.

        Args:
            name: Tool name.
            **kwargs: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            ValueError: If tool is not found.
        """
        executor = self._executors.get(name)
        if executor is None:
            raise ValueError(f"Tool not found: {name}")
        logger.debug(f"Executing tool: {name}")
        return executor(**kwargs)

    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())


def create_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    required: list[str] | None = None,
) -> ChatCompletionToolParam:
    """Factory function to create a tool definition.

    Args:
        name: Tool name (snake_case).
        description: Description of what the tool does.
        parameters: Dictionary of parameter definitions.
        required: List of required parameter names.

    Returns:
        ChatCompletionToolParam tool definition.
    """
    return ChatCompletionToolParam(
        type="function",
        function=ChatCompletionToolParamFunctionChunk(
            name=name,
            description=description,
            parameters={
                "type": "object",
                "properties": parameters,
                "required": required or [],
            },
        ),
    )


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


def register_tool(
    tool: ChatCompletionToolParam,
    executor: Callable[..., Any],
) -> None:
    """Register a tool in the global registry.

    Args:
        tool: Tool definition.
        executor: Tool executor function.
    """
    _registry.register(tool, executor)
