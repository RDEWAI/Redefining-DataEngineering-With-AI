.PHONY: help dev-setup load-data verify-data mcp-server mcp-dev assistant assistant-rag assistant-enhanced assistant-code assistant-dummy-tools assistant-code-dummy-tools compare-modes compare-modes-enterprise compare-modes-enterprise-all test-code-execution benchmark generate-embeddings semantic-search data-analysis multi-agent test test-unit test-integration test-multi-agent lint format clean

help:
	@echo "Chapter 3: AI Engineering with Library Management Data"
	@echo ""
	@echo "Available targets:"
	@echo "  dev-setup                  - Complete development setup"
	@echo "  load-data                  - Load CSV into DuckDB"
	@echo "  verify-data                - Verify data loaded correctly"
	@echo "  mcp-server                 - Start MCP server"
	@echo "  mcp-dev                    - Start MCP Inspector for debugging"
	@echo ""
	@echo "Assistant Modes:"
	@echo "  assistant                  - Traditional mode (8 library tools)"
	@echo "  assistant-rag              - RAG mode (semantic search enabled)"
	@echo "  assistant-enhanced         - Code execution mode (switchable)"
	@echo "  assistant-dummy-tools      - Traditional mode + 100 enterprise dummy tools"
	@echo "  assistant-code-dummy-tools - Code execution mode + 100 enterprise dummy tools"
	@echo ""
	@echo "Comparison & Benchmarks:"
	@echo "  compare-modes              - Compare Traditional vs Code Execution (interactive)"
	@echo "  compare-modes-enterprise   - Enterprise scale demo with 100 dummy tools (interactive)"
	@echo "  compare-modes-enterprise-all - Run ALL queries with 100 dummy tools (automated)"
	@echo "  benchmark                  - Run token comparison benchmark"
	@echo "  test-code-execution        - Test Phase 6 code execution sandbox"
	@echo ""
	@echo "RAG & Semantic Search:"
	@echo "  generate-embeddings        - Generate book embeddings for RAG"
	@echo "  semantic-search            - Test semantic search"
	@echo "  data-analysis              - Start data analysis agent"
	@echo ""
	@echo "Multi-Agent System:"
	@echo "  multi-agent                - Start multi-agent system with orchestrator"
	@echo "  test-multi-agent           - Run multi-agent system tests"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  test                       - Run all tests"
	@echo "  test-unit                  - Run unit tests only"
	@echo "  test-integration           - Run integration tests only"
	@echo "  lint                       - Run ruff linter"
	@echo "  format                     - Auto-format code"
	@echo "  clean                      - Clean generated files"

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

verify-data:
	@echo "Verifying data load..."
	@uv run python -c "import duckdb; conn = duckdb.connect('data/duckdb/chapter3.db'); count = conn.execute('SELECT COUNT(*) FROM library.books').fetchone()[0]; print(f'✓ Found {count} books'); assert count == 200, f'Expected 200 books, got {count}'"

mcp-server:
	@echo "Starting MCP server..."
	uv run fastmcp run src/mcp_servers/library_server.py

mcp-dev:
	@echo "Starting MCP Inspector..."
	uv run fastmcp dev src/mcp_servers/library_server.py

assistant:
	@echo "Starting Library Assistant (Traditional Mode)..."
	uv run python src/agents/library_assistant.py

assistant-rag:
	@echo "Starting Library Assistant (RAG Mode)..."
	uv run python src/agents/library_assistant.py --rag

assistant-enhanced:
	@echo "Starting Enhanced Library Assistant (Code Execution Mode)..."
	uv run python src/agents/library_assistant_enhanced.py

assistant-dummy-tools:
	@echo "Starting Library Assistant (Traditional Mode + 100 Enterprise Dummy Tools)..."
	@echo "This demonstrates token overhead at enterprise scale."
	uv run python src/agents/library_assistant.py --dummy-tools

assistant-code-dummy-tools:
	@echo "Starting Enhanced Assistant (Code Execution Mode + 100 Enterprise Dummy Tools)..."
	@echo "This demonstrates token efficiency at enterprise scale."
	uv run python src/agents/library_assistant_enhanced.py --mode code_execution --dummy-tools

compare-modes:
	@echo "Comparing Traditional vs Code Execution modes..."
	uv run python scripts/compare_modes.py

compare-modes-enterprise:
	@echo "Enterprise Scale Demo: Comparing with 100 dummy tools..."
	@echo "Expected: 80%+ token reduction in code execution mode"
	@echo ""
	uv run python scripts/compare_modes.py --enable-dummy-tools

compare-modes-enterprise-all:
	@echo "Enterprise Scale Demo: Running ALL queries with 100 dummy tools..."
	@echo "Expected: 80%+ token reduction in code execution mode"
	uv run python scripts/compare_modes.py --enable-dummy-tools --all --no-rag

test-code-execution:
	@echo "Testing Phase 6 code execution sandbox..."
	uv run python scripts/test_code_execution.py

benchmark:
	@echo "Running token comparison benchmark..."
	uv run python benchmarks/token_comparison.py

generate-embeddings:
	@echo "Generating book embeddings..."
	uv run python -c "from src.rag.embeddings import generate_all_embeddings; generate_all_embeddings()"

semantic-search:
	@echo "Starting semantic search CLI..."
	uv run python -c "from src.rag.vector_store import semantic_search_cli; semantic_search_cli()"

data-analysis:
	@echo "Starting data analysis agent..."
	uv run python -m src.agents.data_analysis_agent

multi-agent:
	@echo "Starting Multi-Agent Library System..."
	@echo ""
	@echo "This system uses specialized agents coordinated by an orchestrator:"
	@echo "  - SearchAgent: Book discovery and semantic search"
	@echo "  - AnalyticsAgent: Statistics and reporting"
	@echo "  - RecommendationAgent: Suggestions with quality filters"
	@echo ""
	uv run python -m src.agents.orchestrator_agent

test-multi-agent:
	@echo "Running multi-agent system tests..."
	uv run pytest tests/unit/test_protocol.py tests/unit/test_agents.py tests/integration/test_multi_agent.py -v

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
