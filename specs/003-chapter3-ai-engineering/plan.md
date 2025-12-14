# Implementation Plan: Chapter 3 - AI Engineering with Library Management Data

**Branch**: `003-chapter3-ai-engineering` | **Date**: 2025-12-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-chapter3-ai-engineering/spec.md`
**GitHub Epic**: #15 | **Sub-Issues**: #16, #17, #18, #19, #20, #21

## Summary

Build a progressive AI Engineering learning path using the Library Management IoT dataset (200 books). The implementation spans six sub-features: data infrastructure (003a), MCP server (003b), traditional tool use (003c), code execution pattern (003d), RAG with semantic search (003e), and multi-agent orchestration (003f). Each sub-feature builds on the previous, demonstrating increasingly sophisticated AI patterns while measuring concrete benefits like token reduction.

## Technical Context

**Language/Version**: Python 3.10-3.12 (aligned with existing project)
**Primary Dependencies**:
- DuckDB 1.1.3 (existing - database)
- FastMCP (MCP server SDK)
- OpenRouter/Ollama (LLM providers)
- DuckDB VSS extension (vector similarity search for RAG)
- pandas, numpy, matplotlib, seaborn (sandbox whitelist)

**Storage**: DuckDB at `chapter-3/data/duckdb/library.db` with `library` schema
**Testing**: pytest with `uv run pytest` (aligned with constitution)
**Target Platform**: Local development (macOS/Linux)
**Project Type**: Single project with modular sub-packages
**Performance Goals**:
- Data loading: < 5 seconds for 200 records
- Tool response: < 2 seconds for search queries
- Code execution: < 30 seconds per sandbox run
- 30% token reduction with code execution vs traditional tools

**Constraints**:
- Sandbox imports restricted to: pandas, duckdb, numpy, matplotlib, seaborn
- 30-second execution timeout for generated code
- User-friendly error messages for all failures

**Scale/Scope**: 200 books, single-user educational environment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Maintainability | PASS | Type hints, docstrings, ruff linting planned |
| II. Testing Standards | PASS | Unit + integration tests per sub-feature, TDD where applicable |
| III. User Experience Consistency | PASS | CLI tools with --help, structured logging, actionable errors |
| IV. Performance & Scalability | PASS | Benchmarks for token comparison, profiling for code execution |
| V. Reproducibility & Environment | PASS | UV-managed, Docker for data only, `make` targets per sub-feature |

**Quality Gates**:
- [x] Linting (ruff) - zero errors required
- [x] Type checking (mypy) - passing required
- [x] Unit tests - 80% coverage minimum
- [x] Integration tests - 100% pass rate
- [x] UV dependency resolution - successful sync
- [x] Documentation - quickstart + API docs per sub-feature

## Project Structure

### Documentation (this feature)

```text
specs/003-chapter3-ai-engineering/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (MCP tool schemas, API contracts)
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
chapter-3/
├── README.md                    # Quickstart and overview
├── Makefile                     # make targets: load-data, mcp-server, assistant, benchmark, etc.
├── pyproject.toml               # UV-managed dependencies
├── data/
│   ├── raw/
│   │   └── library/
│   │       └── library_dataset_random.csv
│   └── duckdb/
│       └── library.db
├── src/
│   ├── __init__.py
│   ├── library/                 # 003a: Shared library layer
│   │   ├── __init__.py
│   │   ├── domain.py            # Data classes: Book, Location, Status
│   │   ├── repository.py        # DuckDB I/O, search, stats
│   │   └── tools.py             # Standardized tool functions
│   ├── llm/                     # 003a: LLM abstraction
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract interface
│   │   ├── openrouter_client.py # OpenRouter API client
│   │   └── ollama_client.py     # Ollama local client
│   ├── mcp_servers/             # 003b: MCP server
│   │   ├── __init__.py
│   │   └── library_server.py    # FastMCP library tools server
│   ├── agents/                  # 003c, 003e, 003f: Agents
│   │   ├── __init__.py
│   │   ├── library_assistant.py # 003c: Traditional tool use
│   │   ├── data_analysis_agent.py # 003e: RAG + analytics
│   │   ├── search_agent.py      # 003f: Search specialist
│   │   ├── analytics_agent.py   # 003f: Analytics specialist
│   │   ├── recommendation_agent.py # 003f: Recommendation specialist
│   │   └── orchestrator_agent.py   # 003f: Query router
│   ├── code_execution/          # 003d: Sandbox execution
│   │   ├── __init__.py
│   │   ├── sandbox.py           # Sandboxed Python executor
│   │   └── tool_api.py          # Tool-to-API transformer
│   ├── tools/                   # 003e: Tool registry
│   │   ├── __init__.py
│   │   ├── tool_registry.py     # Tool registry with metadata
│   │   └── tool_search.py       # Dynamic tool discovery
│   ├── rag/                     # 003e: RAG components
│   │   ├── __init__.py
│   │   ├── embeddings.py        # Embedding generation
│   │   └── vector_store.py      # DuckDB VSS vector store
│   └── a2a/                     # 003f: A2A protocol
│       ├── __init__.py
│       ├── protocol.py          # Message protocol
│       └── server.py            # In-process routing
├── scripts/
│   └── load_library_csv_to_duckdb.py
├── benchmarks/
│   └── token_comparison.py      # 003d: Token usage benchmark
├── docs/
│   ├── 01-data-infrastructure.md
│   ├── 02-llm-abstraction.md
│   ├── 03-mcp-basics.md
│   ├── 04-traditional-tools.md
│   ├── 05-code-execution.md
│   ├── 06-advanced-tools-rag.md
│   └── 07-a2a-multi-agent.md
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── test_domain.py
    │   ├── test_repository.py
    │   ├── test_tools.py
    │   ├── test_sandbox.py
    │   ├── test_embeddings.py
    │   └── test_tool_registry.py
    └── integration/
        ├── test_data_load.py
        ├── test_mcp_server.py
        ├── test_assistant.py
        ├── test_code_execution.py
        ├── test_semantic_search.py
        └── test_multi_agent.py
```

**Structure Decision**: Single project with modular sub-packages under `chapter-3/src/`. This mirrors the progressive build structure (003a-003f) while keeping related code together. The `chapter-3/` directory is self-contained to avoid conflicts with the main project's existing `scripts/` and `data/` directories.

## Complexity Tracking

No constitution violations requiring justification. The architecture follows established patterns:
- Repository pattern for data access (standard for DuckDB)
- Strategy pattern for LLM abstraction (required for multi-provider support)
- Plugin pattern for tool registry (required for dynamic discovery)
