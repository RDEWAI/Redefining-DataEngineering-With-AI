"""Ollama LLM provider implementation.

.. deprecated::
    This module is deprecated and will be removed in Phase 7.
    Use UnifiedLLMClient instead, which provides the same functionality
    with a simpler interface and support for multiple providers.

    Migration example:
        # Old (deprecated):
        from src.llm import OllamaProvider
        provider = OllamaProvider(base_url="http://localhost:11434")
        response = provider.generate([Message(role="user", content="Hello")])

        # New (recommended):
        from src.llm import UnifiedLLMClient
        client = UnifiedLLMClient.from_env()  # or
        client = UnifiedLLMClient(
            base_url="http://localhost:11434/v1",
            model="llama3.2"
        )
        response = client.generate([Message(role="user", content="Hello")])

This module implements the LLMProvider interface for local Ollama server,
enabling the use of local LLM models like Llama, Mistral, and others.
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


class OllamaProvider(LLMProvider):
    """Ollama API provider for local LLM access.

    Uses the Ollama API to access locally running LLM models.

    Args:
        base_url: Ollama server URL (or set OLLAMA_HOST env var)
        default_model: Default model to use (default: llama3.2)

    Example:
        >>> provider = OllamaProvider(base_url="http://localhost:11434")
        >>> response = provider.generate(
        ...     messages=[Message(role="user", content="Hello!")],
        ...     model="llama3.2"
        ... )
    """

    DEFAULT_MODEL = "llama3.2"
    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
    ) -> None:
        """Initialize Ollama provider.

        Args:
            base_url: Ollama server URL (defaults to OLLAMA_HOST or localhost:11434)
            default_model: Default model (defaults to llama3.2)
        """
        # Get base URL from parameter, env var, or default
        env_url = os.getenv("OLLAMA_HOST")
        self._base_url: str = base_url or env_url or self.DEFAULT_BASE_URL
        self._default_model = default_model or self.DEFAULT_MODEL

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Content-Type": "application/json"},
            timeout=120.0,  # Longer timeout for local models
        )

    @property
    def default_model(self) -> str:
        """Get the default model."""
        return self._default_model

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "ollama"

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert Message objects to Ollama API format."""
        converted = []
        for msg in messages:
            m: dict[str, Any] = {"role": msg.role}
            if msg.content:
                m["content"] = msg.content
            converted.append(m)
        return converted

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert ToolDefinition objects to Ollama API format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def _parse_tool_calls(self, raw_calls: list[dict[str, Any]]) -> list[ToolCall]:
        """Parse tool calls from API response."""
        tool_calls: list[ToolCall] = []
        for call in raw_calls:
            function = call.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=call.get("id", f"call_{len(tool_calls)}"),
                    name=function.get("name", ""),
                    arguments=(
                        json.dumps(function.get("arguments", {}))
                        if isinstance(function.get("arguments"), dict)
                        else function.get("arguments", "{}")
                    ),
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
        """Generate a response from Ollama.

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
            "stream": False,
            "options": {"temperature": temperature},
        }

        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        if tools:
            payload["tools"] = self._convert_tools(tools)

        response = self._client.post("/api/chat", json=payload)
        response.raise_for_status()

        data = response.json()
        message = data.get("message", {})

        # Parse tool calls if present
        tool_calls: list[ToolCall] = []
        if "tool_calls" in message:
            tool_calls = self._parse_tool_calls(message["tool_calls"])

        # Calculate token usage from response
        usage = {}
        if "prompt_eval_count" in data:
            usage["prompt_tokens"] = data["prompt_eval_count"]
        if "eval_count" in data:
            usage["completion_tokens"] = data["eval_count"]
        usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=data.get("done_reason", "stop"),
            usage=usage,
            model=data.get("model", model),
        )

    def stream_generate(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Generate a streaming response from Ollama.

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
            "stream": True,
            "options": {"temperature": temperature},
        }

        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    message = data.get("message", {})
                    content = message.get("content", "")
                    if content:
                        yield content

                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

    def count_tokens(
        self,
        messages: list[Message],
        model: str | None = None,
    ) -> int:
        """Estimate token count for messages.

        Uses a simple heuristic since Ollama doesn't provide token counting API.
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

        # Rough estimate: ~4 characters per token
        return total_chars // 4

    def list_models(self) -> list[str]:
        """List available models on the Ollama server.

        Returns:
            List of model names
        """
        response = self._client.get("/api/tags")
        response.raise_for_status()

        data = response.json()
        models = data.get("models", [])
        return [m.get("name", "") for m in models]

    def check_connection(self) -> bool:
        """Check if Ollama server is accessible.

        Returns:
            True if server is accessible, False otherwise
        """
        try:
            response = self._client.get("/api/tags")
            return bool(response.status_code == 200)
        except httpx.RequestError:
            return False

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "OllamaProvider":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()
