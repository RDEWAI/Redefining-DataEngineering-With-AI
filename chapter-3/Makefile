.PHONY: help dev-setup load-data verify-data mcp-server mcp-dev assistant benchmark generate-embeddings semantic-search multi-agent test test-unit test-integration lint format clean

help:
	@echo "Chapter 3: AI Engineering with Library Management Data"
	@echo ""
	@echo "Available targets:"
	@echo "  dev-setup           - Complete development setup"
	@echo "  load-data           - Load CSV into DuckDB"
	@echo "  verify-data         - Verify data loaded correctly"
	@echo "  mcp-server          - Start MCP server"
	@echo "  mcp-dev             - Start MCP Inspector for debugging"
	@echo "  assistant           - Start Library Assistant CLI"
	@echo "  benchmark           - Run token comparison benchmark"
	@echo "  generate-embeddings - Generate book embeddings for RAG"
	@echo "  semantic-search     - Test semantic search"
	@echo "  multi-agent         - Start multi-agent system"
	@echo "  test                - Run all tests"
	@echo "  test-unit           - Run unit tests only"
	@echo "  test-integration    - Run integration tests only"
	@echo "  lint                - Run ruff linter"
	@echo "  format              - Auto-format code"
	@echo "  clean               - Clean generated files"

dev-setup:
	@echo "Setting up development environment..."
	uv sync
	@echo "✓ Dependencies installed"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and add your OPENROUTER_API_KEY"
	@echo "  2. Run 'make load-data' to load CSV into DuckDB"

load-data:
	@echo "Loading CSV data into DuckDB..."
	uv run python scripts/load_library_csv_to_duckdb.py
	@echo "✓ Data loaded successfully"

verify-data:
	@echo "Verifying data load..."
	@uv run python -c "import duckdb; conn = duckdb.connect('data/duckdb/library.db'); count = conn.execute('SELECT COUNT(*) FROM library.books').fetchone()[0]; print(f'✓ Found {count} books'); assert count == 200, f'Expected 200 books, got {count}'"

mcp-server:
	@echo "Starting MCP server..."
	uv run fastmcp run src/mcp_servers/library_server.py

mcp-dev:
	@echo "Starting MCP Inspector..."
	uv run fastmcp dev src/mcp_servers/library_server.py

assistant:
	@echo "Starting Library Assistant..."
	uv run python src/agents/library_assistant.py

benchmark:
	@echo "Running token comparison benchmark..."
	uv run python benchmarks/token_comparison.py

generate-embeddings:
	@echo "Generating book embeddings..."
	uv run python -c "from src.rag.embeddings import generate_all_embeddings; generate_all_embeddings()"

semantic-search:
	@echo "Starting semantic search CLI..."
	uv run python -c "from src.rag.vector_store import semantic_search_cli; semantic_search_cli()"

multi-agent:
	@echo "Starting multi-agent system..."
	uv run python src/agents/orchestrator_agent.py

test:
	@echo "Running all tests..."
	uv run pytest tests/ -v

test-unit:
	@echo "Running unit tests..."
	uv run pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	uv run pytest tests/integration/ -v

lint:
	@echo "Running ruff linter..."
	uv run ruff check src/ tests/

format:
	@echo "Auto-formatting code..."
	uv run ruff format src/ tests/

clean:
	@echo "Cleaning generated files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned"
