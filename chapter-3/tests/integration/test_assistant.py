"""Integration tests for Library Assistant with multi-turn conversation support.

These tests verify the complete flow of the Library Assistant:
- Tool execution loop
- Multi-turn conversation handling
- Token usage tracking
- Error handling
"""

import json

from src.agents.library_assistant import LibraryAssistant
from src.llm.base import LLMResponse, Message, ToolCall, ToolDefinition


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        """Initialize with a list of responses to return."""
        self._responses = responses
        self._response_index = 0
        self._calls: list[dict] = []
        self._message_counts: list[int] = []  # Track message count at each call

    @property
    def default_model(self) -> str:
        return "mock-model"

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Return the next response from the list."""
        # Record the number of messages at time of call
        self._message_counts.append(len(messages))
        self._calls.append(
            {
                "messages": list(messages),  # Copy the list
                "model": model,
                "tools": tools,
            }
        )

        if self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
            return response

        # Default text response
        return LLMResponse(
            content="I don't have any more prepared responses.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        )

    def count_tokens(self, messages: list[Message], model: str | None = None) -> int:
        return sum(len(m.content or "") for m in messages) // 4


class TestLibraryAssistantInit:
    """Test LibraryAssistant initialization."""

    def test_init_with_provider(self) -> None:
        """Test initialization with explicit provider."""
        provider = MockLLMProvider([])
        assistant = LibraryAssistant(llm_provider=provider)

        assert assistant._provider == provider
        assert len(assistant._conversation_history) == 1  # System message

    def test_init_system_prompt(self) -> None:
        """Test that system prompt is properly set."""
        provider = MockLLMProvider([])
        assistant = LibraryAssistant(llm_provider=provider)

        assert assistant._conversation_history[0].role == "system"
        assert "library" in assistant._conversation_history[0].content.lower()

    def test_init_empty_token_usage(self) -> None:
        """Test that token usage starts at zero."""
        provider = MockLLMProvider([])
        assistant = LibraryAssistant(llm_provider=provider)

        usage = assistant.get_token_usage()
        assert usage["total_prompt_tokens"] == 0
        assert usage["total_completion_tokens"] == 0


class TestLibraryAssistantQuery:
    """Test single query execution."""

    def test_simple_text_response(self) -> None:
        """Test handling a simple text response (no tool calls)."""
        response = LLMResponse(
            content="Hello! I'm the Library Assistant. How can I help you?",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
        )
        provider = MockLLMProvider([response])
        assistant = LibraryAssistant(llm_provider=provider)

        result = assistant.query("Hello")

        assert result == "Hello! I'm the Library Assistant. How can I help you?"

    def test_query_with_tool_call(self) -> None:
        """Test handling a query that triggers a tool call."""
        # First response: LLM decides to call a tool
        tool_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_123",
                    name="get_library_stats",
                    arguments="{}",
                )
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80},
        )
        # Second response: LLM responds with the result
        final_response = LLMResponse(
            content="The library has 200 books total. 150 are available, 30 are checked out, and 20 are missing.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 25, "total_tokens": 125},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider)

        result = assistant.query("How many books are in the library?")

        assert "200" in result or "library" in result.lower()

    def test_query_with_search_tool(self) -> None:
        """Test handling a search query."""
        # First response: LLM decides to search
        tool_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_456",
                    name="search_books",
                    arguments=json.dumps({"query": "Python", "category": "Programming"}),
                )
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 70, "completion_tokens": 25, "total_tokens": 95},
        )
        # Second response: LLM summarizes results
        final_response = LLMResponse(
            content="I found several Python programming books available.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 150, "completion_tokens": 20, "total_tokens": 170},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider)

        result = assistant.query("Find Python programming books")

        assert result is not None


class TestMultiTurnConversation:
    """Test multi-turn conversation support."""

    def test_conversation_history_maintained(self) -> None:
        """Test that conversation history is maintained across queries."""
        response1 = LLMResponse(
            content="I found 5 Python books.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
        )
        response2 = LLMResponse(
            content="The first book is 'Learning Python'.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 12, "total_tokens": 112},
        )

        provider = MockLLMProvider([response1, response2])
        assistant = LibraryAssistant(llm_provider=provider)

        assistant.query("Find Python books")
        assistant.query("What's the first one?")

        # Should have system + user1 + assistant1 + user2 + assistant2
        assert len(assistant._conversation_history) >= 5

    def test_context_from_previous_query(self) -> None:
        """Test that the assistant uses context from previous queries."""
        response1 = LLMResponse(
            content="The library has 200 books.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
        )
        response2 = LLMResponse(
            content="Yes, that's correct - 200 books in total.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 80, "completion_tokens": 12, "total_tokens": 92},
        )

        provider = MockLLMProvider([response1, response2])
        assistant = LibraryAssistant(llm_provider=provider)

        assistant.query("How many books?")
        assistant.query("Can you confirm that number?")

        # The second query should have been sent with history
        assert len(provider._calls) == 2
        # Second call should have more messages (using message counts at time of call)
        assert provider._message_counts[1] > provider._message_counts[0]

    def test_clear_conversation(self) -> None:
        """Test clearing conversation history."""
        response = LLMResponse(
            content="Hello!",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
        )

        provider = MockLLMProvider([response, response])
        assistant = LibraryAssistant(llm_provider=provider)

        assistant.query("Hello")
        assistant.clear_conversation()

        # Should only have the system message after clearing
        assert len(assistant._conversation_history) == 1
        assert assistant._conversation_history[0].role == "system"


class TestTokenUsageTracking:
    """Test token usage tracking across queries."""

    def test_token_usage_accumulated(self) -> None:
        """Test that token usage is accumulated across queries."""
        response1 = LLMResponse(
            content="First response",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
        )
        response2 = LLMResponse(
            content="Second response",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 80, "completion_tokens": 15, "total_tokens": 95},
        )

        provider = MockLLMProvider([response1, response2])
        assistant = LibraryAssistant(llm_provider=provider)

        assistant.query("First query")
        assistant.query("Second query")

        usage = assistant.get_token_usage()
        assert usage["total_prompt_tokens"] == 130  # 50 + 80
        assert usage["total_completion_tokens"] == 25  # 10 + 15
        assert usage["query_count"] == 2

    def test_token_usage_with_tool_calls(self) -> None:
        """Test that token usage includes tool call rounds."""
        tool_response = LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="call_1", name="get_library_stats", arguments="{}")],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80},
        )
        final_response = LLMResponse(
            content="Here are the stats",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider)

        assistant.query("Show library stats")

        usage = assistant.get_token_usage()
        assert usage["total_prompt_tokens"] == 160  # 60 + 100
        assert usage["total_completion_tokens"] == 30  # 20 + 10
        assert usage["tool_calls_count"] >= 1

    def test_reset_token_usage(self) -> None:
        """Test resetting token usage counters."""
        response = LLMResponse(
            content="Response",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
        )

        provider = MockLLMProvider([response])
        assistant = LibraryAssistant(llm_provider=provider)

        assistant.query("Test")
        assistant.reset_token_usage()

        usage = assistant.get_token_usage()
        assert usage["total_prompt_tokens"] == 0
        assert usage["total_completion_tokens"] == 0
        assert usage["query_count"] == 0


class TestErrorHandling:
    """Test error handling in the assistant."""

    def test_tool_execution_error_handled(self) -> None:
        """Test that tool execution errors are handled gracefully."""
        # Tool call with invalid arguments
        tool_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_err",
                    name="search_books",
                    arguments='{"invalid_param": "value"}',  # Missing required 'query'
                )
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
        )
        final_response = LLMResponse(
            content="I encountered an error. Let me try again.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider)

        # Should not raise, should handle gracefully
        result = assistant.query("Search for something")
        assert result is not None

    def test_unknown_tool_handled(self) -> None:
        """Test that unknown tool calls are handled gracefully."""
        tool_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_unknown",
                    name="unknown_tool",
                    arguments="{}",
                )
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
        )
        final_response = LLMResponse(
            content="I apologize, I tried to use a tool that doesn't exist.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider)

        result = assistant.query("Do something unusual")
        assert result is not None

    def test_max_tool_iterations_limit(self) -> None:
        """Test that there's a limit on tool call iterations."""
        # Create responses that keep calling tools indefinitely
        infinite_tool_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_loop",
                    name="get_library_stats",
                    arguments="{}",
                )
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
        )

        # Provide many tool responses
        responses = [infinite_tool_response] * 20
        # Final response to break the loop
        responses.append(
            LLMResponse(
                content="Done after many iterations",
                tool_calls=[],
                finish_reason="stop",
                usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            )
        )

        provider = MockLLMProvider(responses)
        assistant = LibraryAssistant(llm_provider=provider, max_tool_iterations=5)

        # Should not loop forever, should hit iteration limit
        result = assistant.query("Keep running tools")
        assert result is not None


class TestShowToolCalls:
    """Test tool call display functionality."""

    def test_show_tool_calls_default_true(self) -> None:
        """Test that show_tool_calls is True by default."""
        provider = MockLLMProvider([])
        assistant = LibraryAssistant(llm_provider=provider)

        assert assistant._show_tool_calls is True

    def test_show_tool_calls_can_be_disabled(self) -> None:
        """Test that show_tool_calls can be disabled on init."""
        provider = MockLLMProvider([])
        assistant = LibraryAssistant(llm_provider=provider, show_tool_calls=False)

        assert assistant._show_tool_calls is False

    def test_show_tool_calls_can_be_toggled(self) -> None:
        """Test that show_tool_calls can be toggled at runtime."""
        provider = MockLLMProvider([])
        assistant = LibraryAssistant(llm_provider=provider)

        assert assistant._show_tool_calls is True
        assistant._show_tool_calls = False
        assert assistant._show_tool_calls is False
        assistant._show_tool_calls = True
        assert assistant._show_tool_calls is True

    def test_tool_call_output_when_enabled(self, capsys) -> None:
        """Test that tool call info is printed when show_tool_calls is True."""
        tool_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_test",
                    name="get_library_stats",
                    arguments="{}",
                )
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80},
        )
        final_response = LLMResponse(
            content="The library has 200 books.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider, show_tool_calls=True)

        assistant.query("Show stats")

        captured = capsys.readouterr()
        # Check LLM call output
        assert "LLM Call" in captured.out
        assert "mock-model" in captured.out
        # Check tool call output
        assert "Tool Call" in captured.out
        assert "get_library_stats" in captured.out

    def test_tool_call_output_suppressed_when_disabled(self, capsys) -> None:
        """Test that tool call info is NOT printed when show_tool_calls is False."""
        tool_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_test",
                    name="get_library_stats",
                    arguments="{}",
                )
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80},
        )
        final_response = LLMResponse(
            content="The library has 200 books.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider, show_tool_calls=False)

        assistant.query("Show stats")

        captured = capsys.readouterr()
        # Check NO LLM call output
        assert "LLM Call" not in captured.out
        # Check NO tool call output
        assert "Tool Call" not in captured.out
        assert "get_library_stats" not in captured.out

    def test_llm_call_shows_iteration_number(self, capsys) -> None:
        """Test that LLM calls show iteration numbers."""
        tool_response = LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="call_1", name="get_library_stats", arguments="{}")],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80},
        )
        final_response = LLMResponse(
            content="Done",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider, show_tool_calls=True)

        assistant.query("Test")

        captured = capsys.readouterr()
        assert "LLM Call #1" in captured.out
        assert "LLM Call #2" in captured.out


class TestMultipleToolCalls:
    """Test handling of multiple simultaneous tool calls."""

    def test_multiple_tool_calls_in_one_response(self) -> None:
        """Test handling multiple tool calls in a single response."""
        tool_response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="search_books",
                    arguments=json.dumps({"query": "Python"}),
                ),
                ToolCall(
                    id="call_2",
                    name="get_library_stats",
                    arguments="{}",
                ),
            ],
            finish_reason="tool_calls",
            usage={"prompt_tokens": 70, "completion_tokens": 30, "total_tokens": 100},
        )
        final_response = LLMResponse(
            content="I found Python books and the library has 200 books total.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 200, "completion_tokens": 25, "total_tokens": 225},
        )

        provider = MockLLMProvider([tool_response, final_response])
        assistant = LibraryAssistant(llm_provider=provider)

        result = assistant.query("Find Python books and tell me library stats")
        assert result is not None

        usage = assistant.get_token_usage()
        assert usage["tool_calls_count"] >= 2
