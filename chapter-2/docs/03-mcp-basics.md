# MCP Basics: Model Context Protocol for Library Tools

**Sub-feature**: 003b - Basic MCP Server
**Date**: 2025-12-14

## Overview

The Model Context Protocol (MCP) is an open standard for exposing tools, resources, and prompts to AI applications like Claude Desktop. This document explains how our Library MCP Server works and how it compares to traditional tool use patterns.

## What is MCP?

MCP provides a standardized way for AI applications to:
- **Tools**: Execute functions with typed parameters (like our `search_books`)
- **Resources**: Access data sources (like our `library://stats`)
- **Prompts**: Use pre-built prompt templates (like our `book_search`)

### MCP vs Traditional Tool Use

| Aspect | MCP | Traditional JSON Schema Tools |
|--------|-----|------------------------------|
| **Protocol** | Standardized MCP protocol | Custom API/function calls |
| **Discovery** | Automatic via MCP | Manual tool registration |
| **Schema** | Auto-generated from type hints | Manual JSON schema definition |
| **Integration** | Works with any MCP client | Requires custom integration |
| **Resources** | Built-in resource protocol | Custom data access |
| **Prompts** | Template system included | No standard approach |

## Library MCP Server Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Claude Desktop                        │
│                   (MCP Client)                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ MCP Protocol
                       │
┌──────────────────────▼──────────────────────────────────┐
│                Library MCP Server                        │
│              (FastMCP + Python)                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Tools     │  │  Resources  │  │   Prompts   │    │
│  │   (8)       │  │     (3)     │  │     (2)     │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │            │
│         └────────────────┼────────────────┘            │
│                          │                             │
│                ┌─────────▼──────────┐                  │
│                │ BookRepository     │                  │
│                │ (library layer)    │                  │
│                └─────────┬──────────┘                  │
│                          │                             │
│                ┌─────────▼──────────┐                  │
│                │   DuckDB Database  │                  │
│                │  (library.books)   │                  │
│                └────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

## Setup and Installation

### 1. Install FastMCP

```bash
cd chapter-2
uv add fastmcp
```

### 2. Configure Claude Desktop

Edit your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

Add the library-server configuration (update paths to match your system):

```json
{
  "mcpServers": {
    "library-server": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/chapter-2",
        "python",
        "-m",
        "fastmcp",
        "run",
        "src/mcp/library_server.py"
      ],
      "env": {
        "DB_PATH": "/absolute/path/to/chapter-2/data/duckdb/chapter2.db"
      }
    }
  }
}
```

### 3. Start the MCP Server

For production use with Claude Desktop:
```bash
make mcp-server
```

For development with MCP Inspector (debugging):
```bash
make mcp-dev
```

The MCP Inspector provides a web UI to test tools and inspect MCP communication.

## Available Tools

### 1. search_books

Search books by title, author, or keyword.

**Parameters:**
- `query` (required): Search query string
- `category` (optional): Filter by category (Programming, History, Science, Fiction, Thriller)
- `limit` (optional): Max results (1-50, default: 10)

**Example:**
```python
# In Claude Desktop:
"Search for Python programming books"
```

### 2. get_book_details

Get complete details for a specific book.

**Parameters:**
- `book_id` (required): Book ID (e.g., 'B001')

### 3. check_availability

Check if a book is available for checkout.

**Parameters:**
- `book_id` (required): Book ID to check

### 4. list_by_category

List all books in a category.

**Parameters:**
- `category` (required): Category name
- `status` (optional): Filter by status

### 5. list_by_status

List all books with a specific status.

**Parameters:**
- `status` (required): Present, Missing, or Checked Out
- `category` (optional): Filter by category

### 6. locate_book

Get the physical location of a book.

**Parameters:**
- `book_id` (required): Book ID to locate

### 7. find_books_in_cabinet

Find all books in a cabinet location.

**Parameters:**
- `cabinet` (required): Cabinet number
- `rack` (optional): Rack number within cabinet

### 8. get_weak_signal_books

Get books with weak RFID signals needing maintenance.

**Parameters:**
- `threshold` (optional): Signal strength threshold in dBm (default: -55)

## Available Resources

Resources provide read-only access to library data.

### 1. library://stats

Aggregate statistics showing book counts by category and status.

**Usage in Claude:**
```
"Show me the library statistics"
```

### 2. library://missing_books

List of all missing books, ordered by last seen timestamp.

**Usage in Claude:**
```
"What books are currently missing?"
```

### 3. library://location_map

Map of library locations showing book counts per Cabinet/Rack/Row.

**Usage in Claude:**
```
"Show me the library location map"
```

## Available Prompts

Prompts are pre-built templates for common queries.

### 1. book_search

Generate a natural language book search query.

**Arguments:**
- `query` (required): What the user is looking for

### 2. library_status_report

Generate a comprehensive library status report.

**Arguments:**
- `focus` (optional): Area to focus on (availability, maintenance, categories)

## Using MCP Tools in Claude Desktop

Once configured, you can use the library tools naturally in conversation:

**Example 1: Search and Check Availability**
```
User: "I'm looking for books about Python programming. Are any available?"

Claude will:
1. Use search_books(query="Python", category="Programming")
2. Use check_availability for each result
3. Present available books
```

**Example 2: Library Statistics**
```
User: "Give me a library status report focused on maintenance"

Claude will:
1. Use the library_status_report prompt with focus="maintenance"
2. Read library://stats resource
3. Call get_weak_signal_books
4. Read library://missing_books
5. Generate comprehensive report
```

**Example 3: Location Search**
```
User: "What books are in Cabinet 3?"

Claude will:
1. Use find_books_in_cabinet(cabinet=3)
2. Present the list with details
```

## MCP vs Traditional Tools: A Comparison

### Traditional Approach (User Story 3)

In User Story 3 (003c), we'll implement the same functionality using traditional JSON schema tools:

```python
# Manual tool definition
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_books",
            "description": "Search books...",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string", "enum": [...]}
                },
                "required": ["query"]
            }
        }
    }
]

# Manual tool execution
if tool_call.name == "search_books":
    result = search_books(**tool_call.arguments)
```

### MCP Approach (This Implementation)

```python
# Automatic schema generation from type hints
@mcp.tool()
def search_books(query: str, category: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Search books..."""
    # Implementation
```

**Benefits:**
- ✅ No manual JSON schema writing
- ✅ Type safety from Python type hints
- ✅ Automatic parameter validation
- ✅ Standardized protocol
- ✅ Built-in error handling
- ✅ Works with any MCP client

## Testing the MCP Server

### Unit Tests

Test schema generation and validation:

```bash
uv run pytest tests/unit/test_mcp_tools.py -v
```

### Integration Tests

Test end-to-end tool execution with FastMCP's test client:

```bash
uv run pytest tests/integration/test_mcp_server.py -v
```

### Manual Testing with MCP Inspector

1. Start the inspector:
   ```bash
   make mcp-dev
   ```

2. Open the web UI (usually http://localhost:5173)

3. Test tools interactively:
   - View all available tools
   - Execute tools with custom parameters
   - Inspect request/response payloads
   - Debug schema issues

## Debugging Tips

### Common Issues

**Issue**: Claude Desktop doesn't see the server

**Solutions:**
- Check that paths in `claude_desktop_config.json` are absolute
- Verify DB_PATH points to existing database
- Restart Claude Desktop after config changes
- Check Claude Desktop logs for connection errors

**Issue**: Tool calls fail with schema errors

**Solutions:**
- Run unit tests to verify schemas: `make test-unit`
- Use MCP Inspector to test tools directly
- Check parameter types match JSON schema

**Issue**: Database connection errors

**Solutions:**
- Verify DB_PATH is set correctly
- Ensure database file exists: `ls data/duckdb/chapter2.db`
- Run `make load-data` if database is missing
- Check database has data: `make verify-data`

### Logging

Enable debug logging in the MCP server:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Best Practices

### 1. User-Friendly Error Messages

Always return helpful error messages:

```python
if book is None:
    return {"error": f"Book with ID '{book_id}' not found. Please check the book ID and try again."}
```

### 2. Type Hints

Use type hints for automatic schema generation:

```python
def search_books(query: str, category: Optional[str] = None, limit: int = 10) -> list[dict]:
```

### 3. Docstrings

Provide clear docstrings - these become tool descriptions:

```python
"""Search books by title, author, or keyword.

Args:
    query: Search query to match against title or author
    category: Optional category filter
    limit: Maximum number of results to return
"""
```

### 4. Validation

Validate inputs and provide helpful feedback:

```python
if limit < 1 or limit > 50:
    return {"error": "Limit must be between 1 and 50"}
```

## Next Steps

- **User Story 3 (003c)**: Compare MCP approach with traditional JSON schema tools
- **User Story 4 (003d)**: Add code execution for token efficiency
- **User Story 5 (003e)**: Implement RAG with semantic search
- **User Story 6 (003f)**: Build multi-agent system with A2A protocol

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://gofastmcp.com/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Anthropic: Building with MCP](https://www.anthropic.com/news/model-context-protocol)
