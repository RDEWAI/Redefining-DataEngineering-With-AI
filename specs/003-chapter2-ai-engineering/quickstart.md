# Quickstart: Chapter 2 - AI Engineering with Library Management Data

**Branch**: `003-chapter3-ai-engineering` | **Date**: 2025-12-14

## Prerequisites

- Python 3.10-3.12
- UV package manager (`brew install uv` or `pip install uv`)
- Docker (for data extraction only)
- OpenRouter API key (or local Ollama installation)

## Setup

### 1. Clone and Navigate

```bash
cd /path/to/Redefining-DataEngineering-With-AI
git checkout 003-chapter3-ai-engineering
cd chapter-2
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### 4. Load Data

```bash
# Extract CSV from Docker (one-time)
make data-copy

# Load into DuckDB
make load-data
```

## Sub-Feature Workflows

### 003a: Library Data Infrastructure

```bash
# Verify data is loaded
make verify-data

# Run data tests
make test-unit
```

**Quick Test:**
```python
import duckdb
conn = duckdb.connect('data/duckdb/chapter3.db')
print(conn.execute("SELECT COUNT(*) FROM library.books").fetchone())
# Expected: (200,)
```

### 003b: MCP Server

```bash
# Start MCP server
make mcp-server

# In another terminal, test with MCP Inspector
make mcp-dev
```

**Claude Desktop Configuration:**
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "library": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/mcp_servers/library_server.py"],
      "cwd": "/path/to/chapter-2"
    }
  }
}
```

### 003c: Traditional Tool Use (Library Assistant)

```bash
# Start interactive assistant
make assistant

# Example queries:
# > What programming books are available?
# > Show me books by John Smith
# > Which books are missing?
```

### 003d: Code Execution Benchmark

```bash
# Run token comparison benchmark
make benchmark

# View results
cat benchmarks/results/token_comparison.json
```

**Expected Output:**
```
Query: "Show top 5 categories by missing books with average signal strength"
Traditional tools: ~1500 tokens
Code execution: ~450 tokens
Reduction: 70%
```

### 003e: Semantic Search (RAG)

```bash
# Generate embeddings (first time only)
make generate-embeddings

# Test semantic search
make semantic-search

# Example queries:
# > that book about time travel
# > something about Python programming
# > adventure stories
```

### 003f: Multi-Agent System

```bash
# Start multi-agent CLI
make multi-agent

# Example queries:
# > Find available programming books and recommend one with good signal
# > How many books are missing? Show breakdown by category
# > Search for fiction books and analyze their availability patterns
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make help` | Show all available targets |
| `make dev-setup` | Complete development setup |
| `make data-copy` | Extract CSV from Docker |
| `make load-data` | Load CSV into DuckDB |
| `make verify-data` | Verify data loaded correctly |
| `make mcp-server` | Start MCP server |
| `make mcp-dev` | Start MCP Inspector for debugging |
| `make assistant` | Start Library Assistant CLI |
| `make benchmark` | Run token comparison benchmark |
| `make generate-embeddings` | Generate book embeddings for RAG |
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
| `DB_PATH` | DuckDB database path | `data/duckdb/chapter3.db` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Troubleshooting

### "No module named 'fastmcp'"
```bash
uv sync  # Re-sync dependencies
```

### "OPENROUTER_API_KEY not set"
```bash
export OPENROUTER_API_KEY="your-key-here"
# Or add to .env file
```

### "Database not found"
```bash
make load-data  # Load data first
```

### "MCP server not connecting"
1. Check server is running: `make mcp-server`
2. Verify config path in Claude Desktop settings
3. Restart Claude Desktop completely

### "Embeddings table empty"
```bash
make generate-embeddings  # Generate embeddings first
```

## Learning Path

1. **Start with 003a** - Understand the data and query patterns
2. **Build 003b** - Learn MCP fundamentals
3. **Implement 003c** - Compare traditional tool calling
4. **Add 003d** - Measure token savings with code execution
5. **Enhance with 003e** - Add semantic search capabilities
6. **Complete with 003f** - Orchestrate multiple agents

Each sub-feature builds on the previous. Run tests at each step to verify correctness.

## Resources

- [FastMCP Documentation](https://gofastmcp.com/)
- [OpenRouter API](https://openrouter.ai/docs)
- [DuckDB VSS Extension](https://duckdb.org/docs/stable/core_extensions/vss)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
