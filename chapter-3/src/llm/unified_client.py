"""Unified LLM client using OpenAI SDK.

This module provides a unified LLM client that works with multiple providers
(OpenRouter, Ollama, OpenAI) through the OpenAI SDK's custom base_url feature.

Example:
    >>> from src.llm.unified_client import UnifiedLLMClient
    >>> client = UnifiedLLMClient.from_env()
    >>> response = client.generate([Message(role="user", content="Hello!")])
    >>> print(response.content)
    >>> print(response.usage)  # {'prompt_tokens': 5, 'completion_tokens': 10, ...}
"""

import json
import os
from collections.abc import Iterator
from enum import Enum
from typing import Any

from openai import APIError, AuthenticationError, OpenAI

from .base import (
    LLMProvider,
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)


class ProviderType(Enum):
    """Supported LLM provider types."""

    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    OPENAI = "openai"


# Provider detection patterns for base URLs
PROVIDER_URL_PATTERNS = {
    "openrouter.ai": ProviderType.OPENROUTER,
    "localhost:11434": ProviderType.OLLAMA,
    "127.0.0.1:11434": ProviderType.OLLAMA,
    "api.openai.com": ProviderType.OPENAI,
}


class UnifiedLLMClient(LLMProvider):
    """Unified LLM client supporting OpenRouter, Ollama, and OpenAI.

    Uses the OpenAI SDK with custom base_url to connect to different providers.
    This provides a consistent interface regardless of the underlying provider.

    Args:
        base_url: API endpoint URL (e.g., https://openrouter.ai/api/v1)
        api_key: API key (required for OpenRouter/OpenAI, optional for Ollama)
        model: Model identifier (e.g., openai/gpt-4o-mini, llama3.2)
        enable_usage_tracking: Enable token usage tracking (default: True)

    Example:
        >>> # Initialize with explicit parameters
        >>> client = UnifiedLLMClient(
        ...     base_url="https://openrouter.ai/api/v1",
        ...     api_key="sk-or-v1-...",
        ...     model="openai/gpt-4o-mini"
        ... )

        >>> # Or load from environment
        >>> client = UnifiedLLMClient.from_env()
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        model: str = "openai/gpt-4o-mini",
        enable_usage_tracking: bool = True,
    ) -> None:
        """Initialize the unified LLM client.

        Args:
            base_url: API endpoint URL
            api_key: API key (required for OpenRouter/OpenAI, optional for Ollama)
            model: Model identifier
            enable_usage_tracking: Enable token usage tracking

        Raises:
            ValueError: If API key is missing for providers that require it
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._enable_usage_tracking = enable_usage_tracking
        self._provider_type = self._detect_provider(base_url)

        # Validate API key based on provider
        if self._provider_type != ProviderType.OLLAMA and not api_key:
            provider_name = self._provider_type.value.capitalize()
            raise ValueError(
                f"API key is required for {provider_name}. "
                f"Set LLM_API_KEY environment variable or pass api_key parameter. "
                f"For local Ollama, set LLM_BASE_URL to http://localhost:11434/v1"
            )

        # For Ollama, use a dummy key if none provided (Ollama ignores it)
        self._api_key = api_key or "ollama"

        # Initialize OpenAI client with custom base URL
        self._client = OpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=120.0,  # Longer timeout for local models
        )

    @classmethod
    def from_env(cls) -> "UnifiedLLMClient":
        """Create a client from environment variables.

        Environment variables:
            LLM_BASE_URL: API endpoint URL (required)
            LLM_API_KEY: API key (required for OpenRouter/OpenAI)
            LLM_MODEL: Model identifier (default: openai/gpt-4o-mini)
            LLM_ENABLE_USAGE_TRACKING: Enable usage tracking (default: true)

        Returns:
            UnifiedLLMClient instance

        Raises:
            ValueError: If required environment variables are missing

        Example:
            >>> # Set environment variables
            >>> os.environ["LLM_BASE_URL"] = "https://openrouter.ai/api/v1"
            >>> os.environ["LLM_API_KEY"] = "sk-or-v1-..."
            >>> os.environ["LLM_MODEL"] = "openai/gpt-4o-mini"
            >>> client = UnifiedLLMClient.from_env()
        """
        base_url = os.getenv("LLM_BASE_URL")
        if not base_url:
            raise ValueError(
                "LLM_BASE_URL environment variable is required. "
                "Example values:\n"
                "  - OpenRouter: https://openrouter.ai/api/v1\n"
                "  - Ollama: http://localhost:11434/v1\n"
                "  - OpenAI: https://api.openai.com/v1"
            )

        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
        enable_usage = os.getenv("LLM_ENABLE_USAGE_TRACKING", "true").lower() == "true"

        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            enable_usage_tracking=enable_usage,
        )

    def _detect_provider(self, base_url: str) -> ProviderType:
        """Detect provider type from base URL.

        Args:
            base_url: API endpoint URL

        Returns:
            Detected provider type
        """
        url_lower = base_url.lower()
        for pattern, provider in PROVIDER_URL_PATTERNS.items():
            if pattern in url_lower:
                return provider

        # Default to OpenRouter for unknown URLs (compatible with OpenAI SDK)
        return ProviderType.OPENROUTER

    @property
    def default_model(self) -> str:
        """Get the default model."""
        return self._model

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return f"unified-{self._provider_type.value}"

    @property
    def provider_type(self) -> ProviderType:
        """Get the detected provider type."""
        return self._provider_type

    @property
    def base_url(self) -> str:
        """Get the base URL."""
        return self._base_url

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert Message objects to OpenAI API format."""
        return [msg.to_dict() for msg in messages]

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert ToolDefinition objects to OpenAI API format."""
        return [tool.to_openai_format() for tool in tools]

    def _parse_tool_calls(self, raw_calls: list[Any]) -> list[ToolCall]:
        """Parse tool calls from OpenAI SDK response."""
        tool_calls = []
        for call in raw_calls:
            tool_calls.append(
                ToolCall(
                    id=call.id or "",
                    name=call.function.name or "",
                    arguments=call.function.arguments or "{}",
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
        """Generate a response from the LLM.

        Args:
            messages: Conversation history
            model: Model to use (defaults to client's model)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            tools: Available tools for function calling
            tool_choice: Tool selection mode (auto, none, required)

        Returns:
            LLMResponse with content, tool calls, and usage metrics

        Raises:
            openai.APIError: On API errors
            openai.AuthenticationError: On authentication failures
        """
        model = model or self._model

        # Build request parameters
        params: dict[str, Any] = {
            "model": model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
        }

        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        if tools:
            params["tools"] = self._convert_tools(tools)
            if tool_choice:
                params["tool_choice"] = tool_choice

        try:
            response = self._client.chat.completions.create(**params)

            choice = response.choices[0] if response.choices else None
            message = choice.message if choice else None

            # Parse tool calls if present
            tool_calls: list[ToolCall] = []
            if message and message.tool_calls:
                tool_calls = self._parse_tool_calls(message.tool_calls)

            # Extract usage metrics
            usage: dict[str, int] = {}
            if response.usage and self._enable_usage_tracking:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return LLMResponse(
                content=message.content if message else None,
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason if choice else "",
                usage=usage,
                model=response.model,
            )

        except AuthenticationError as e:
            raise ValueError(
                f"Authentication failed for {self._provider_type.value}. "
                f"Please check your API key (LLM_API_KEY). "
                f"Error: {e.message}"
            ) from e
        except APIError as e:
            raise ValueError(
                f"API error from {self._provider_type.value}: {e.message}. "
                f"Please check your configuration (LLM_BASE_URL, LLM_MODEL)."
            ) from e

    def stream_generate(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Generate a streaming response from the LLM.

        Args:
            messages: Conversation history
            model: Model to use (defaults to client's model)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        model = model or self._model

        params: dict[str, Any] = {
            "model": model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        try:
            stream = self._client.chat.completions.create(**params)

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except AuthenticationError as e:
            raise ValueError(
                f"Authentication failed for {self._provider_type.value}. "
                f"Please check your API key. Error: {e.message}"
            ) from e
        except APIError as e:
            raise ValueError(
                f"Streaming API error from {self._provider_type.value}: {e.message}"
            ) from e

    def count_tokens(
        self,
        messages: list[Message],
        model: str | None = None,
    ) -> int:
        """Estimate token count for messages.

        Uses a simple heuristic since token counting requires model-specific
        tokenizers. Approximately 4 characters per token for English text.

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
        """Close the client connection."""
        self._client.close()

    def __enter__(self) -> "UnifiedLLMClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()
