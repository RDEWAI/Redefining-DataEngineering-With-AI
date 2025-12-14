"""LLM provider abstraction layer.

This package provides:
- LLMProvider: Abstract base class for LLM providers
- OpenRouterProvider: OpenRouter API client
- OllamaProvider: Local Ollama client

Example:
    >>> from src.llm import OpenRouterProvider, Message
    >>> provider = OpenRouterProvider()
    >>> response = provider.generate([Message(role="user", content="Hello")])
"""

from .base import (
    LLMProvider,
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from .ollama_client import OllamaProvider
from .openrouter_client import OpenRouterProvider

__all__ = [
    # Base classes
    "LLMProvider",
    "LLMResponse",
    "Message",
    "ToolCall",
    "ToolDefinition",
    "TokenUsage",
    # Providers
    "OpenRouterProvider",
    "OllamaProvider",
]


def get_provider(provider_name: str = "openrouter", **kwargs) -> LLMProvider:
    """Factory function to get an LLM provider.

    Args:
        provider_name: Provider name ("openrouter" or "ollama")
        **kwargs: Additional arguments passed to the provider

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider_name is not recognized

    Example:
        >>> provider = get_provider("openrouter", api_key="sk-...")
        >>> provider = get_provider("ollama", base_url="http://localhost:11434")
    """
    providers = {
        "openrouter": OpenRouterProvider,
        "ollama": OllamaProvider,
    }

    if provider_name not in providers:
        valid = ", ".join(providers.keys())
        raise ValueError(f"Unknown provider: {provider_name}. Valid options: {valid}")

    return providers[provider_name](**kwargs)
