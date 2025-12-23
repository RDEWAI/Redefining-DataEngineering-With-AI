# 02 - LLM Abstraction Layer

**Sub-feature**: 003a - Library Data Infrastructure (LLM component)
**GitHub Issue**: #16

## Overview

This document covers the LLM provider abstraction layer, which enables:
- Switching between LLM providers (OpenRouter, Ollama)
- Consistent interface for text generation
- Support for function/tool calling
- Token counting for usage tracking

## Quick Start

```python
from src.agentic.llm import OpenRouterProvider, OllamaProvider, Message, get_provider

# Using OpenRouter (cloud)
provider = OpenRouterProvider()  # Uses OPENROUTER_API_KEY env var

# Using Ollama (local)
provider = OllamaProvider()  # Uses localhost:11434

# Or use the factory function
provider = get_provider("openrouter")
provider = get_provider("ollama", base_url="http://localhost:11434")

# Generate a response
response = provider.generate([
    Message(role="user", content="What is Python?")
])
print(response.content)
```

## Configuration

### Environment Variables

```bash
# OpenRouter
OPENROUTER_API_KEY=sk-or-v1-...

# Ollama (optional, defaults to localhost:11434)
OLLAMA_HOST=http://localhost:11434
```

### .env.example

```bash
# LLM Provider Configuration
# Choose provider: openrouter or ollama
LLM_PROVIDER=openrouter

# OpenRouter API key (required for openrouter provider)
OPENROUTER_API_KEY=your-api-key-here

# Database path
DB_PATH=data/duckdb/library.db
```

## Provider Classes

### LLMProvider (Abstract Base)

All providers implement this interface:

```python
class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[list[ToolDefinition]] = None,
        tool_choice: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a response."""
        pass

    @abstractmethod
    def stream_generate(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Generate a streaming response."""
        pass

    @abstractmethod
    def count_tokens(
        self,
        messages: list[Message],
        model: Optional[str] = None,
    ) -> int:
        """Count tokens in messages."""
        pass
```

### OpenRouterProvider

Access cloud LLM models through OpenRouter:

```python
from src.agentic.llm import OpenRouterProvider, Message

# Initialize
provider = OpenRouterProvider(
    api_key="sk-or-v1-...",  # Or use OPENROUTER_API_KEY env var
    default_model="anthropic/claude-3-haiku",
)

# Basic generation
response = provider.generate([
    Message(role="system", content="You are a helpful assistant."),
    Message(role="user", content="Hello!"),
])

# With custom model
response = provider.generate(
    messages=[Message(role="user", content="Explain Python")],
    model="openai/gpt-4o-mini",
    temperature=0.5,
    max_tokens=500,
)

# Streaming
for chunk in provider.stream_generate([
    Message(role="user", content="Tell me a story")
]):
    print(chunk, end="", flush=True)
```

**Available Models via OpenRouter**:
- `anthropic/claude-3-haiku` (default, fast & cheap)
- `anthropic/claude-3-sonnet`
- `openai/gpt-4o-mini`
- `openai/gpt-4o`
- `meta-llama/llama-3-70b`
- And many more...

### OllamaProvider

Access locally running models:

```python
from src.agentic.llm import OllamaProvider, Message

# Initialize
provider = OllamaProvider(
    base_url="http://localhost:11434",  # Or use OLLAMA_HOST env var
    default_model="llama3.2",
)

# Basic generation
response = provider.generate([
    Message(role="user", content="Hello!"),
])

# List available models
models = provider.list_models()
print(models)  # ['llama3.2', 'mistral', ...]

# Check if server is running
if provider.check_connection():
    print("Ollama server is running")
```

**Common Ollama Models**:
- `llama3.2` (default, 8B parameters)
- `llama3.2:70b` (larger model)
- `mistral` (7B, fast)
- `codellama` (code-focused)

## Data Classes

### Message

```python
from src.agentic.llm import Message

# User message
user_msg = Message(role="user", content="Hello")

# System message
system_msg = Message(role="system", content="You are helpful.")

# Assistant message with tool calls
assistant_msg = Message(
    role="assistant",
    tool_calls=[{
        "id": "call_123",
        "function": {
            "name": "search_books",
            "arguments": '{"query": "Python"}'
        }
    }]
)

# Tool result message
tool_msg = Message(
    role="tool",
    tool_call_id="call_123",
    content='{"books": [...], "count": 5}'
)
```

### ToolDefinition

```python
from src.agentic.llm import ToolDefinition

search_tool = ToolDefinition(
    name="search_books",
    description="Search books by title or author",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "category": {
                "type": "string",
                "enum": ["Programming", "History", "Science", "Fiction", "Thriller"]
            }
        },
        "required": ["query"]
    }
)
```

### LLMResponse

```python
from src.agentic.llm import LLMResponse

response = provider.generate([...], tools=[search_tool])

# Check response
print(response.content)  # Text content (may be None if tool call)
print(response.has_tool_calls)  # True if tool calls present
print(response.tool_calls)  # List[ToolCall]
print(response.usage)  # {"prompt_tokens": 100, "completion_tokens": 50}
print(response.model)  # Model used
print(response.finish_reason)  # "stop", "tool_calls", etc.
```

## Tool Calling

### Defining Tools

```python
from src.agentic.llm import ToolDefinition, Message

# Define tools
tools = [
    ToolDefinition(
        name="search_books",
        description="Search books by title or author",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    ),
    ToolDefinition(
        name="get_book_details",
        description="Get details for a specific book",
        parameters={
            "type": "object",
            "properties": {
                "book_id": {"type": "string"}
            },
            "required": ["book_id"]
        }
    ),
]
```

### Tool Calling Loop

```python
import json
from src.agentic.library import search_books, get_book_details

# Define tool handlers
tool_handlers = {
    "search_books": search_books,
    "get_book_details": get_book_details,
}

# Initial request
messages = [
    Message(role="user", content="Find Python programming books")
]

# Tool calling loop
while True:
    response = provider.generate(messages, tools=tools)

    if not response.has_tool_calls:
        # No tool calls, we have the final response
        print(response.content)
        break

    # Add assistant message with tool calls
    messages.append(Message(
        role="assistant",
        tool_calls=[{
            "id": tc.id,
            "function": {
                "name": tc.name,
                "arguments": tc.arguments
            }
        } for tc in response.tool_calls]
    ))

    # Execute each tool call
    for tool_call in response.tool_calls:
        handler = tool_handlers.get(tool_call.name)
        if handler:
            args = json.loads(tool_call.arguments)
            result = handler(**args)

            # Add tool result
            messages.append(Message(
                role="tool",
                tool_call_id=tool_call.id,
                content=json.dumps(result)
            ))
```

## Token Counting

```python
from src.agentic.llm import Message

messages = [
    Message(role="system", content="You are a helpful assistant."),
    Message(role="user", content="What is Python programming?"),
]

# Count tokens (estimate)
token_count = provider.count_tokens(messages)
print(f"Estimated tokens: {token_count}")

# Get actual usage from response
response = provider.generate(messages)
print(f"Prompt tokens: {response.usage.get('prompt_tokens')}")
print(f"Completion tokens: {response.usage.get('completion_tokens')}")
print(f"Total tokens: {response.usage.get('total_tokens')}")
```

## Error Handling

```python
import httpx
from src.agentic.llm import OpenRouterProvider

try:
    provider = OpenRouterProvider()
    response = provider.generate([...])
except ValueError as e:
    # Missing API key
    print(f"Configuration error: {e}")
except httpx.HTTPStatusError as e:
    # API error (rate limit, invalid request, etc.)
    print(f"API error: {e.response.status_code}")
except httpx.RequestError as e:
    # Network error
    print(f"Network error: {e}")
```

## Best Practices

1. **Use Context Managers**:
```python
with OpenRouterProvider() as provider:
    response = provider.generate([...])
# Connection automatically closed
```

2. **Reuse Provider Instances**:
```python
# Good - single instance
provider = OpenRouterProvider()
for query in queries:
    provider.generate([Message(role="user", content=query)])

# Bad - creating new instance each time
for query in queries:
    provider = OpenRouterProvider()  # Don't do this
    provider.generate([...])
```

3. **Handle Token Limits**:
```python
MAX_TOKENS = 4096

messages = [...]
while provider.count_tokens(messages) > MAX_TOKENS:
    # Remove oldest messages (keep system prompt)
    messages = [messages[0]] + messages[2:]
```

4. **Use Appropriate Models**:
- Fast/cheap tasks: `anthropic/claude-3-haiku` or `llama3.2`
- Complex reasoning: `anthropic/claude-3-sonnet` or `gpt-4o`
- Local privacy: Ollama with any supported model

## File Structure

```
chapter-3/src/llm/
├── __init__.py          # Package exports & get_provider()
├── base.py              # Abstract base classes
├── openrouter_client.py # OpenRouter implementation
└── ollama_client.py     # Ollama implementation
```

## Next Steps

The LLM abstraction is used in:
- **Library Assistant** (003c) - Traditional tool calling
- **Code Execution** (003d) - Code generation for analytics
- **Multi-Agent** (003f) - Agent orchestration
