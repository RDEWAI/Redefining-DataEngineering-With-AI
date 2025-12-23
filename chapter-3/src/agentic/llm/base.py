"""Abstract base class for LLM providers.

This module defines the interface that all LLM providers must implement.
It supports text generation, streaming, and token counting.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A message in a conversation.

    Attributes:
        role: Message role (system, user, assistant, tool)
        content: Message content (text or tool results)
        name: Optional name for tool messages
        tool_call_id: ID for tool result messages
        tool_calls: List of tool calls (for assistant messages)
    """

    role: str
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for API calls."""
        msg: dict[str, Any] = {"role": self.role}

        if self.content is not None:
            msg["content"] = self.content

        if self.name is not None:
            msg["name"] = self.name

        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id

        if self.tool_calls is not None:
            msg["tool_calls"] = self.tool_calls

        return msg


@dataclass
class ToolDefinition:
    """Definition of a tool for LLM function calling.

    Attributes:
        name: Tool name
        description: Tool description
        parameters: JSON Schema for parameters
    """

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCall:
    """A tool call from the LLM.

    Attributes:
        id: Unique identifier for this call
        name: Name of the tool to call
        arguments: Arguments as JSON string
    """

    id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    """Response from an LLM generation.

    Attributes:
        content: Text content of the response
        tool_calls: List of tool calls (if any)
        finish_reason: Reason generation stopped
        usage: Token usage statistics
        model: Model used for generation
    """

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class TokenUsage:
    """Token usage statistics.

    Attributes:
        prompt_tokens: Tokens in the prompt
        completion_tokens: Tokens in the completion
        total_tokens: Total tokens used
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Subclasses must implement generate(), stream_generate(), and count_tokens()
    methods. The interface supports both synchronous and asynchronous usage.

    Example:
        >>> provider = OpenRouterProvider(api_key="...")
        >>> response = provider.generate(messages=[Message(role="user", content="Hello")])
        >>> print(response.content)
    """

    @abstractmethod
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
            model: Model to use (defaults to provider's default)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            tools: Available tools for function calling
            tool_choice: Tool selection mode (auto, none, required)

        Returns:
            LLMResponse with content and/or tool calls
        """
        pass

    @abstractmethod
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
            model: Model to use (defaults to provider's default)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        pass

    @abstractmethod
    def count_tokens(
        self,
        messages: list[Message],
        model: str | None = None,
    ) -> int:
        """Count tokens in messages.

        Args:
            messages: Messages to count tokens for
            model: Model to use for tokenization

        Returns:
            Estimated token count
        """
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass
