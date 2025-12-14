# Chapter 3: AI Engineering with Library Management Data

Progressive AI Engineering learning path using Library Management IoT dataset (200 books). This chapter demonstrates modern AI patterns through six sub-features, from basic data infrastructure to sophisticated multi-agent systems.

## Overview

This project implements a complete AI Engineering stack:

- **003a**: Library Data Infrastructure - DuckDB setup and query tools
- **003b**: Basic MCP Server - FastMCP tool exposure for Claude Desktop
- **003c**: Traditional Tool Use - JSON schema-based tool calling with token logging
- **003d**: Code Execution Pattern - Sandboxed Python execution for token efficiency
- **003e**: Advanced Tool Use & RAG - Semantic search with DuckDB VSS
- **003f**: A2A Multi-Agent System - Orchestrated specialist agents

## Quick Start

### Prerequisites

- Python 3.10-3.12
- UV package manager (`brew install uv` or `pip install uv`)
- OpenRouter API key (or local Ollama installation)

### Setup

```bash
# Install dependencies
make dev-setup

# Configure environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# Load data into DuckDB
make load-data
make verify-data
```

### Verify Installation

```bash
# Check data is loaded
make verify-data
# Expected: ✓ Found 200 books

# Run tests
make test
```

## Sub-Feature Workflows

### 003a: Library Data Infrastructure

Set up DuckDB database with library data and query capabilities.

```bash
# Load data
make load-data

# Verify
make verify-data

# Run tests
make test-unit
```

**Test Query:**
```python
import duckdb
conn = duckdb.connect('data/duckdb/library.db')
books = conn.execute("SELECT * FROM library.books WHERE category = 'Programming'").fetchall()
print(f"Found {len(books)} programming books")
```

### 003b: MCP Server

Expose library tools via MCP for Claude Desktop integration.

```bash
# Start MCP server
make mcp-server

# Test with MCP Inspector
make mcp-dev
```

**Claude Desktop Setup:**
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "library": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/mcp_servers/library_server.py"],
      "cwd": "/path/to/chapter-3"
    }
  }
}
```

### 003c: Traditional Tool Use

Library Assistant with JSON schema tools and token logging.

```bash
make assistant
```

**Example queries:**
- "What programming books are available?"
- "Show me books by John Smith"
- "Which books are missing?"

### 003d: Code Execution Benchmark

Measure token reduction with sandboxed code execution.

```bash
make benchmark
```

**Expected Results:**
- Traditional tools: ~1500 tokens
- Code execution: ~450 tokens
- Reduction: 70%

### 003e: Semantic Search (RAG)

Semantic book search using DuckDB VSS.

```bash
# Generate embeddings (first time only)
make generate-embeddings

# Test semantic search
make semantic-search
```

**Example queries:**
- "that book about time travel"
- "something about Python programming"
- "adventure stories"

### 003f: Multi-Agent System

Orchestrated specialist agents for complex queries.

```bash
make multi-agent
```

**Example queries:**
- "Find available programming books and recommend one with good signal"
- "How many books are missing? Show breakdown by category"
- "Search for fiction books and analyze their availability patterns"

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make help` | Show all available targets |
| `make dev-setup` | Complete development setup |
| `make load-data` | Load CSV into DuckDB |
| `make verify-data` | Verify data loaded correctly |
| `make mcp-server` | Start MCP server |
| `make mcp-dev` | Start MCP Inspector |
| `make assistant` | Start Library Assistant CLI |
| `make benchmark` | Run token comparison benchmark |
| `make generate-embeddings` | Generate book embeddings |
| `make semantic-search` | Test semantic search |
| `make multi-agent` | Start multi-agent system |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests only |
| `make lint` | Run ruff linter |
| `make format` | Auto-format code |
| `make clean` | Clean generated files |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `LLM_PROVIDER` | LLM provider (`openrouter` or `ollama`) | `openrouter` |
| `LLM_MODEL` | Model identifier | `anthropic/claude-3.5-sonnet` |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `DB_PATH` | DuckDB database path | `data/duckdb/library.db` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Project Structure

```
chapter-3/
├── README.md                    # This file
├── Makefile                     # Make targets
├── pyproject.toml               # UV dependencies
├── data/
│   ├── raw/library/             # Source CSV files
│   └── duckdb/                  # DuckDB database files
├── src/
│   ├── library/                 # 003a: Data layer
│   ├── llm/                     # 003a: LLM abstraction
│   ├── mcp_servers/             # 003b: MCP server
│   ├── agents/                  # 003c, 003e, 003f: Agents
│   ├── code_execution/          # 003d: Sandbox
│   ├── tools/                   # 003e: Tool registry
│   ├── rag/                     # 003e: RAG components
│   └── a2a/                     # 003f: A2A protocol
├── scripts/                     # Data loading scripts
├── benchmarks/                  # Performance benchmarks
├── docs/                        # Detailed documentation
└── tests/                       # Unit and integration tests
```

## Learning Path

1. **Start with 003a** - Understand data and query patterns
2. **Build 003b** - Learn MCP fundamentals
3. **Implement 003c** - Compare traditional tool calling
4. **Add 003d** - Measure token savings
5. **Enhance with 003e** - Add semantic search
6. **Complete with 003f** - Orchestrate multiple agents

Each sub-feature builds on the previous. Run tests at each step to verify correctness.

## Testing

```bash
# Run all tests
make test

# Run specific test suite
make test-unit
make test-integration

# Run with coverage
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

**Quality Gates:**
- Unit test coverage: 80%+
- Integration tests: 100% pass rate
- Linting: Zero ruff errors
- Type checking: mypy passing

## Troubleshooting

### "No module named 'fastmcp'"
```bash
uv sync
```

### "OPENROUTER_API_KEY not set"
```bash
export OPENROUTER_API_KEY="your-key-here"
# Or add to .env file
```

### "Database not found"
```bash
make load-data
```

### "MCP server not connecting"
1. Check server is running: `make mcp-server`
2. Verify config path in Claude Desktop settings
3. Restart Claude Desktop completely

### "Embeddings table empty"
```bash
make generate-embeddings
```

## Resources

- [FastMCP Documentation](https://gofastmcp.com/)
- [OpenRouter API](https://openrouter.ai/docs)
- [DuckDB VSS Extension](https://duckdb.org/docs/stable/core_extensions/vss)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

## License

Part of the "Redefining Data Engineering with AI" project.
