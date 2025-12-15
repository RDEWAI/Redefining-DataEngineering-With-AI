"""OpenRouter LLM provider implementation.

.. deprecated::
    This module is deprecated and will be removed in Phase 7.
    Use UnifiedLLMClient instead, which provides the same functionality
    with a simpler interface and support for multiple providers.

    Migration example:
        # Old (deprecated):
        from src.llm import OpenRouterProvider
        provider = OpenRouterProvider(api_key="sk-...")
        response = provider.generate([Message(role="user", content="Hello")])

        # New (recommended):
        from src.llm import UnifiedLLMClient
        client = UnifiedLLMClient.from_env()  # or
        client = UnifiedLLMClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-...",
            model="openai/gpt-4o-mini"
        )
        response = client.generate([Message(role="user", content="Hello")])

This module implements the LLMProvider interface for the OpenRouter API,
which provides access to various LLM models through a unified interface.
"""

import json
import os
from collections.abc import Iterator
from typing import Any

import httpx

from .base import (
    LLMProvider,
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider for LLM access.

    Uses the OpenRouter API to access various LLM models including
    Claude, GPT-4, Llama, and others.

    Args:
        api_key: OpenRouter API key (or set OPENROUTER_API_KEY env var)
        default_model: Default model to use (default: anthropic/claude-3-haiku)
        base_url: API base URL (default: https://openrouter.ai/api/v1)

    Example:
        >>> provider = OpenRouterProvider(api_key="sk-...")
        >>> response = provider.generate(
        ...     messages=[Message(role="user", content="Hello!")],
        ...     model="anthropic/claude-3-haiku"
        ... )
    """

    DEFAULT_MODEL = "anthropic/claude-3-haiku"
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize OpenRouter provider.

        Args:
            api_key: API key (defaults to OPENROUTER_API_KEY env var)
            default_model: Default model (defaults to claude-3-haiku)
            base_url: API base URL

        Raises:
            ValueError: If no API key is provided or found in environment
        """
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenRouter API key is required. "
                "Set OPENROUTER_API_KEY environment variable or pass api_key parameter."
            )

        self._default_model = default_model or self.DEFAULT_MODEL
        self._base_url = base_url or self.BASE_URL

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/rdewai",  # For OpenRouter attribution
                "X-Title": "Chapter 3 AI Engineering",
            },
            timeout=60.0,
        )

    @property
    def default_model(self) -> str:
        """Get the default model."""
        return self._default_model

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "openrouter"

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert Message objects to API format."""
        return [msg.to_dict() for msg in messages]

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert ToolDefinition objects to API format."""
        return [tool.to_openai_format() for tool in tools]

    def _parse_tool_calls(self, raw_calls: list[dict[str, Any]]) -> list[ToolCall]:
        """Parse tool calls from API response."""
        tool_calls = []
        for call in raw_calls:
            function = call.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=call.get("id", ""),
                    name=function.get("name", ""),
                    arguments=function.get("arguments", "{}"),
                )
            )
        return tool_calls

    def generate(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Generate a response from OpenRouter.

        Args:
            messages: Conversation history
            model: Model to use (defaults to provider's default)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            tools: Available tools for function calling
            tool_choice: Tool selection mode

        Returns:
            LLMResponse with content and/or tool calls

        Raises:
            httpx.HTTPError: On API errors
        """
        model = model or self._default_model

        payload: dict[str, Any] = {
            "model": model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = self._convert_tools(tools)
            if tool_choice:
                payload["tool_choice"] = tool_choice

        response = self._client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Parse tool calls if present
        tool_calls: list[ToolCall] = []
        if "tool_calls" in message:
            tool_calls = self._parse_tool_calls(message["tool_calls"])

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", ""),
            usage=data.get("usage", {}),
            model=data.get("model", model),
        )

    def stream_generate(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Generate a streaming response from OpenRouter.

        Args:
            messages: Conversation history
            model: Model to use (defaults to provider's default)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        model = model or self._default_model

        payload: dict[str, Any] = {
            "model": model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        with self._client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line or line == "data: [DONE]":
                    continue

                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def count_tokens(
        self,
        messages: list[Message],
        model: str | None = None,
    ) -> int:
        """Estimate token count for messages.

        Uses a simple heuristic since OpenRouter doesn't provide token counting.
        Approximately 4 characters per token for English text.

        Args:
            messages: Messages to count tokens for
            model: Model (not used for estimation)

        Returns:
            Estimated token count
        """
        total_chars = 0
        for msg in messages:
            if msg.content:
                total_chars += len(msg.content)
            if msg.name:
                total_chars += len(msg.name)
            if msg.tool_calls:
                total_chars += len(json.dumps(msg.tool_calls))

        # Rough estimate: ~4 characters per token
        return total_chars // 4

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "OpenRouterProvider":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()
