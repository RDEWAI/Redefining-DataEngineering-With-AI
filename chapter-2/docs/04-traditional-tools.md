# Traditional Tool Use with JSON Schema

This document explains the traditional JSON schema tool use pattern implemented in the Library Assistant. This serves as a baseline for comparing token usage with the code execution pattern.

## Overview

Traditional tool use follows the pattern documented in the [Anthropic Tool Use Guide](https://docs.anthropic.com/en/docs/build-with-claude/tool-use):

1. Define tools with JSON schemas
2. Send user query with tool definitions
3. LLM returns tool calls (if needed)
4. Execute tools and return results
5. LLM generates final response

## Architecture

```
User Input
    │
    ▼
┌─────────────────────────┐
│   Library Assistant     │
│   (with tool defs)      │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│       LLM API           │
│  (OpenRouter/Ollama)    │
└─────────────────────────┘
    │
    ▼ (tool_calls)
┌─────────────────────────┐
│    Tool Executor        │
│  search_books()         │
│  get_book_details()     │
│  list_by_category()     │
│  ...                    │
└─────────────────────────┘
    │
    ▼ (tool_results)
┌─────────────────────────┐
│       LLM API           │
│  (generates response)   │
└─────────────────────────┘
    │
    ▼
Final Response
```

## Tool Definitions

The Library Assistant exposes 9 tools, defined in `src/agents/library_assistant.py`:

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `search_books` | Search by title/author/keyword | `query` |
| `get_book_details` | Get complete book information | `book_id` |
| `check_availability` | Check if book is available | `book_id` |
| `list_by_category` | List books in a category | `category` |
| `list_by_status` | List books by status | `status` |
| `locate_book` | Get physical location | `book_id` |
| `find_books_in_cabinet` | List books in a cabinet | `cabinet` |
| `get_weak_signal_books` | Find books with weak RFID | (optional `threshold`) |
| `get_library_stats` | Get aggregate statistics | (none) |

## JSON Schema Example

Each tool is defined with a JSON Schema for parameters:

```python
ToolDefinition(
    name="search_books",
    description="Search books by title, author, or keyword.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to match against title or author"
            },
            "category": {
                "type": "string",
                "enum": ["Programming", "History", "Science", "Fiction", "Thriller"],
                "description": "Optional category filter"
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of results"
            }
        },
        "required": ["query"]
    }
)
```

## Usage

### Interactive Mode

Start the interactive REPL:

```bash
make assistant
```

Or directly:

```bash
cd chapter-2
uv run python src/agents/library_assistant.py
```

### Environment Configuration

Create a `.env` file in the `chapter-2/` directory:

```bash
# Copy the example
cp .env.example .env

# Edit with your settings
```

**Required `.env` variables:**

```bash
# API Key (required for OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Provider settings
LLM_PROVIDER=openrouter
LLM_MODEL=openai/gpt-4o-mini

# Database path
DB_PATH=data/duckdb/chapter2.db
```

**Important Notes:**
- The `.env` file is automatically loaded using `python-dotenv`
- **Not all OpenRouter models support tool calling!** Use models like:
  - `openai/gpt-4o-mini` ✅ (recommended - cheap and supports tools)
  - `anthropic/claude-3-haiku-20240307` ✅
  - `mistralai/mistral-small-latest` ✅
  - Free models (`:free` suffix) typically do NOT support tools ❌

### Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help message (with current tool display status) |
| `/settings` | Show current configuration (mode, RAG status, LLM settings) |
| `/stats` | Show token usage statistics |
| `/tools` | Toggle tool call display ON/OFF (for educational visibility) |
| `/clear` | Clear conversation history |
| `/reset` | Reset token counters |
| `/quit` | Exit the assistant |

### Educational Tool Call Display

The Library Assistant includes an **educational display mode** that shows the complete tool use flow. This is enabled by default (`/tools` to toggle).

**What you'll see:**

1. **🤖 LLM Call #N** - Shows when the model is being called and what it's doing
2. **🔧 Tool Calls** - Shows which tools the model decided to use
3. **📞 Calling** - Shows the function name and arguments
4. **✅ Result** - Shows the tool execution result summary

### Example Session

```
Library Assistant - Interactive Mode
==================================================

Provider: openrouter
Model: openai/gpt-4o-mini

Commands:
  /help     - Show this help message
  /stats    - Show token usage statistics
  /tools    - Toggle tool call display (currently: ON)
  /clear    - Clear conversation history
  /reset    - Reset token usage counters
  /quit     - Exit the assistant

Ask me anything about the library!
--------------------------------------------------

You: What programming books are available?

🤖 LLM Call #1 → openai/gpt-4o-mini
   └─ Analyzing query and deciding on tools...
   → Decided to call 1 tool(s)

🔧 Tool Call (1):
----------------------------------------
  📞 Calling: list_by_category()
     └─ category: Programming
  ✅ Result: Found 40 book(s) in Programming

🤖 LLM Call #2 → openai/gpt-4o-mini
   └─ Processing tool results and generating response...
   ✓ Response ready (no more tool calls needed)

A: Here are some programming books that are currently available in the library:

1. **The Adventures of Chronicles** by Jordan Brown
   - Location: Cabinet 4, Rack 5, Row 4
   - Status: Present

2. **The Chronicles of Quest** by Casey Smith
   - Location: Cabinet 4, Rack 5, Row 1
   - Status: Present

...

You: /stats

Token Usage Statistics:
  Queries: 1
  Tool calls: 1
  Prompt tokens: 4,591
  Completion tokens: 422
  Total tokens: 5,013

You: /tools
Tool call display: OFF

You: /quit
Goodbye!
```

### Understanding the Tool Use Loop

The example above demonstrates the complete tool use loop:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Query: "What programming books are available?"       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 🤖 LLM Call #1                                            │
│    - Receives query + tool definitions (9 tools)            │
│    - Analyzes what tools are needed                         │
│    - Returns: tool_calls = [list_by_category(Programming)]  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 🔧 Tool Execution                                         │
│    - Execute list_by_category("Programming")                │
│    - Returns: 40 books with details                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 🤖 LLM Call #2                                            │
│    - Receives tool results                                  │
│    - No more tools needed                                   │
│    - Generates natural language response                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Final Response to User                                    │
└─────────────────────────────────────────────────────────────┘
```

## Programmatic Usage

```python
from src.agentic.agents.library_assistant import LibraryAssistant, create_assistant

# Create with OpenRouter (tool display on by default)
assistant = create_assistant(provider="openrouter")

# Create with tool display disabled (for production/clean output)
assistant = create_assistant(provider="openrouter", show_tool_calls=False)

# Or with Ollama (local)
assistant = create_assistant(provider="ollama", model="llama3.2")

# Query the assistant
response = assistant.query("What programming books are available?")
print(response)

# Check token usage
usage = assistant.get_token_usage()
print(f"Total tokens used: {usage['total_tokens']}")
print(f"Tool calls made: {usage['tool_calls_count']}")

# Multi-turn conversation
assistant.query("How many are checked out?")  # Uses context from previous query

# Toggle tool call display at runtime
assistant._show_tool_calls = False  # Turn off
assistant._show_tool_calls = True   # Turn on

# Clear history for new conversation
assistant.clear_conversation()

# Reset token counters
assistant.reset_token_usage()
```

## Troubleshooting

### Error: "404 Not Found" from OpenRouter

**Problem:** `No endpoints found that support tool use`

**Solution:** The model you selected doesn't support tool/function calling. Use a model that supports tools:

```bash
# In .env, change to a supported model:
LLM_MODEL=openai/gpt-4o-mini
# NOT: LLM_MODEL=meta-llama/llama-3.2-3b-instruct:free
```

### Error: "Database lock" / "Could not set lock on file"

**Problem:** Another process (like MCP server) has the database locked.

**Solution:** The library tools now use read-only mode by default for concurrent access. If you still see this error:

1. Stop any running MCP servers: `kill <PID>`
2. Or restart and only run one process at a time

### Error: "API key is required"

**Problem:** The `.env` file is not being loaded or key is missing.

**Solution:**
1. Ensure `.env` file exists in `chapter-2/` directory
2. Check the key format (no quotes needed):
   ```bash
   OPENROUTER_API_KEY=sk-or-v1-your-key-here
   ```
3. The `.env` file is loaded automatically via `python-dotenv`

## Comparison with MCP

This table compares Traditional Tool Use with MCP (Model Context Protocol):

| Aspect | Traditional Tools | MCP |
|--------|-------------------|-----|
| **Integration** | Direct function calls | Protocol-based server |
| **Discovery** | Static tool list | Dynamic tool discovery |
| **Transport** | In-process | stdio/HTTP |
| **Use Case** | Single application | Multi-client sharing |
| **Complexity** | Lower | Higher |
| **Flexibility** | Limited | High |

## Token Usage Considerations

Traditional tool use has token overhead from:

1. **Tool Definitions**: Each call includes full JSON schemas (~500-800 tokens for 9 tools)
2. **Tool Results**: Raw JSON responses in conversation history
3. **Multiple Rounds**: Complex queries may need several tool calls

This baseline is measured for comparison with the code execution pattern in Phase 4, which aims to reduce token usage by 30%+ through:
- Single code generation instead of multiple tool calls
- Direct data manipulation without JSON overhead
- Batch operations in a single execution

## Next Steps

- See [05-code-execution.md](./05-code-execution.md) for the code execution pattern
- Compare token usage using `make benchmark`
