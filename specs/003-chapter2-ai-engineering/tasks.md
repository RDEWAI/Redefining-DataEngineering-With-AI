# Tasks: Chapter 2 - AI Engineering with Library Management Data

**Input**: Design documents from `/specs/003-chapter3-ai-engineering/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**GitHub Epic**: #15 | **Sub-Issues**: #16, #17, #18, #19, #20, #21

**Tests**: Tests included per constitution (80% unit coverage, integration tests)

**Organization**: Tasks grouped by user story (US1-US6) mapping to sub-features (003a-003f)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US6) this task belongs to
- Include exact file paths in descriptions

## Path Convention

All paths relative to `chapter-2/` directory:
- **Source**: `src/`
- **Tests**: `tests/unit/`, `tests/integration/`
- **Scripts**: `scripts/`
- **Docs**: `docs/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [X] T001 Create `chapter-2/` directory structure per plan.md
- [X] T002 Create `chapter-2/pyproject.toml` with UV-managed dependencies (duckdb, fastmcp, openai, sentence-transformers, pandas, numpy, matplotlib, seaborn, pytest)
- [X] T003 [P] Create `chapter-2/Makefile` with targets: dev-setup, data-copy, load-data, test, lint
- [X] T004 [P] Create `chapter-2/.env.example` with OPENROUTER_API_KEY, LLM_PROVIDER, DB_PATH
- [X] T005 [P] Create `chapter-2/README.md` with quickstart and overview
- [X] T006 Initialize `chapter-2/src/__init__.py` and all sub-package `__init__.py` files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 [P] Create `chapter-2/src/library/__init__.py` with package exports
- [X] T008 [P] Create `chapter-2/src/llm/__init__.py` with package exports
- [X] T009 [P] Create `chapter-2/tests/__init__.py` and test package structure
- [X] T010 Create `chapter-2/data/raw/library/` directory and verify CSV is accessible
- [X] T011 Create `chapter-2/data/duckdb/` directory for database files

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Library Data Setup and Query (Priority: P1) - MVP

**Goal**: Set up library data infrastructure with DuckDB and query capabilities (Sub-feature 003a)

**Independent Test**: Load CSV, query by category, verify 200 records accessible

### Unit Tests for User Story 1

- [X] T012 [P] [US1] Create `chapter-2/tests/unit/test_domain.py` with tests for Book, Location, Status, Category domain classes
- [X] T013 [P] [US1] Create `chapter-2/tests/unit/test_repository.py` with tests for BookRepository (search, filter, stats)

### Integration Tests for User Story 1

- [X] T014 [P] [US1] Create `chapter-2/tests/integration/test_data_load.py` with end-to-end CSV loading test

### Domain Layer Implementation

- [X] T015 [P] [US1] Create `chapter-2/src/library/domain.py` with BookStatus enum (Present, Missing, Checked Out)
- [X] T016 [P] [US1] Add Category enum to `chapter-2/src/library/domain.py` (Programming, History, Science, Fiction, Thriller)
- [X] T017 [P] [US1] Add Location dataclass to `chapter-2/src/library/domain.py` (cabinet, rack, row)
- [X] T018 [US1] Add Book dataclass to `chapter-2/src/library/domain.py` with has_weak_signal and is_available properties

### Repository Layer Implementation

- [X] T019 [US1] Create `chapter-2/src/library/repository.py` with BookRepository class and DuckDB connection
- [X] T020 [US1] Add search_books(query, category) method to BookRepository
- [X] T021 [US1] Add get_book_by_id(book_id) method to BookRepository
- [X] T022 [US1] Add list_by_category(category, status) method to BookRepository
- [X] T023 [US1] Add list_by_status(status, category) method to BookRepository
- [X] T024 [US1] Add get_weak_signal_books(threshold) method to BookRepository
- [X] T025 [US1] Add find_books_in_cabinet(cabinet, rack) method to BookRepository
- [X] T026 [US1] Add get_library_stats() method to BookRepository

### Tool Functions Implementation

- [X] T027 [US1] Create `chapter-2/src/library/tools.py` with standardized tool functions wrapping repository
- [X] T028 [US1] Implement all 8 tool functions in tools.py: search_books, get_book_details, check_availability, list_by_category, list_by_status, locate_book, find_books_in_cabinet, get_weak_signal_books

### Data Loading Script

- [X] T029 [US1] Create `chapter-2/scripts/load_library_csv_to_duckdb.py` following pattern from Feature 002
- [X] T030 [US1] Add schema creation with library.books table and all constraints
- [X] T031 [US1] Add CSV loading with validation and error handling
- [X] T032 [US1] Add user-friendly error messages for data loading failures

### LLM Abstraction Layer

- [X] T033 [P] [US1] Create `chapter-2/src/llm/base.py` with abstract LLMProvider interface (generate, stream_generate, count_tokens)
- [X] T034 [US1] Create `chapter-2/src/llm/openrouter_client.py` implementing LLMProvider for OpenRouter API
- [X] T035 [US1] Create `chapter-2/src/llm/ollama_client.py` implementing LLMProvider for local Ollama
- [X] T036 [US1] Add token counting implementation to both LLM clients

### Makefile Targets for US1

- [X] T037 [US1] Add `make load-data` target to chapter-2/Makefile
- [X] T038 [US1] Add `make verify-data` target to check 200 records loaded
- [X] T039 [US1] Add `make test-unit` target for unit tests

### Documentation for US1

- [X] T040 [P] [US1] Create `chapter-2/docs/01-data-infrastructure.md` with setup instructions
- [X] T041 [P] [US1] Create `chapter-2/docs/02-llm-abstraction.md` with provider configuration

**Checkpoint**: User Story 1 complete - data infrastructure works independently

---

## Phase 4: User Story 2 - MCP Server for Library Tools (Priority: P2)

**Goal**: Expose library operations as MCP tools using FastMCP (Sub-feature 003b)

**Independent Test**: Connect Claude Desktop to MCP server, execute search_books tool

### Unit Tests for User Story 2

- [X] T042 [P] [US2] Create `chapter-2/tests/unit/test_mcp_tools.py` with tests for MCP tool schema generation

### Integration Tests for User Story 2

- [X] T043 [P] [US2] Create `chapter-2/tests/integration/test_mcp_server.py` with in-memory MCP transport tests

### MCP Server Implementation

- [X] T044 [US2] Create `chapter-2/src/mcp_servers/__init__.py`
- [X] T045 [US2] Create `chapter-2/src/mcp_servers/library_server.py` with FastMCP server initialization
- [X] T046 [US2] Add @mcp.tool decorators for all 8 library tools in library_server.py
- [X] T047 [US2] Add @mcp.resource decorators for library://stats, library://missing_books, library://location_map
- [X] T048 [US2] Add @mcp.prompt decorators for book_search, library_status_report
- [X] T049 [US2] Add Context parameter for logging and progress reporting
- [X] T050 [US2] Add user-friendly error messages for MCP tool failures

### MCP Configuration

- [X] T051 [US2] Create MCP server configuration JSON for Claude Desktop in docs/
- [X] T052 [US2] Add `make mcp-server` target to start FastMCP server
- [X] T053 [US2] Add `make mcp-dev` target to start MCP Inspector for debugging

### Documentation for US2

- [X] T054 [P] [US2] Create `chapter-2/docs/03-mcp-basics.md` with MCP concepts and setup

**Checkpoint**: User Story 2 complete - MCP server works with Claude Desktop

---

## Phase 5: User Story 3 - Traditional Tool Use with JSON Schema (Priority: P3)

**Goal**: Build Library Assistant with traditional JSON schema tools for baseline token measurement (Sub-feature 003c)

**Independent Test**: Ask "What programming books are available?" and verify tool calls and token logging

### Unit Tests for User Story 3

- [X] T055 [P] [US3] Create `chapter-2/tests/unit/test_tools.py` with tests for JSON schema tool definitions

### Integration Tests for User Story 3

- [X] T056 [P] [US3] Create `chapter-2/tests/integration/test_assistant.py` with multi-turn conversation tests

### Library Assistant Implementation

- [X] T057 [US3] Create `chapter-2/src/agents/__init__.py`
- [X] T058 [US3] Create `chapter-2/src/agents/library_assistant.py` with LibraryAssistant class
- [X] T059 [US3] Implement JSON schema tool definitions matching contracts/llm-tools.json
- [X] T060 [US3] Implement tool execution loop with tool_calls handling
- [X] T061 [US3] Add multi-turn conversation support with message history
- [X] T062 [US3] Add token usage logging per query for baseline measurement
- [X] T063 [US3] Add support for both OpenRouter and Ollama backends
- [X] T064 [US3] Add user-friendly error messages for tool failures

### CLI Interface for US3

- [X] T065 [US3] Add interactive REPL to library_assistant.py for CLI usage
- [X] T066 [US3] Add `make assistant` target to start Library Assistant CLI

### Documentation for US3

- [X] T067 [P] [US3] Create `chapter-2/docs/04-traditional-tools.md` comparing MCP vs traditional patterns

**Checkpoint**: User Story 3 complete - Library Assistant works with token logging

---

## Phase 5.5: Code Quality & Unified LLM Client (NEW)

**Goal**: Add git hooks for code quality enforcement and unify LLM client configuration across all providers

**Independent Test**:
- Run `git commit` → pre-commit hooks (ruff, mypy) execute automatically
- Run `git push` → pre-push hooks (unit tests) execute automatically
- Use `UnifiedLLMClient.from_env()` → client works with any provider (OpenRouter/Ollama/OpenAI)

**Dependencies**: Requires Phase 5 (US3) complete. Blocks Phase 6 (US4) until complete.

### Phase 5.5.1: Setup - Pre-commit Framework

**Purpose**: Install and configure pre-commit hooks framework

- [X] T5.5-001 Add `pre-commit>=3.0.0` to dev dependencies in `chapter-2/pyproject.toml`
- [X] T5.5-002 Run `uv sync` to install pre-commit dependency in `chapter-2/`
- [X] T5.5-003 Verify `uv run pre-commit --version` returns version >= 3.0.0

---

### Phase 5.5.2: Git Hooks Configuration

**Purpose**: Configure pre-commit and pre-push hooks for automated quality checks

- [X] T5.5-004 [P] Create `chapter-2/.pre-commit-config.yaml` with ruff-check hook (linting)
- [X] T5.5-005 [P] Add ruff-format hook to `.pre-commit-config.yaml` (formatting check)
- [X] T5.5-006 [P] Add mypy hook to `.pre-commit-config.yaml` (type checking)
- [X] T5.5-007 [P] Add pytest-unit hook for pre-push stage to `.pre-commit-config.yaml` (unit tests)
- [X] T5.5-008 Install git hooks using `uv run pre-commit install && uv run pre-commit install --hook-type pre-push`
- [X] T5.5-009 [P] Update `.gitignore` to exclude `.pre-commit-cache` and `.mypy_cache` directories
- [X] T5.5-010 Verify pre-commit hooks with `uv run pre-commit run --all-files`

**Checkpoint**: Git hooks installed and running - commits trigger ruff/mypy, pushes trigger tests

---

### Phase 5.5.3: Unified LLM Client Implementation

**Purpose**: Create OpenAI SDK-based unified client supporting OpenRouter, Ollama, and OpenAI

- [X] T5.5-011 [P] Create `chapter-2/src/llm/unified_client.py` with UnifiedLLMClient class
- [X] T5.5-012 [P] Implement OpenAI SDK initialization with custom `base_url` parameter in `unified_client.py`
- [X] T5.5-013 Add `from_env()` class method to load LLM_BASE_URL, LLM_API_KEY, LLM_MODEL from environment
- [X] T5.5-014 Implement `generate()` method matching LLMProvider interface from `base.py`
- [X] T5.5-015 Add usage tracking via OpenAI SDK `response.usage` (returns prompt_tokens, completion_tokens, total_tokens)
- [X] T5.5-016 Add API key validation - required for OpenRouter/OpenAI, optional for Ollama
- [X] T5.5-017 Add user-friendly error messages for configuration errors (missing API key, invalid URL)

**Checkpoint**: UnifiedLLMClient works with all three providers via base_url switching

---

### Phase 5.5.4: Unit Tests for Unified Client

**Purpose**: Test coverage for unified LLM client

- [X] T5.5-018 [P] Create `chapter-2/tests/unit/test_unified_client.py` with test fixtures
- [X] T5.5-019 [P] Add test for OpenRouter initialization (base_url=https://openrouter.ai/api/v1)
- [X] T5.5-020 [P] Add test for Ollama initialization (base_url=http://localhost:11434/v1, no API key)
- [X] T5.5-021 [P] Add test for OpenAI initialization (base_url=https://api.openai.com/v1)
- [X] T5.5-022 Add test for missing API key error when provider requires it
- [X] T5.5-023 Add test for usage tracking returns correct fields (prompt_tokens, completion_tokens, total_tokens)
- [X] T5.5-024 Add test for `from_env()` loading configuration from environment variables

---

### Phase 5.5.5: Integration & Migration

**Purpose**: Update configuration and maintain backward compatibility

- [X] T5.5-025 Update `chapter-2/.env.example` with unified LLM configuration variables:
  - LLM_BASE_URL (with examples for all 3 providers)
  - LLM_API_KEY (note: optional for Ollama)
  - LLM_MODEL (with model examples)
  - LLM_ENABLE_USAGE_TRACKING (default: true)
- [X] T5.5-026 Update `chapter-2/src/llm/__init__.py` to export UnifiedLLMClient
- [X] T5.5-027 Add deprecation warning docstrings to `chapter-2/src/llm/openrouter_client.py`
- [X] T5.5-028 Add deprecation warning docstrings to `chapter-2/src/llm/ollama_client.py`

**Checkpoint**: Configuration updated, legacy clients deprecated but still functional

---

### Phase 5.5.6: Verification & Documentation

**Purpose**: Verify all components work together

- [X] T5.5-029 Run full verification: `uv run pre-commit run --all-files` passes
- [X] T5.5-030 Run full verification: `uv run ruff check chapter-2/src/` passes with zero errors
- [X] T5.5-031 Run full verification: `uv run pytest chapter-2/tests/unit/ -v` passes 100%
- [X] T5.5-032 Verify git commit triggers pre-commit hooks automatically
- [X] T5.5-033 Verify git push triggers pre-push hooks (unit tests) automatically

**Checkpoint**: Phase 5.5 complete - code quality gates active, unified client ready

---

## Summary: Phase 5.5 Tasks

| Sub-Phase | Task Count | Parallelizable | Description |
|-----------|-----------|----------------|-------------|
| 5.5.1: Setup | 3 | 0 | Pre-commit installation |
| 5.5.2: Git Hooks | 7 | 4 | Hook configuration |
| 5.5.3: Unified Client | 7 | 2 | Core implementation |
| 5.5.4: Unit Tests | 7 | 4 | Test coverage |
| 5.5.5: Integration | 4 | 0 | Config & migration |
| 5.5.6: Verification | 5 | 0 | End-to-end validation |
| **Total** | **33** | **10** | |

### Parallel Execution for Phase 5.5

**After T5.5-003 (setup complete)**:
```bash
# Run in parallel:
Task: T5.5-004 [P] Create .pre-commit-config.yaml with ruff-check hook
Task: T5.5-005 [P] Add ruff-format hook
Task: T5.5-006 [P] Add mypy hook
Task: T5.5-007 [P] Add pytest-unit hook for pre-push
Task: T5.5-009 [P] Update .gitignore

# After hooks configured:
Task: T5.5-011 [P] Create unified_client.py
Task: T5.5-012 [P] Implement OpenAI SDK initialization
```

**After T5.5-017 (client complete)**:
```bash
# Run in parallel:
Task: T5.5-018 [P] Create test_unified_client.py
Task: T5.5-019 [P] Test OpenRouter initialization
Task: T5.5-020 [P] Test Ollama initialization
Task: T5.5-021 [P] Test OpenAI initialization
```

---

## Phase 6: User Story 4 - Code Execution for Token Efficiency (Priority: P4)

**Goal**: Implement sandboxed code execution and benchmark token reduction (Sub-feature 003d)

**Independent Test**: Run benchmark query, verify 30%+ token reduction with code execution

### Unit Tests for User Story 4

- [X] T068 [P] [US4] Create `chapter-2/tests/unit/test_sandbox.py` with security constraint tests (import whitelist, timeout, memory)

### Integration Tests for User Story 4

- [X] T069 [P] [US4] Create `chapter-2/tests/integration/test_code_execution.py` with end-to-end code execution tests

### Sandbox Implementation

- [X] T070 [US4] Create `chapter-2/src/code_execution/__init__.py`
- [X] T071 [US4] Create `chapter-2/src/code_execution/sandbox.py` with CodeSandbox class
- [X] T072 [US4] Implement subprocess isolation with resource limits (30s timeout, memory limit)
- [X] T073 [US4] Implement import whitelist enforcement (pandas, duckdb, numpy, matplotlib, seaborn)
- [X] T074 [US4] Add user-friendly error messages for timeout and out-of-memory conditions

### Tool-to-API Transformer

- [X] T075 [US4] Create `chapter-2/src/code_execution/tool_api.py` with tool-to-code wrapper generator
- [X] T076 [US4] Generate Python wrapper code for each library tool
- [X] T077 [US4] Add type hints and docstrings for LLM understanding

### Benchmark Implementation

- [X] T078 [US4] Create `chapter-2/benchmarks/token_comparison.py` with TokenBenchmark class
- [X] T079 [US4] Implement fixed benchmark query: "Show top 5 categories by missing books with average signal strength"
- [X] T080 [US4] Implement traditional tools measurement (multiple tool calls)
- [X] T081 [US4] Implement code execution measurement (single code generation)
- [X] T082 [US4] Add comparison output: token count, latency, accuracy
- [X] T083 [US4] Add `make benchmark` target to run token comparison

### Documentation for US4

- [X] T084 [P] [US4] Create `chapter-2/docs/05-code-execution.md` documenting token reduction results

### Dual-Mode Integration (Enhancement)

- [X] T085 [US4] Create `chapter-2/src/agents/library_assistant_enhanced.py` with dual-mode support
- [X] T086 [US4] Implement AssistantMode enum (TRADITIONAL, CODE_EXECUTION)
- [X] T087 [US4] Add mode switching capability with `/mode` command
- [X] T088 [US4] Add token tracking unified across both modes
- [X] T089 [US4] Create `chapter-2/scripts/compare_modes.py` for side-by-side comparison
- [X] T090 [US4] Add `make assistant-enhanced` target for interactive mode switching
- [X] T091 [US4] Add `make assistant-code` target for code execution mode
- [X] T092 [US4] Add `make compare-modes` target for automated comparison
- [X] T093 [US4] Update `docs/05-code-execution.md` with dual-mode usage guide

**Checkpoint**: User Story 4 complete - benchmark shows measurable token reduction + learners can compare modes hands-on

---

## Phase 6.5: Pre-Phase 7 - Dataset Enhancement with Description Column

**Goal**: Add Description column to library dataset and update all dependent code before starting RAG implementation

**Why**: RAG needs rich textual content for effective semantic search. The current dataset has only structured metadata (Title, Author, Category, Location). Adding 50-100 word book descriptions enables meaningful semantic embeddings and natural language queries.

**Impact**: Updates required across 7 source files, 5 test files, and 3 documentation files

**Independent Test**: Load enhanced CSV with description column, verify all 200 books have descriptions, all existing tests pass

**Dependencies**: Requires US4 (Phase 6) complete. Blocks US5 (Phase 7 RAG) until complete.

### Description Generation

- [X] T094 [P] Create `chapter-2/scripts/generate_descriptions.py` with hybrid template + LLM approach
- [X] T095 Implement category-specific description templates (Programming, Fiction, Thriller, Science, History)
- [X] T096 Generate 200 unique descriptions (50-100 words each) based on book titles and categories
- [X] T097 Write enhanced CSV with Description column (position 4, after Author) to `chapter-2/data/raw/library/library_dataset_random.csv`
- [X] T098 Validate: 200 books processed, no data loss, descriptions non-empty and semantically diverse

### Domain Model Updates

- [X] T099 [P] Update `chapter-2/src/library/domain.py` Book dataclass - add `description: str` field after `author`
- [X] T100 Update `Book.to_dict()` method in `domain.py` to include `"description": self.description`
- [X] T101 Update `Book.from_row()` classmethod in `domain.py` to unpack description from tuple (position 3)
- [X] T102 Update `Book.from_dict()` classmethod in `domain.py` to handle `description` key

### Database Schema & Loader Updates

- [X] T103 [P] Update `chapter-2/scripts/load_library_csv_to_duckdb.py` - add `description VARCHAR NOT NULL` to CREATE TABLE statement (after author)
- [X] T104 Update INSERT statement in `load_library_csv_to_duckdb.py` to map CSV `Description` column to database `description` field
- [X] T105 Add "description" to NULL value checks in `validate_data()` function in `load_library_csv_to_duckdb.py`
- [X] T106 Add length validation for descriptions (50-300 characters) in `validate_data()` function

### Repository Query Updates

- [X] T107 Update `chapter-2/src/library/repository.py` `search_books()` - add `description` to SELECT statement (line ~97)
- [X] T108 Update `chapter-2/src/library/repository.py` `get_book_by_id()` - add `description` to SELECT statement (line ~125)
- [X] T109 Update `chapter-2/src/library/repository.py` `list_by_category()` - add `description` to SELECT statement (line ~150)
- [X] T110 Update `chapter-2/src/library/repository.py` `list_by_status()` - add `description` to SELECT statement (line ~180)
- [X] T111 Update `chapter-2/src/library/repository.py` `get_weak_signal_books()` - add `description` to SELECT statement (line ~208)
- [X] T112 Update `chapter-2/src/library/repository.py` `find_books_in_cabinet()` - add `description` to SELECT statement (line ~232)

### Test Updates

- [X] T113 [P] Update `chapter-2/tests/unit/test_domain.py` - add description field to all Book test fixtures
- [X] T114 [P] Update `chapter-2/tests/unit/test_repository.py` - add description to test data and assertions
- [X] T115 [P] Update `chapter-2/tests/unit/test_tools.py` - add assertions for description in tool responses
- [X] T116 Update `chapter-2/tests/integration/test_data_load.py` - add description column existence validation
- [X] T117 Add description NULL check validation to `test_data_load.py`
- [X] T118 Add description length constraint checks (50-300 chars) to `test_data_load.py`

### Documentation Updates

- [X] T119 [P] Update `specs/003-chapter3-ai-engineering/data-model.md` - add Description field to Book entity schema
- [X] T120 [P] Update `specs/003-chapter3-ai-engineering/spec.md` FR-002 - add Description to list of book attributes
- [X] T121 [P] Update `chapter-2/docs/01-data-infrastructure.md` - update code examples to show Description field

### End-to-End Validation

- [X] T122 Delete existing database: `rm chapter-2/data/duckdb/chapter3.db`
- [X] T123 Run enhanced CSV loader: `python chapter-2/scripts/load_library_csv_to_duckdb.py`
- [X] T124 Run all unit tests: `uv run pytest chapter-2/tests/unit/ -v` - verify 100% pass
- [X] T125 Run all integration tests: `uv run pytest chapter-2/tests/integration/ -v` - verify 100% pass
- [X] T126 Verify 200 books loaded with descriptions: `SELECT COUNT(*), COUNT(description) FROM library.books`
- [X] T127 Spot-check sample descriptions for quality and semantic diversity

**Checkpoint**: Description column integrated into all phases - RAG implementation can begin with rich textual data

**Parallel Opportunities**:
```bash
# After T094-T098 (descriptions generated):
Task: T099 [P] Update Book dataclass
Task: T103 [P] Update CSV loader schema
Task: T113 [P] Update test_domain.py fixtures
Task: T114 [P] Update test_repository.py fixtures
Task: T115 [P] Update test_tools.py assertions
Task: T119 [P] Update data-model.md
Task: T120 [P] Update spec.md FR-002
Task: T121 [P] Update docs

# After T102 (domain complete):
# Run repository updates T107-T112 sequentially (same file)
# Run test updates T116-T118 sequentially (same file)
```

---

## Phase 7: User Story 5 - Semantic Search with RAG (Priority: P5)

**Goal**: Implement RAG with DuckDB VSS for semantic book search (Sub-feature 003e)

**Independent Test**: Search "that book about time travel" and receive relevant fiction/science books

### Unit Tests for User Story 5

- [X] T128 [P] [US5] Create `chapter-2/tests/unit/test_embeddings.py` with embedding generation tests
- [X] T129 [P] [US5] Create `chapter-2/tests/unit/test_tool_registry.py` with tool registry tests

### Integration Tests for User Story 5

- [X] T130 [P] [US5] Create `chapter-2/tests/integration/test_semantic_search.py` with retrieval accuracy tests

### RAG Implementation

- [X] T131 [US5] Create `chapter-2/src/rag/__init__.py`
- [X] T132 [US5] Create `chapter-2/src/rag/embeddings.py` with EmbeddingGenerator class using sentence-transformers
- [X] T133 [US5] Implement embed_text(text) and embed_books(books) methods
- [X] T134 [US5] Create `chapter-2/src/rag/vector_store.py` with DuckDBVectorStore class
- [X] T178 [US5] Implement VSS extension setup and book_embeddings table creation
- [X] T179 [US5] Implement semantic_search(query, top_k) using array_cosine_distance
- [X] T180 [US5] Add HNSW index creation after data population
- [X] T181 [US5] Add user-friendly error messages for empty search results

### Tool Registry Implementation

- [X] T182 [US5] Create `chapter-2/src/tools/__init__.py`
- [X] T183 [US5] Create `chapter-2/src/tools/tool_registry.py` with ToolRegistry class
- [X] T141 [US5] Implement register_tool(tool) with metadata (name, description, schema, capabilities)
- [X] T142 [US5] Implement get_tool(name) for direct lookup
- [X] T143 [US5] Implement list_tools(capability) for capability-based filtering

### Tool Search Implementation

- [X] T144 [US5] Create `chapter-2/src/tools/tool_search.py` with ToolSearch class
- [X] T145 [US5] Implement search_by_name(query) for name-based lookup
- [X] T146 [US5] Implement search_by_description(query) using embedding similarity

### Data Analysis Agent

- [X] T147 [US5] Create `chapter-2/src/agents/data_analysis_agent.py` with DataAnalysisAgent class
- [X] T148 [US5] Integrate code execution for complex analytics
- [X] T149 [US5] Integrate semantic search for book discovery

### CLI and Makefile for US5

- [X] T150 [US5] Add `make generate-embeddings` target to generate book embeddings
- [X] T151 [US5] Add `make semantic-search` target for interactive semantic search

### Documentation for US5

- [X] T152 [P] [US5] Create `chapter-2/docs/06-advanced-tools-rag.md` explaining RAG scope decisions

**Checkpoint**: User Story 5 complete - semantic search works with 70%+ top-3 precision

---

## Phase 7.5: Enterprise Tool Scale Demonstration (NEW)

**Goal**: Demonstrate token efficiency of code execution vs traditional tool calling at enterprise scale with 100 dummy tools across 10 domains.

**Independent Test**: Run `compare_modes.py --enable-dummy-tools` and verify 80%+ token reduction for code execution mode.

**Dependencies**: Requires Phase 7 (RAG) complete. Blocks Phase 8 (Multi-Agent System).

**Rationale**: From Anthropic's "Advanced Tool Use" paper - code execution dramatically reduces token overhead when dealing with many tools. This phase provides empirical evidence with a realistic enterprise simulation.

### Phase 7.5.1: Dummy Tool Generator

**Purpose**: Create 100 enterprise dummy tools across 10 domains

- [X] T7.5-001 [US4+] Create `chapter-2/src/tools/dummy_tools.py` with EnterpriseDomain enum and DummyTool dataclass
- [X] T7.5-002 [P] [US4+] Generate 10 tools for Engineering domain (CI/CD: run_build, check_ci_status, trigger_deployment, get_test_coverage, etc.)
- [X] T7.5-003 [P] [US4+] Generate 10 tools for Data Platform domain (query_warehouse, get_data_lineage, validate_schema, refresh_dashboard, etc.)
- [X] T7.5-004 [P] [US4+] Generate 10 tools for Security domain (scan_vulnerabilities, check_access_permissions, audit_logs, rotate_secrets, etc.)
- [X] T7.5-005 [P] [US4+] Generate 10 tools for HR domain (get_employee_info, submit_pto_request, check_org_chart, get_team_roster, etc.)
- [X] T7.5-006 [P] [US4+] Generate 10 tools for Finance domain (get_budget_status, submit_expense, generate_invoice, check_payment_status, etc.)
- [X] T7.5-007 [P] [US4+] Generate 10 tools for Marketing domain (get_campaign_metrics, schedule_post, analyze_sentiment, generate_report, etc.)
- [X] T7.5-008 [P] [US4+] Generate 10 tools for Sales domain (get_lead_details, update_opportunity, check_quota, forecast_revenue, etc.)
- [X] T7.5-009 [P] [US4+] Generate 10 tools for Support domain (create_ticket, get_ticket_status, escalate_issue, search_knowledge_base, etc.)
- [X] T7.5-010 [P] [US4+] Generate 10 tools for Infrastructure domain (check_server_status, scale_service, get_metrics, restart_container, etc.)
- [X] T7.5-011 [P] [US4+] Generate 10 tools for ML Platform domain (train_model, get_experiment_results, deploy_model, monitor_predictions, etc.)

### Phase 7.5.2: Mock Implementations

**Purpose**: Create mock function implementations for all dummy tools

- [X] T7.5-012 [US4+] Add `generate_dummy_tools() -> list[ToolDefinition]` function
- [X] T7.5-013 [US4+] Add `get_dummy_tool_functions() -> dict[str, Callable]` for mock implementations
- [X] T7.5-014 [US4+] Add `create_mock_function(domain, tool_name, description)` factory function
- [X] T7.5-015 [US4+] Ensure all mock functions return realistic-looking JSON responses

### Phase 7.5.3: Assistant Integration

**Purpose**: Update assistants to support dummy tools

- [X] T7.5-016 [US4+] Update `chapter-2/src/agents/library_assistant.py` - add `enable_dummy_tools: bool = False` parameter
- [X] T7.5-017 [US4+] Update `_get_tools()` method to optionally include dummy tools
- [X] T7.5-018 [US4+] Update `_get_tool_functions()` method to include dummy tool mock implementations
- [X] T7.5-019 [US4+] Update `chapter-2/src/agents/library_assistant_enhanced.py` - add `enable_dummy_tools: bool = False` parameter
- [X] T7.5-020 [US4+] Update `ToolAPIGenerator` to optionally include dummy tool API stubs in code execution mode

### Phase 7.5.4: CLI Commands

**Purpose**: Add interactive commands for enabling/disabling dummy tools

- [X] T7.5-021 [US4+] Add `/dummy-tools` command to library_assistant.py REPL
- [X] T7.5-022 [US4+] Add `/dummy-tools` command to library_assistant_enhanced.py REPL
- [X] T7.5-023 [US4+] Add `/settings` command update to show dummy tools count when enabled
- [X] T7.5-024 [US4+] Add tool count display in startup message when dummy tools enabled

### Phase 7.5.5: Compare Modes Update

**Purpose**: Update compare_modes.py to demonstrate enterprise scale

- [X] T7.5-025 [US4+] Update `chapter-2/scripts/compare_modes.py` - add `--enable-dummy-tools` argument
- [X] T7.5-026 [US4+] Add token breakdown display showing tool definition overhead
- [X] T7.5-027 [US4+] Add summary showing percentage reduction with dummy tools vs without

### Phase 7.5.6: Makefile Targets

**Purpose**: Add make targets for enterprise tool demonstration

- [X] T7.5-028 [P] [US4+] Add `make assistant-dummy-tools` target (starts traditional mode with 100 dummy tools)
- [X] T7.5-029 [P] [US4+] Add `make assistant-code-dummy-tools` target (starts code execution mode with 100 dummy tools)
- [X] T7.5-030 [P] [US4+] Add `make compare-modes-enterprise` target (runs comparison with dummy tools enabled)

### Phase 7.5.7: Unit Tests

**Purpose**: Test dummy tool generation and integration

- [X] T7.5-031 [P] [US4+] Create `chapter-2/tests/unit/test_dummy_tools.py`
- [X] T7.5-032 [P] [US4+] Test `generate_dummy_tools()` returns exactly 100 tools
- [X] T7.5-033 [P] [US4+] Test tools are distributed across 10 domains (10 each)
- [X] T7.5-034 [P] [US4+] Test `get_dummy_tool_functions()` returns matching function count
- [X] T7.5-035 [P] [US4+] Test mock functions return valid JSON structure

### Phase 7.5.8: Integration Tests

**Purpose**: End-to-end tests with dummy tools enabled

- [X] T7.5-036 [P] [US4+] Create `chapter-2/tests/integration/test_assistant_dummy.py`
- [X] T7.5-037 [P] [US4+] Test LibraryAssistant initializes with dummy tools enabled
- [X] T7.5-038 [P] [US4+] Test EnhancedLibraryAssistant initializes with dummy tools enabled
- [X] T7.5-039 [P] [US4+] Test library queries still work correctly with dummy tools present
- [X] T7.5-040 [P] [US4+] Test token usage increases in traditional mode with dummy tools

### Phase 7.5.9: Verification & Benchmark

**Purpose**: Verify implementation and record results

- [X] T7.5-041 [US4+] Run `uv run pytest chapter-2/tests/unit/test_dummy_tools.py -v` - verify 100% pass (30/30 tests passed)
- [X] T7.5-042 [US4+] Run `uv run pytest chapter-2/tests/integration/test_assistant_dummy.py -v` - verify 100% pass (16/16 tests passed)
- [X] T7.5-043 [US4+] Run `make compare-modes-enterprise` and record results (code execution works end-to-end)
- [X] T7.5-044 [US4+] Verify traditional mode uses 15,000+ tokens for tool definitions (~131,710 total for 6 queries - PASS)
- [X] T7.5-045 [US4+] Verify code execution mode uses < 2,000 tokens for tool definitions (~25,161 total for 6 queries, ~600-800 API stub overhead - PASS)
- [X] T7.5-046 [US4+] Verify token reduction is 80%+ as predicted (80.9% overall reduction - PASS)

### Phase 7.5.10: Documentation

**Purpose**: Document enterprise scale demonstration

- [X] T7.5-047 [P] [US4+] Create `chapter-2/docs/05.5-enterprise-tool-scale.md`
- [X] T7.5-048 [US4+] Document motivation (Anthropic paper reference)
- [X] T7.5-049 [US4+] Document 10 enterprise domains and tool examples
- [X] T7.5-050 [US4+] Document expected token reduction percentages
- [X] T7.5-051 [US4+] Document how to run comparison benchmarks

**Checkpoint**: Phase 7.5 complete - enterprise scale demonstration shows 80%+ token reduction (80.9% achieved)

---

### Phase 7.5 Summary

| Sub-Phase | Task Count | Parallelizable | Description |
|-----------|-----------|----------------|-------------|
| 7.5.1: Tool Generator | 11 | 10 | Create 100 enterprise dummy tools |
| 7.5.2: Mock Implementations | 4 | 0 | Mock function factory |
| 7.5.3: Assistant Integration | 5 | 0 | Update assistants |
| 7.5.4: CLI Commands | 4 | 0 | Interactive commands |
| 7.5.5: Compare Modes | 3 | 0 | Benchmark script updates |
| 7.5.6: Makefile Targets | 3 | 3 | Make targets |
| 7.5.7: Unit Tests | 5 | 5 | Test coverage |
| 7.5.8: Integration Tests | 5 | 5 | E2E tests |
| 7.5.9: Documentation | 5 | 1 | Docs |
| 7.5.10: Verification | 6 | 0 | Benchmarks |
| **Total** | **51** | **24** | |

### Parallel Execution for Phase 7.5

**After T7.5-001 (base module created)**:
```bash
# Run in parallel - all 10 domain tool generators:
Task: T7.5-002 [P] Engineering domain tools
Task: T7.5-003 [P] Data Platform domain tools
Task: T7.5-004 [P] Security domain tools
Task: T7.5-005 [P] HR domain tools
Task: T7.5-006 [P] Finance domain tools
Task: T7.5-007 [P] Marketing domain tools
Task: T7.5-008 [P] Sales domain tools
Task: T7.5-009 [P] Support domain tools
Task: T7.5-010 [P] Infrastructure domain tools
Task: T7.5-011 [P] ML Platform domain tools
```

**After T7.5-020 (assistant integration complete)**:
```bash
# Run in parallel:
Task: T7.5-028 [P] make assistant-dummy-tools target
Task: T7.5-029 [P] make assistant-code-dummy-tools target
Task: T7.5-030 [P] make compare-modes-enterprise target
Task: T7.5-031-T7.5-035 [P] Unit tests
Task: T7.5-036-T7.5-040 [P] Integration tests
Task: T7.5-041 [P] Documentation
```

---

## Phase 8: User Story 6 - Multi-Agent System with Orchestration (Priority: P6)

**Goal**: Build multi-agent system with search, analytics, recommendation agents (Sub-feature 003f)

**Independent Test**: Ask multi-step query requiring multiple agents, verify correct routing

### Unit Tests for User Story 6

- [X] T153 [P] [US6] Create `chapter-2/tests/unit/test_agents.py` with tests for each agent type
- [X] T154 [P] [US6] Create `chapter-2/tests/unit/test_protocol.py` with A2A message protocol tests

### Integration Tests for User Story 6

- [X] T155 [P] [US6] Create `chapter-2/tests/integration/test_multi_agent.py` with end-to-end multi-step query tests

### A2A Protocol Implementation

- [X] T156 [US6] Create `chapter-2/src/a2a/__init__.py`
- [X] T157 [US6] Create `chapter-2/src/a2a/protocol.py` with QueryType enum and AgentMessage dataclass
- [X] T158 [US6] Create `chapter-2/src/a2a/server.py` with in-process message routing

### Specialized Agents Implementation

- [X] T159 [US6] Create `chapter-2/src/agents/search_agent.py` with SearchAgent class
- [X] T160 [US6] Implement search_agent with tools: search_books, get_book_details, locate_book, semantic_search
- [X] T161 [US6] Create `chapter-2/src/agents/analytics_agent.py` with AnalyticsAgent class
- [X] T162 [US6] Implement analytics_agent with tools: get_library_stats, list_by_category, list_by_status, execute_analytics
- [X] T163 [US6] Create `chapter-2/src/agents/recommendation_agent.py` with RecommendationAgent class
- [X] T164 [US6] Implement recommendation_agent with signal strength consideration ("avoid weak signal books")

### Orchestrator Implementation

- [X] T165 [US6] Create `chapter-2/src/agents/orchestrator_agent.py` with OrchestratorAgent class
- [X] T166 [US6] Implement query classification (search / analytics / multi-step)
- [X] T167 [US6] Implement agent discovery and routing
- [X] T168 [US6] Implement result aggregation from multiple agents
- [X] T169 [US6] Add routing decision display for transparency
- [X] T170 [US6] Add user-friendly error messages for agent failures

### CLI and Makefile for US6

- [X] T171 [US6] Add unified multi-agent CLI to orchestrator_agent.py
- [X] T172 [US6] Add `make multi-agent` target to start multi-agent system
- [X] T173 [US6] Add routing visualization in CLI output

### Documentation for US6

- [X] T174 [P] [US6] Create `chapter-2/docs/08-multi-agent-system.md` explaining multi-agent architecture

**Checkpoint**: User Story 6 complete - multi-agent system routes queries at 85%+ accuracy

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final quality improvements affecting all user stories

- [X] T175 [P] Run ruff linting on all chapter-2/ Python files and fix issues
- [X] T176 [P] Run mypy type checking on all chapter-2/ Python files and fix issues
- [X] T177 [P] Verify all docstrings follow Google style
- [X] T178 Add structured logging (JSON) across all modules
- [X] T179 Verify all edge cases have user-friendly error messages
- [X] T180 Run `make test` and ensure 80%+ unit test coverage
- [X] T181 Run quickstart.md validation - execute all steps and verify
- [X] T182 Update chapter-2/README.md with final instructions
- [X] T183 Create sample queries document for each sub-feature

**Checkpoint**: Phase 9 complete - all quality gates pass, documentation updated

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ───► Phase 2 (Foundational) ───► User Stories
                                                      │
                     ┌────────────────────────────────┤
                     │                                │
                     ▼                                ▼
              US1 (P1) ──────────────────────► US2 (P2)
              003a: Data                       003b: MCP
                     │                                │
                     ▼                                ▼
              US3 (P3) ──────────────────────► Phase 5.5
              003c: Tools                      Code Quality
                                                      │
                                                      ▼
              US4 (P4) ◄───────────────────── Phase 5.5 Done
              003d: Code Exec
                     │
                     ▼
              Phase 6.5 ◄──────────────────── US4 Done
              Dataset Enhancement              (Add Description)
                     │
                     ▼
              US5 (P5) ◄──────────────────── Phase 6.5 Done
              003e: RAG
                     │
                     ▼
              Phase 7.5 ◄─────────────────── US5 Done
              Enterprise Tool Scale            (100 Dummy Tools)
                     │
                     ▼
              US6 (P6) ◄──────────────────── Phase 7.5 Done
              003f: Multi-Agent
                     │
                     ▼
              Phase 9 (Polish)
```

### User Story & Phase Dependencies

| Story/Phase | Depends On | Can Parallelize With |
|-------------|------------|----------------------|
| US1 (003a) | Phase 2 only | None (foundational) |
| US2 (003b) | US1 (shared library layer) | None |
| US3 (003c) | US2 (same tool functions) | None |
| **Phase 5.5** | **US3 (003c) complete** | **None** |
| US4 (003d) | **Phase 5.5 complete** | None |
| **Phase 6.5** | **US4 (003d) complete** | **None** |
| US5 (003e) | **Phase 6.5 complete** (needs Description for RAG) | None |
| **Phase 7.5** | **US5 (003e) complete** | **None** |
| US6 (003f) | **Phase 7.5 complete** | None |

**Notes**:
- Phase 5.5 is a code quality phase inserted between US3 and US4. It adds git hooks and unified LLM client that US4+ will use.
- Phase 6.5 is a dataset enhancement phase inserted before US5 (RAG). It adds the Description column to enable rich textual content for semantic search.
- Phase 7.5 is an enterprise scale demonstration phase inserted before US6 (Multi-Agent). It adds 100 dummy tools to demonstrate code execution token efficiency.

### Within Each User Story

1. Unit tests first (can parallelize)
2. Integration tests (can parallelize with unit tests)
3. Core implementation (models → services → features)
4. CLI/Makefile targets
5. Documentation

### Parallel Opportunities (Within Story)

- All unit tests marked [P] can run in parallel
- All integration tests marked [P] can run in parallel
- Documentation tasks marked [P] can run in parallel with implementation
- Setup tasks T001-T006 can run in parallel where marked [P]

---

## Parallel Examples

### Phase 1 Setup (Parallel)

```bash
# Launch all parallelizable setup tasks:
Task: "Create chapter-2/Makefile with targets"
Task: "Create chapter-2/.env.example"
Task: "Create chapter-2/README.md"
```

### User Story 1 Tests (Parallel)

```bash
# Launch all US1 tests together:
Task: "Create chapter-2/tests/unit/test_domain.py"
Task: "Create chapter-2/tests/unit/test_repository.py"
Task: "Create chapter-2/tests/integration/test_data_load.py"
```

### User Story 1 Domain (Parallel)

```bash
# Launch domain class creation together:
Task: "Create BookStatus enum in domain.py"
Task: "Add Category enum to domain.py"
Task: "Add Location dataclass to domain.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (003a - Data Infrastructure)
4. **STOP and VALIDATE**: Load data, query books, verify 200 records
5. Deploy/demo if ready - learners can start data exercises

### Incremental Delivery

| Milestone | Stories Complete | Learner Value |
|-----------|------------------|---------------|
| MVP | US1 | Data infrastructure, queries working |
| +MCP | US1-US2 | MCP server connects to Claude |
| +Tools | US1-US3 | Library Assistant with token logging |
| +CodeExec | US1-US4 | Benchmark shows token reduction |
| +RAG | US1-US5 | Semantic search over catalog |
| Complete | US1-US6 | Full multi-agent system |

### Sub-Feature to GitHub Issue Mapping

| Story | Sub-Feature | GitHub Issue |
|-------|-------------|--------------|
| US1 | 003a: Library Data Infrastructure | #16 |
| US2 | 003b: Basic MCP Server | #17 |
| US3 | 003c: Traditional Tool Use | #18 |
| US4 | 003d: Code Execution Pattern | #19 |
| US5 | 003e: Advanced Tool Use & RAG | #20 |
| US6 | 003f: A2A Multi-Agent System | #21 |

---

## Summary

| Metric | Count |
|--------|-------|
| **Total Tasks** | 234 |
| **Setup (Phase 1)** | 6 |
| **Foundational (Phase 2)** | 5 |
| **US1 Tasks** | 30 |
| **US2 Tasks** | 13 |
| **US3 Tasks** | 13 |
| **Phase 5.5 (Code Quality)** | 33 |
| **US4 Tasks** | 17 |
| **Phase 6.5 (Dataset Enhancement)** | 34 |
| **US5 Tasks** | 25 |
| **Phase 7.5 (Enterprise Tool Scale)** | 51 |
| **US6 Tasks** | 22 |
| **Polish (Phase 9)** | 9 |
| **Parallelizable Tasks** | 82 |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [US#] label maps task to specific user story for traceability
- Each user story builds on previous (progressive learning path)
- Verify tests compile/fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- User-friendly error messages required per clarification session
- Sandbox whitelist: pandas, duckdb, numpy, matplotlib, seaborn
