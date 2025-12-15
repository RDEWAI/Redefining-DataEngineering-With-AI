"""Unit tests for UnifiedLLMClient.

This module tests the unified LLM client that works with multiple providers
(OpenRouter, Ollama, OpenAI) through the OpenAI SDK.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.llm.base import Message, ToolDefinition
from src.llm.unified_client import ProviderType, UnifiedLLMClient


class TestUnifiedLLMClientInitialization:
    """Tests for UnifiedLLMClient initialization."""

    def test_openrouter_initialization(self) -> None:
        """Test initialization with OpenRouter base URL."""
        client = UnifiedLLMClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-v1-test-key",
            model="openai/gpt-4o-mini",
        )

        assert client.provider_type == ProviderType.OPENROUTER
        assert client.default_model == "openai/gpt-4o-mini"
        assert client.base_url == "https://openrouter.ai/api/v1"
        assert client.provider_name == "unified-openrouter"

    def test_ollama_initialization_without_api_key(self) -> None:
        """Test initialization with Ollama (no API key required)."""
        client = UnifiedLLMClient(
            base_url="http://localhost:11434/v1",
            model="llama3.2",
        )

        assert client.provider_type == ProviderType.OLLAMA
        assert client.default_model == "llama3.2"
        assert client.base_url == "http://localhost:11434/v1"
        assert client.provider_name == "unified-ollama"

    def test_ollama_initialization_with_127_address(self) -> None:
        """Test Ollama detection with 127.0.0.1 address."""
        client = UnifiedLLMClient(
            base_url="http://127.0.0.1:11434/v1",
            model="llama3.2",
        )

        assert client.provider_type == ProviderType.OLLAMA

    def test_openai_initialization(self) -> None:
        """Test initialization with OpenAI base URL."""
        client = UnifiedLLMClient(
            base_url="https://api.openai.com/v1",
            api_key="sk-test-key",
            model="gpt-4o-mini",
        )

        assert client.provider_type == ProviderType.OPENAI
        assert client.default_model == "gpt-4o-mini"
        assert client.base_url == "https://api.openai.com/v1"
        assert client.provider_name == "unified-openai"

    def test_trailing_slash_removed_from_base_url(self) -> None:
        """Test that trailing slash is removed from base URL."""
        client = UnifiedLLMClient(
            base_url="https://openrouter.ai/api/v1/",
            api_key="sk-or-v1-test-key",
            model="openai/gpt-4o-mini",
        )

        assert client.base_url == "https://openrouter.ai/api/v1"


class TestUnifiedLLMClientAPIKeyValidation:
    """Tests for API key validation."""

    def test_missing_api_key_for_openrouter_raises_error(self) -> None:
        """Test that missing API key raises ValueError for OpenRouter."""
        with pytest.raises(ValueError) as exc_info:
            UnifiedLLMClient(
                base_url="https://openrouter.ai/api/v1",
                model="openai/gpt-4o-mini",
            )

        error_message = str(exc_info.value)
        assert "API key is required" in error_message
        assert "Openrouter" in error_message

    def test_missing_api_key_for_openai_raises_error(self) -> None:
        """Test that missing API key raises ValueError for OpenAI."""
        with pytest.raises(ValueError) as exc_info:
            UnifiedLLMClient(
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
            )

        error_message = str(exc_info.value)
        assert "API key is required" in error_message
        assert "Openai" in error_message

    def test_ollama_works_without_api_key(self) -> None:
        """Test that Ollama works without API key."""
        # Should not raise
        client = UnifiedLLMClient(
            base_url="http://localhost:11434/v1",
            model="llama3.2",
        )
        assert client.provider_type == ProviderType.OLLAMA


class TestUnifiedLLMClientFromEnv:
    """Tests for from_env() class method."""

    def test_from_env_loads_all_variables(self) -> None:
        """Test from_env() loads all environment variables."""
        env_vars = {
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LLM_API_KEY": "sk-or-v1-test-key",
            "LLM_MODEL": "anthropic/claude-3-haiku-20240307",
            "LLM_ENABLE_USAGE_TRACKING": "true",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            client = UnifiedLLMClient.from_env()

            assert client.base_url == "https://openrouter.ai/api/v1"
            assert client.default_model == "anthropic/claude-3-haiku-20240307"
            assert client.provider_type == ProviderType.OPENROUTER

    def test_from_env_uses_default_model(self) -> None:
        """Test from_env() uses default model when not specified."""
        env_vars = {
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LLM_API_KEY": "sk-or-v1-test-key",
        }

        # Clear LLM_MODEL if it exists
        with patch.dict(os.environ, env_vars, clear=False):
            if "LLM_MODEL" in os.environ:
                del os.environ["LLM_MODEL"]
            client = UnifiedLLMClient.from_env()

            assert client.default_model == "openai/gpt-4o-mini"

    def test_from_env_missing_base_url_raises_error(self) -> None:
        """Test from_env() raises error when LLM_BASE_URL is missing."""
        # Clear the environment variable
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                UnifiedLLMClient.from_env()

            error_message = str(exc_info.value)
            assert "LLM_BASE_URL" in error_message
            assert "environment variable is required" in error_message

    def test_from_env_usage_tracking_disabled(self) -> None:
        """Test from_env() with usage tracking disabled."""
        env_vars = {
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "LLM_ENABLE_USAGE_TRACKING": "false",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            client = UnifiedLLMClient.from_env()
            # Usage tracking should be disabled
            assert client._enable_usage_tracking is False


class TestUnifiedLLMClientUsageTracking:
    """Tests for usage tracking functionality."""

    def test_usage_tracking_returns_correct_fields(self) -> None:
        """Test that usage tracking returns prompt_tokens, completion_tokens, total_tokens."""
        client = UnifiedLLMClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-v1-test-key",
            model="openai/gpt-4o-mini",
            enable_usage_tracking=True,
        )

        # Mock the OpenAI client response
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_message = MagicMock()
        mock_message.content = "Hello!"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "openai/gpt-4o-mini"

        with patch.object(client._client.chat.completions, "create", return_value=mock_response):
            response = client.generate([Message(role="user", content="Hi")])

            assert "prompt_tokens" in response.usage
            assert "completion_tokens" in response.usage
            assert "total_tokens" in response.usage
            assert response.usage["prompt_tokens"] == 10
            assert response.usage["completion_tokens"] == 20
            assert response.usage["total_tokens"] == 30

    def test_usage_tracking_disabled_returns_empty_dict(self) -> None:
        """Test that disabled usage tracking returns empty usage dict."""
        client = UnifiedLLMClient(
            base_url="http://localhost:11434/v1",
            model="llama3.2",
            enable_usage_tracking=False,
        )

        # Mock response without usage
        mock_message = MagicMock()
        mock_message.content = "Hello!"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock()  # Even if usage exists
        mock_response.model = "llama3.2"

        with patch.object(client._client.chat.completions, "create", return_value=mock_response):
            response = client.generate([Message(role="user", content="Hi")])

            assert response.usage == {}


class TestUnifiedLLMClientGenerate:
    """Tests for generate() method."""

    def test_generate_with_tool_calls(self) -> None:
        """Test generate() with tool calls in response."""
        client = UnifiedLLMClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-v1-test-key",
            model="openai/gpt-4o-mini",
        )

        # Mock tool call
        mock_function = MagicMock()
        mock_function.name = "search_books"
        mock_function.arguments = '{"query": "python"}'

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function = mock_function

        mock_message = MagicMock()
        mock_message.content = None
        mock_message.tool_calls = [mock_tool_call]

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        mock_response.model = "openai/gpt-4o-mini"

        with patch.object(client._client.chat.completions, "create", return_value=mock_response):
            tools = [
                ToolDefinition(
                    name="search_books",
                    description="Search for books",
                    parameters={"type": "object", "properties": {}},
                )
            ]
            response = client.generate(
                [Message(role="user", content="Find python books")],
                tools=tools,
            )

            assert response.has_tool_calls
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "search_books"
            assert response.tool_calls[0].id == "call_123"

    def test_generate_passes_temperature_and_max_tokens(self) -> None:
        """Test that generate() passes temperature and max_tokens correctly."""
        client = UnifiedLLMClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-v1-test-key",
            model="openai/gpt-4o-mini",
        )

        mock_message = MagicMock()
        mock_message.content = "Response"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "openai/gpt-4o-mini"

        with patch.object(
            client._client.chat.completions, "create", return_value=mock_response
        ) as mock_create:
            client.generate(
                [Message(role="user", content="Hi")],
                temperature=0.5,
                max_tokens=100,
            )

            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 100


class TestUnifiedLLMClientTokenCounting:
    """Tests for count_tokens() method."""

    def test_count_tokens_estimates_correctly(self) -> None:
        """Test token counting estimation."""
        client = UnifiedLLMClient(
            base_url="http://localhost:11434/v1",
            model="llama3.2",
        )

        messages = [
            Message(role="user", content="Hello, world!"),  # 13 chars
            Message(role="assistant", content="Hi there!"),  # 9 chars
        ]

        token_count = client.count_tokens(messages)

        # Total: 22 chars / 4 = 5 tokens (using rough 4 chars per token estimate)
        assert token_count == 5


class TestUnifiedLLMClientContextManager:
    """Tests for context manager functionality."""

    def test_context_manager_closes_client(self) -> None:
        """Test that context manager calls close()."""
        with patch("src.llm.unified_client.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            with UnifiedLLMClient(
                base_url="http://localhost:11434/v1",
                model="llama3.2",
            ):
                pass

            mock_client.close.assert_called_once()
