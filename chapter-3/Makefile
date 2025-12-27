# Detect operating system and architecture for default Homebrew paths
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

# Default Homebrew paths: /opt/homebrew (Apple Silicon), /usr/local (Intel/older macOS)
ifeq ($(UNAME_S),Darwin)
    ifeq ($(UNAME_M),arm64)
        BREW_PREFIX := /opt/homebrew
    else
        BREW_PREFIX := /usr/local
    endif
endif

.PHONY: help dev-setup load-data verify-data generate-sales-data mcp-server mcp-dev mcp-client mcp-assistant mcp-compare-modes mcp-benchmark mcp-compare-modes-enterprise mcp-compare-modes-enterprise-all assistant assistant-rag assistant-enhanced assistant-code assistant-dummy-tools assistant-code-dummy-tools compare-modes compare-modes-enterprise compare-modes-enterprise-all test-code-execution benchmark generate-embeddings semantic-search data-analysis multi-agent test test-unit test-integration test-multi-agent lint format clean install-brew llm llm-rag


help:
	@echo "Chapter 3: AI Engineering with Library Management Data"
	@echo "Structure: RAG -> MCP -> Agentic AI"
	@echo ""
	@echo "=== Setup ==="
	@echo "  dev-setup                  - Install dependencies (uv sync)"
	@echo "  clean                      - Clean generated files"
	@echo ""
	@echo "=== Section 1: RAG (no database needed) ==="
	@echo "  llm                        - Chat with LLM (no RAG) - see hallucinations"
	@echo "  llm-rag                    - Chat with LLM + RAG - see accurate answers"
	@echo "  --- Production RAG (requires load-data first) ---"
	@echo "  generate-embeddings        - Generate embeddings for books AND sales"
	@echo "  semantic-search            - Interactive semantic search CLI"
	@echo "  assistant-rag              - Library Assistant with RAG enabled"
	@echo ""
	@echo "=== Section 2: MCP (requires load-data first) ==="
	@echo "  load-data                  - Load 200 books + 750 sales into DuckDB"
	@echo "  verify-data                - Verify data loaded correctly"
	@echo "  mcp-client                 - Settings menu to configure MCP options"
	@echo "  mcp-assistant              - AI Chat (code execution ON by default)"
	@echo "  mcp-assistant ARGS=\"--rag\" - Chat with RAG enabled"
	@echo "  mcp-assistant ARGS=\"--no-code-execution\" - Traditional JSON tools"
	@echo "  --- Token Efficiency Comparison ---"
	@echo "  mcp-compare-modes          - Compare Traditional vs Code Execution"
	@echo "  mcp-benchmark              - Run MCP token comparison benchmark"
	@echo "  mcp-compare-modes-enterprise     - Enterprise scale (100 tools, interactive)"
	@echo "  mcp-compare-modes-enterprise-all - Enterprise scale (100 tools, automated)"
	@echo "  --- Advanced: Running your own MCP server ---"
	@echo "  mcp-server                 - Start MCP server (for Claude Desktop)"
	@echo "  mcp-dev                    - Start MCP Inspector for debugging"
	@echo ""
	@echo "=== Section 3: Agentic AI ==="
	@echo "  assistant                  - Traditional tool-calling assistant"
	@echo "  data-analysis              - Start data analysis agent"
	@echo "  multi-agent                - Start multi-agent orchestrator"
	@echo ""
	@echo "=== Testing & Quality ==="
	@echo "  test                       - Run all tests"
	@echo "  test-unit                  - Run unit tests only"
	@echo "  test-integration           - Run integration tests only"
	@echo "  test-multi-agent           - Run multi-agent system tests"
	@echo "  test-code-execution        - Test code execution sandbox"
	@echo "  lint                       - Run ruff linter"
	@echo "  format                     - Auto-format code"



install-brew:
	if ! command -v brew >/dev/null 2>&1; then \
		echo "Homebrew not found. Installing..."; \
		/bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; \
		echo >> $(HOME)/.bash_profile; \
		echo 'eval "$$($(BREW_PREFIX)/bin/brew shellenv)"' >> $(HOME)/.bash_profile; \
		eval "$$($(BREW_PREFIX)/bin/brew shellenv)"; \
		source $(HOME)/.bash_profile; \
	fi; \

install-uv:
	if ! command -v uv >/dev/null 2>&1; then \
		echo "uv not found. Installing via Homebrew..."; \
		$(BREW_PREFIX)/bin/brew install uv; \
		echo 'eval "$$(uv generate-shell-completion bash)"' >> $(HOME)/.bash_profile ;\
		source $(HOME)/.bash_profile; \
	fi; \

dev-setup: install-brew install-uv
	@echo "Setting up development environment..."
	uv sync
	@echo "✓ Dependencies installed"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and add your OPENROUTER_API_KEY"
	@echo "  2. Run 'make load-data' to load CSV into DuckDB"

load-data: generate-sales-data
	@echo "Loading CSV data (books + sales) into DuckDB..."
	uv run python scripts/load_library_csv_to_duckdb.py --include-sales

generate-sales-data:
	@echo "Generating synthetic sales data..."
	uv run python scripts/generate_sales_data.py

verify-data:
	@echo "Verifying data load..."
	@uv run python -c "import duckdb; conn = duckdb.connect('data/duckdb/chapter3.db'); count = conn.execute('SELECT COUNT(*) FROM library.books').fetchone()[0]; print(f'✓ Found {count} books'); assert count == 200, f'Expected 200 books, got {count}'"

mcp-server:
	@echo "Starting MCP server..."
	uv run fastmcp run src/mcp/library_server.py

mcp-dev:
	@echo "Starting MCP Inspector..."
	uv run fastmcp dev src/mcp/library_server.py

mcp-client:
	@echo "============================================================"
	@echo "MCP Client - Configuration Settings"
	@echo "============================================================"
	@echo ""
	@echo "Configure MCP options, then launch the assistant."
	@echo ""
	uv run python -W ignore::RuntimeWarning -m src.mcp.client -i $(ARGS)

mcp-assistant:
	uv run python -W ignore::RuntimeWarning -m src.mcp.client --no-menu $(ARGS)

mcp-compare-modes:
	@echo "============================================================"
	@echo "MCP Token Efficiency: Traditional vs Code Execution"
	@echo "============================================================"
	@echo ""
	uv run python scripts/compare_modes.py

mcp-benchmark:
	@echo "============================================================"
	@echo "MCP Token Comparison Benchmark"
	@echo "============================================================"
	@echo ""
	uv run python benchmarks/token_comparison.py

mcp-compare-modes-enterprise:
	@echo "============================================================"
	@echo "MCP Enterprise Scale Demo (100 Tools)"
	@echo "============================================================"
	@echo "Expected: 80%+ token reduction with code execution"
	@echo ""
	uv run python scripts/compare_modes.py --enable-dummy-tools

mcp-compare-modes-enterprise-all:
	@echo "============================================================"
	@echo "MCP Enterprise Scale Demo - Full Benchmark (100 Tools)"
	@echo "============================================================"
	@echo "Running ALL queries with 100 dummy tools..."
	@echo ""
	uv run python scripts/compare_modes.py --enable-dummy-tools --all --no-rag

assistant:
	@echo "Starting Library Assistant (Traditional Mode)..."
	@uv run python -W ignore::RuntimeWarning -m src.agentic.agents.library_assistant

assistant-rag:
	@echo "Starting Library Assistant (RAG Mode)..."
	@uv run python -W ignore::RuntimeWarning -m src.agentic.agents.library_assistant --rag

assistant-enhanced:
	@echo "Starting Enhanced Library Assistant (Code Execution Mode)..."
	@uv run python -W ignore::RuntimeWarning -m src.agentic.agents.library_assistant_enhanced

assistant-dummy-tools:
	@echo "Starting Library Assistant (Traditional Mode + 100 Enterprise Dummy Tools)..."
	@echo "This demonstrates token overhead at enterprise scale."
	@uv run python -W ignore::RuntimeWarning -m src.agentic.agents.library_assistant --dummy-tools

assistant-code-dummy-tools:
	@echo "Starting Enhanced Assistant (Code Execution Mode + 100 Enterprise Dummy Tools)..."
	@echo "This demonstrates token efficiency at enterprise scale."
	@uv run python -W ignore::RuntimeWarning -m src.agentic.agents.library_assistant_enhanced --mode code_execution --dummy-tools

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
	uv run python -c "from src.agentic.rag.embeddings import generate_all_embeddings; generate_all_embeddings()"
	@echo ""
	@echo "Generating sales embeddings..."
	uv run python -c "from src.agentic.rag.embeddings import generate_sales_embeddings; generate_sales_embeddings()"

semantic-search:
	@echo "Starting semantic search CLI..."
	uv run python -c "from src.agentic.rag.vector_store import semantic_search_cli; semantic_search_cli()"

llm:
	@echo "============================================================"
	@echo "LLM Chat (No RAG)"
	@echo "============================================================"
	@echo ""
	@echo "Ask about our library books - the LLM has NO access to the data."
	@echo "Try: Who wrote 'The Quantum Garden'?"
	@echo ""
	uv run python -m src.rag.simple_rag --no-rag

llm-rag:
	@echo "============================================================"
	@echo "LLM Chat with RAG (Library Data Enabled)"
	@echo "============================================================"
	@echo ""
	@echo "Now the LLM has access to our library database via RAG."
	@echo "Try the same question: Who wrote 'The Quantum Garden'?"
	@echo ""
	uv run python -m src.rag.simple_rag --rag

data-analysis:
	@echo "Starting data analysis agent..."
	uv run python -m src.agentic.agents.data_analysis_agent

multi-agent:
	@echo "Starting Multi-Agent Library System..."
	@echo ""
	@echo "This system uses specialized agents coordinated by an orchestrator:"
	@echo "  - SearchAgent: Book discovery and semantic search"
	@echo "  - AnalyticsAgent: Statistics and reporting"
	@echo "  - RecommendationAgent: Suggestions with quality filters"
	@echo ""
	uv run python -m src.agentic.agents.orchestrator_agent

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
