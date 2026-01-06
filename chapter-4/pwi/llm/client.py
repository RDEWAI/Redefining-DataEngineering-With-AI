"""LLM client wrapper for Planning with Intent.

This module provides an OpenAI-compatible client wrapper that works
with OpenRouter and other API-compatible providers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    pass

from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletionMessageParam

from pwi.utils.logging import get_logger

logger = get_logger("llm.client")


@dataclass
class CompletionResponse:
    """Response from a completion request."""

    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str


@dataclass
class Message:
    """A message in a conversation."""

    role: str  # system, user, assistant
    content: str


class LLMClientError(Exception):
    """Base exception for LLM client errors."""


class LLMRateLimitError(LLMClientError):
    """Raised when rate limited by the API."""


class LLMAuthenticationError(LLMClientError):
    """Raised when authentication fails."""


class LLMClient:
    """OpenAI-compatible LLM client.

    This client works with OpenRouter, OpenAI, Azure OpenAI, and
    any other provider that implements the OpenAI API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        default_model: str = "anthropic/claude-3-5-sonnet",
        timeout: float = 120.0,
        max_retries: int = 3,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the LLM client.

        Args:
            api_key: API key for authentication.
            base_url: Base URL for the API endpoint.
            default_model: Default model to use for completions.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            extra_headers: Additional headers to include in requests.
        """
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries

        # Build headers
        headers = extra_headers or {}
        # OpenRouter-specific headers
        if "openrouter.ai" in base_url:
            headers.setdefault("HTTP-Referer", "https://github.com/pwi")
            headers.setdefault("X-Title", "Planning with Intent")

        # Initialize sync and async clients
        self._sync_client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=headers,
        )

        self._async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=headers,
        )

    def _build_messages(
        self,
        system_prompt: str | None,
        user_message: str,
        conversation_history: list[Message] | None = None,
    ) -> list[ChatCompletionMessageParam]:
        """Build the messages array for the API request."""
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if conversation_history:
            for msg in conversation_history:
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})

        return cast(list[ChatCompletionMessageParam], messages)

    def _parse_response(self, response: Any) -> CompletionResponse:
        """Parse the API response into a CompletionResponse."""
        choice = response.choices[0]
        usage = response.usage

        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            finish_reason=choice.finish_reason or "unknown",
        )

    def complete(
        self,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        conversation_history: list[Message] | None = None,
    ) -> CompletionResponse:
        """Send a completion request (synchronous).

        Args:
            user_message: The user's message/prompt.
            system_prompt: Optional system prompt.
            model: Model to use (defaults to client's default_model).
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens in response.
            conversation_history: Optional prior conversation messages.

        Returns:
            CompletionResponse with the model's response.

        Raises:
            LLMClientError: If the request fails.
        """
        messages = self._build_messages(system_prompt, user_message, conversation_history)
        model = model or self.default_model

        try:
            response = self._sync_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return self._parse_response(response)

        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise LLMRateLimitError(f"Rate limited: {e}") from e
            if "authentication" in error_msg or "401" in error_msg:
                raise LLMAuthenticationError(f"Authentication failed: {e}") from e
            raise LLMClientError(f"LLM request failed: {e}") from e

    async def acomplete(
        self,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        conversation_history: list[Message] | None = None,
    ) -> CompletionResponse:
        """Send a completion request (asynchronous).

        Args:
            user_message: The user's message/prompt.
            system_prompt: Optional system prompt.
            model: Model to use (defaults to client's default_model).
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens in response.
            conversation_history: Optional prior conversation messages.

        Returns:
            CompletionResponse with the model's response.

        Raises:
            LLMClientError: If the request fails.
        """
        messages = self._build_messages(system_prompt, user_message, conversation_history)
        model = model or self.default_model

        try:
            response = await self._async_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return self._parse_response(response)

        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise LLMRateLimitError(f"Rate limited: {e}") from e
            if "authentication" in error_msg or "401" in error_msg:
                raise LLMAuthenticationError(f"Authentication failed: {e}") from e
            raise LLMClientError(f"LLM request failed: {e}") from e

    async def acomplete_with_retry(
        self,
        user_message: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        conversation_history: list[Message] | None = None,
        max_retries: int | None = None,
        initial_delay: float = 1.0,
    ) -> CompletionResponse:
        """Send a completion request with exponential backoff retry.

        Args:
            user_message: The user's message/prompt.
            system_prompt: Optional system prompt.
            model: Model to use.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            conversation_history: Optional prior conversation messages.
            max_retries: Override client's max_retries.
            initial_delay: Initial delay between retries in seconds.

        Returns:
            CompletionResponse with the model's response.

        Raises:
            LLMClientError: If all retries fail.
        """
        retries = max_retries if max_retries is not None else self.max_retries
        delay = initial_delay
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                return await self.acomplete(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    conversation_history=conversation_history,
                )
            except LLMRateLimitError as e:
                last_error = e
                if attempt < retries:
                    logger.warning(
                        f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{retries})"
                    )
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
            except LLMClientError:
                raise

        raise LLMClientError(f"All {retries + 1} attempts failed: {last_error}")

    def close(self) -> None:
        """Close the client connections."""
        self._sync_client.close()

    async def aclose(self) -> None:
        """Close the async client connections."""
        await self._async_client.close()

    async def acomplete_with_tools(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Send a completion request with tool support (for OpenHands agents).

        This method supports the full OpenAI Chat Completions API including
        function/tool calling, which is required for OpenHands-based agents.

        Args:
            messages: List of message dictionaries with role and content.
            model: Model to use (defaults to client's default_model).
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens in response.
            tools: Optional list of tool definitions for function calling.

        Returns:
            Raw OpenAI ChatCompletion response object (for tool call parsing).

        Raises:
            LLMClientError: If the request fails.
        """
        model = model or self.default_model

        try:
            # Build request kwargs
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Add tools if provided
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await self._async_client.chat.completions.create(**kwargs)
            return response

        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise LLMRateLimitError(f"Rate limited: {e}") from e
            if "authentication" in error_msg or "401" in error_msg:
                raise LLMAuthenticationError(f"Authentication failed: {e}") from e
            raise LLMClientError(f"LLM request failed: {e}") from e
