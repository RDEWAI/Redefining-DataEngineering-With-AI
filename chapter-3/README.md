# Chapter 3: AI Engineering with Library Management Data

This chapter demonstrates modern AI engineering patterns using a Library Management dataset. The content follows the book structure: **RAG** → **MCP** → **Agentic AI**.

---

## Section 1: RAG (Retrieval-Augmented Generation)

RAG enables LLMs to answer questions about private data they've never seen during training. This section demonstrates the core RAG pattern: **Retrieve** → **Augment** → **Generate**.

### Quick Start (Simple RAG Demo)

The minimal demo uses 5 fictional books hardcoded in the script - no database setup required:

```bash
# 1. Setup environment
make dev-setup

# 2. Configure API key
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# 3. Run the RAG demo
make rag-demo
```

**What You'll See:**

| Query | Without RAG | With RAG |
|-------|-------------|----------|
| "Who wrote The Quantum Garden?" | Hallucinated answer | "Dr. Elena Voss" (correct) |
| "Which books are available?" | "I don't have access" | Lists 3 available books |

```bash
# Interactive Q&A mode
make rag-interactive
```

### Production RAG with DuckDB VSS

For the full library dataset (200 books), we use vector embeddings and semantic search.
This requires database setup (see Section 2 prerequisites):

```bash
# Generate embeddings (after load-data)
make generate-embeddings

# Interactive semantic search
make semantic-search

# Assistant with RAG enabled
make assistant-rag
```

**Example Semantic Queries:**
- "books about time travel adventures"
- "something about Python programming"
- "mystery novels with detective stories"

### RAG Make Commands

| Command | Description |
|---------|-------------|
| `make rag-demo` | Simple RAG vs no-RAG comparison (no DB needed) |
| `make rag-interactive` | Interactive RAG Q&A mode (no DB needed) |
| `make generate-embeddings` | Generate book embeddings (requires DB) |
| `make semantic-search` | Interactive semantic search (requires DB) |
| `make assistant-rag` | Library Assistant with RAG (requires DB) |

---

## Section 2: MCP (Model Context Protocol)

MCP exposes your tools to AI applications like Claude Desktop. This section shows how to create and deploy an MCP server.

### Prerequisites (Database Setup)

MCP and Agentic sections require the library database:

```bash
# Load 200 books into DuckDB
make load-data
make verify-data    # Expected: ✓ Found 200 books
```

### Start the MCP Server

```bash
# Production mode
make mcp-server

# Development mode with MCP Inspector
make mcp-dev
```

### Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "library": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/agentic/mcp_servers/library_server.py"],
      "cwd": "/path/to/chapter-3"
    }
  }
}
```

**Available MCP Tools:**
- `search_books` - Search by title, author, or keyword
- `get_book_details` - Get full book information
- `get_available_books` - List books currently available
- `get_books_by_category` - Filter by category
- `get_library_statistics` - Library analytics
- `checkout_book` / `return_book` - Circulation management
- `get_overdue_books` - Find overdue items

### MCP Make Commands

| Command | Description |
|---------|-------------|
| `make mcp-server` | Start MCP server |
| `make mcp-dev` | Start MCP Inspector for debugging |

---

## Section 3: Agentic AI

This section covers tool-calling patterns, from traditional JSON schema tools to code execution and multi-agent orchestration.

### 3.1 Traditional Tool Use

The Library Assistant uses JSON schema-based tool calling:

```bash
make assistant
```

**In-App Commands:**
- `/help` - Show available commands
- `/tools` - Toggle tool call display
- `/stats` - Show token usage statistics
- `/quit` - Exit

**Example Queries:**
- "What programming books are available?"
- "Show me books by John Smith"
- "Which books are missing?"

### 3.2 Code Execution Pattern

Enhanced assistant with sandboxed Python execution for token efficiency:

```bash
# Code execution mode (default)
make assistant-enhanced

# Compare modes side-by-side
make compare-modes

# Run benchmarks
make benchmark
```

**Why Code Execution?**

Traditional tool calling sends full JSON schemas for every tool in every request. Code execution sends tools once, then executes Python code—dramatically reducing tokens.

**Expected Results:**
- Traditional: ~4,000 tokens
- Code Execution: ~2,100 tokens
- **Reduction: ~48%**

### 3.3 Enterprise Scale (100+ Tools)

At enterprise scale with many tools, the difference is dramatic:

```bash
# Interactive demo
make compare-modes-enterprise

# Automated full benchmark
make compare-modes-enterprise-all
```

**Enterprise Results (100 dummy tools):**
- Traditional: ~131,000 tokens
- Code Execution: ~25,000 tokens
- **Reduction: 80%+**

This demonstrates insights from Anthropic's "Advanced Tool Use" paper.

### 3.4 Multi-Agent System

Orchestrated specialist agents handle complex queries:

```bash
make multi-agent
```

**Specialist Agents:**
- **SearchAgent** - Book discovery and semantic search
- **AnalyticsAgent** - Statistics and reporting
- **RecommendationAgent** - Suggestions with quality filters

**Example Multi-Agent Queries:**
- "Find available programming books and recommend one with good signal"
- "How many books are missing? Show breakdown by category"
- "Search for fiction books and analyze their availability patterns"

### Agentic Make Commands

| Command | Description |
|---------|-------------|
| `make assistant` | Traditional tool-calling mode |
| `make assistant-enhanced` | Code execution mode |
| `make assistant-dummy-tools` | Traditional + 100 enterprise tools |
| `make assistant-code-dummy-tools` | Code execution + 100 enterprise tools |
| `make compare-modes` | Compare Traditional vs Code Execution |
| `make compare-modes-enterprise` | Enterprise scale demo (interactive) |
| `make compare-modes-enterprise-all` | Enterprise scale demo (automated) |
| `make test-code-execution` | Test code execution sandbox |
| `make benchmark` | Run token comparison benchmark |
| `make data-analysis` | Start data analysis agent |
| `make multi-agent` | Start multi-agent orchestrator |

---

## All Make Commands

### Setup

| Command | Description |
|---------|-------------|
| `make help` | Show all available targets |
| `make dev-setup` | Install dependencies (uv sync) |
| `make clean` | Clean generated files |

### Data (Required for MCP & Agentic)

| Command | Description |
|---------|-------------|
| `make load-data` | Load 200 books into DuckDB |
| `make verify-data` | Verify data loaded correctly |

### Testing & Quality

| Command | Description |
|---------|-------------|
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests only |
| `make test-multi-agent` | Run multi-agent system tests |
| `make lint` | Run ruff linter |
| `make format` | Auto-format code |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `LLM_PROVIDER` | `openrouter` or `ollama` | `openrouter` |
| `LLM_MODEL` | Model identifier | `anthropic/claude-3.5-sonnet` |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `DB_PATH` | DuckDB database path | `data/duckdb/chapter3.db` |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## Project Structure

```
chapter-3/
├── src/
│   ├── rag/                     # Section 1: Simple RAG demo
│   │   └── simple_rag.py        # Minimal RAG implementation
│   └── agentic/                 # Main package
│       ├── rag/                 # Production RAG (embeddings, vector store)
│       ├── mcp_servers/         # Section 2: MCP server
│       ├── library/             # Data layer (domain, repository)
│       ├── llm/                 # LLM abstraction (OpenRouter, Ollama)
│       ├── agents/              # Section 3: All agents
│       ├── code_execution/      # Sandbox for code execution
│       ├── tools/               # Tool registry and search
│       └── a2a/                 # Agent-to-Agent protocol
├── data/
│   ├── raw/library/             # Source CSV files
│   └── duckdb/                  # DuckDB database
├── scripts/                     # Utility scripts
├── benchmarks/                  # Performance benchmarks
├── docs/                        # Detailed documentation
└── tests/                       # Unit and integration tests
```

---

## Troubleshooting

### "OPENROUTER_API_KEY not set"
```bash
export OPENROUTER_API_KEY="your-key-here"
# Or add to .env file
```

### "Database not found"
```bash
make load-data
```

### "No module named 'fastmcp'"
```bash
uv sync
```

### "Embeddings table empty"
```bash
make generate-embeddings
```

### "Could not set lock on file" (DuckDB)
```bash
# Close other terminals running chapter-3 commands
lsof data/duckdb/chapter3.db
# Kill orphaned processes if needed
```

### "MCP server not connecting"
1. Check server is running: `make mcp-server`
2. Verify config path in Claude Desktop settings
3. Restart Claude Desktop completely

---

## Resources

- [FastMCP Documentation](https://gofastmcp.com/)
- [OpenRouter API](https://openrouter.ai/docs)
- [DuckDB VSS Extension](https://duckdb.org/docs/stable/core_extensions/vss)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

---

## License

Part of the "Redefining Data Engineering with AI" project.
