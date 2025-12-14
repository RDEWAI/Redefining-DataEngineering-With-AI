# Tasks: Chapter 3 - AI Engineering with Library Management Data

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

All paths relative to `chapter-3/` directory:
- **Source**: `src/`
- **Tests**: `tests/unit/`, `tests/integration/`
- **Scripts**: `scripts/`
- **Docs**: `docs/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [X] T001 Create `chapter-3/` directory structure per plan.md
- [X] T002 Create `chapter-3/pyproject.toml` with UV-managed dependencies (duckdb, fastmcp, openai, sentence-transformers, pandas, numpy, matplotlib, seaborn, pytest)
- [X] T003 [P] Create `chapter-3/Makefile` with targets: dev-setup, data-copy, load-data, test, lint
- [X] T004 [P] Create `chapter-3/.env.example` with OPENROUTER_API_KEY, LLM_PROVIDER, DB_PATH
- [X] T005 [P] Create `chapter-3/README.md` with quickstart and overview
- [X] T006 Initialize `chapter-3/src/__init__.py` and all sub-package `__init__.py` files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 [P] Create `chapter-3/src/library/__init__.py` with package exports
- [X] T008 [P] Create `chapter-3/src/llm/__init__.py` with package exports
- [X] T009 [P] Create `chapter-3/tests/__init__.py` and test package structure
- [X] T010 Create `chapter-3/data/raw/library/` directory and verify CSV is accessible
- [X] T011 Create `chapter-3/data/duckdb/` directory for database files

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Library Data Setup and Query (Priority: P1) - MVP

**Goal**: Set up library data infrastructure with DuckDB and query capabilities (Sub-feature 003a)

**Independent Test**: Load CSV, query by category, verify 200 records accessible

### Unit Tests for User Story 1

- [X] T012 [P] [US1] Create `chapter-3/tests/unit/test_domain.py` with tests for Book, Location, Status, Category domain classes
- [X] T013 [P] [US1] Create `chapter-3/tests/unit/test_repository.py` with tests for BookRepository (search, filter, stats)

### Integration Tests for User Story 1

- [X] T014 [P] [US1] Create `chapter-3/tests/integration/test_data_load.py` with end-to-end CSV loading test

### Domain Layer Implementation

- [X] T015 [P] [US1] Create `chapter-3/src/library/domain.py` with BookStatus enum (Present, Missing, Checked Out)
- [X] T016 [P] [US1] Add Category enum to `chapter-3/src/library/domain.py` (Programming, History, Science, Fiction, Thriller)
- [X] T017 [P] [US1] Add Location dataclass to `chapter-3/src/library/domain.py` (cabinet, rack, row)
- [X] T018 [US1] Add Book dataclass to `chapter-3/src/library/domain.py` with has_weak_signal and is_available properties

### Repository Layer Implementation

- [X] T019 [US1] Create `chapter-3/src/library/repository.py` with BookRepository class and DuckDB connection
- [X] T020 [US1] Add search_books(query, category) method to BookRepository
- [X] T021 [US1] Add get_book_by_id(book_id) method to BookRepository
- [X] T022 [US1] Add list_by_category(category, status) method to BookRepository
- [X] T023 [US1] Add list_by_status(status, category) method to BookRepository
- [X] T024 [US1] Add get_weak_signal_books(threshold) method to BookRepository
- [X] T025 [US1] Add find_books_in_cabinet(cabinet, rack) method to BookRepository
- [X] T026 [US1] Add get_library_stats() method to BookRepository

### Tool Functions Implementation

- [X] T027 [US1] Create `chapter-3/src/library/tools.py` with standardized tool functions wrapping repository
- [X] T028 [US1] Implement all 8 tool functions in tools.py: search_books, get_book_details, check_availability, list_by_category, list_by_status, locate_book, find_books_in_cabinet, get_weak_signal_books

### Data Loading Script

- [X] T029 [US1] Create `chapter-3/scripts/load_library_csv_to_duckdb.py` following pattern from Feature 002
- [X] T030 [US1] Add schema creation with library.books table and all constraints
- [X] T031 [US1] Add CSV loading with validation and error handling
- [X] T032 [US1] Add user-friendly error messages for data loading failures

### LLM Abstraction Layer

- [X] T033 [P] [US1] Create `chapter-3/src/llm/base.py` with abstract LLMProvider interface (generate, stream_generate, count_tokens)
- [X] T034 [US1] Create `chapter-3/src/llm/openrouter_client.py` implementing LLMProvider for OpenRouter API
- [X] T035 [US1] Create `chapter-3/src/llm/ollama_client.py` implementing LLMProvider for local Ollama
- [X] T036 [US1] Add token counting implementation to both LLM clients

### Makefile Targets for US1

- [X] T037 [US1] Add `make load-data` target to chapter-3/Makefile
- [X] T038 [US1] Add `make verify-data` target to check 200 records loaded
- [X] T039 [US1] Add `make test-unit` target for unit tests

### Documentation for US1

- [X] T040 [P] [US1] Create `chapter-3/docs/01-data-infrastructure.md` with setup instructions
- [X] T041 [P] [US1] Create `chapter-3/docs/02-llm-abstraction.md` with provider configuration

**Checkpoint**: User Story 1 complete - data infrastructure works independently

---

## Phase 4: User Story 2 - MCP Server for Library Tools (Priority: P2)

**Goal**: Expose library operations as MCP tools using FastMCP (Sub-feature 003b)

**Independent Test**: Connect Claude Desktop to MCP server, execute search_books tool

### Unit Tests for User Story 2

- [X] T042 [P] [US2] Create `chapter-3/tests/unit/test_mcp_tools.py` with tests for MCP tool schema generation

### Integration Tests for User Story 2

- [X] T043 [P] [US2] Create `chapter-3/tests/integration/test_mcp_server.py` with in-memory MCP transport tests

### MCP Server Implementation

- [X] T044 [US2] Create `chapter-3/src/mcp_servers/__init__.py`
- [X] T045 [US2] Create `chapter-3/src/mcp_servers/library_server.py` with FastMCP server initialization
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

- [X] T054 [P] [US2] Create `chapter-3/docs/03-mcp-basics.md` with MCP concepts and setup

**Checkpoint**: User Story 2 complete - MCP server works with Claude Desktop

---

## Phase 5: User Story 3 - Traditional Tool Use with JSON Schema (Priority: P3)

**Goal**: Build Library Assistant with traditional JSON schema tools for baseline token measurement (Sub-feature 003c)

**Independent Test**: Ask "What programming books are available?" and verify tool calls and token logging

### Unit Tests for User Story 3

- [ ] T055 [P] [US3] Create `chapter-3/tests/unit/test_tools.py` with tests for JSON schema tool definitions

### Integration Tests for User Story 3

- [ ] T056 [P] [US3] Create `chapter-3/tests/integration/test_assistant.py` with multi-turn conversation tests

### Library Assistant Implementation

- [ ] T057 [US3] Create `chapter-3/src/agents/__init__.py`
- [ ] T058 [US3] Create `chapter-3/src/agents/library_assistant.py` with LibraryAssistant class
- [ ] T059 [US3] Implement JSON schema tool definitions matching contracts/llm-tools.json
- [ ] T060 [US3] Implement tool execution loop with tool_calls handling
- [ ] T061 [US3] Add multi-turn conversation support with message history
- [ ] T062 [US3] Add token usage logging per query for baseline measurement
- [ ] T063 [US3] Add support for both OpenRouter and Ollama backends
- [ ] T064 [US3] Add user-friendly error messages for tool failures

### CLI Interface for US3

- [ ] T065 [US3] Add interactive REPL to library_assistant.py for CLI usage
- [ ] T066 [US3] Add `make assistant` target to start Library Assistant CLI

### Documentation for US3

- [ ] T067 [P] [US3] Create `chapter-3/docs/04-traditional-tools.md` comparing MCP vs traditional patterns

**Checkpoint**: User Story 3 complete - Library Assistant works with token logging

---

## Phase 6: User Story 4 - Code Execution for Token Efficiency (Priority: P4)

**Goal**: Implement sandboxed code execution and benchmark token reduction (Sub-feature 003d)

**Independent Test**: Run benchmark query, verify 30%+ token reduction with code execution

### Unit Tests for User Story 4

- [ ] T068 [P] [US4] Create `chapter-3/tests/unit/test_sandbox.py` with security constraint tests (import whitelist, timeout, memory)

### Integration Tests for User Story 4

- [ ] T069 [P] [US4] Create `chapter-3/tests/integration/test_code_execution.py` with end-to-end code execution tests

### Sandbox Implementation

- [ ] T070 [US4] Create `chapter-3/src/code_execution/__init__.py`
- [ ] T071 [US4] Create `chapter-3/src/code_execution/sandbox.py` with CodeSandbox class
- [ ] T072 [US4] Implement subprocess isolation with resource limits (30s timeout, memory limit)
- [ ] T073 [US4] Implement import whitelist enforcement (pandas, duckdb, numpy, matplotlib, seaborn)
- [ ] T074 [US4] Add user-friendly error messages for timeout and out-of-memory conditions

### Tool-to-API Transformer

- [ ] T075 [US4] Create `chapter-3/src/code_execution/tool_api.py` with tool-to-code wrapper generator
- [ ] T076 [US4] Generate Python wrapper code for each library tool
- [ ] T077 [US4] Add type hints and docstrings for LLM understanding

### Benchmark Implementation

- [ ] T078 [US4] Create `chapter-3/benchmarks/token_comparison.py` with TokenBenchmark class
- [ ] T079 [US4] Implement fixed benchmark query: "Show top 5 categories by missing books with average signal strength"
- [ ] T080 [US4] Implement traditional tools measurement (multiple tool calls)
- [ ] T081 [US4] Implement code execution measurement (single code generation)
- [ ] T082 [US4] Add comparison output: token count, latency, accuracy
- [ ] T083 [US4] Add `make benchmark` target to run token comparison

### Documentation for US4

- [ ] T084 [P] [US4] Create `chapter-3/docs/05-code-execution.md` documenting token reduction results

**Checkpoint**: User Story 4 complete - benchmark shows measurable token reduction

---

## Phase 7: User Story 5 - Semantic Search with RAG (Priority: P5)

**Goal**: Implement RAG with DuckDB VSS for semantic book search (Sub-feature 003e)

**Independent Test**: Search "that book about time travel" and receive relevant fiction/science books

### Unit Tests for User Story 5

- [ ] T085 [P] [US5] Create `chapter-3/tests/unit/test_embeddings.py` with embedding generation tests
- [ ] T086 [P] [US5] Create `chapter-3/tests/unit/test_tool_registry.py` with tool registry tests

### Integration Tests for User Story 5

- [ ] T087 [P] [US5] Create `chapter-3/tests/integration/test_semantic_search.py` with retrieval accuracy tests

### RAG Implementation

- [ ] T088 [US5] Create `chapter-3/src/rag/__init__.py`
- [ ] T089 [US5] Create `chapter-3/src/rag/embeddings.py` with EmbeddingGenerator class using sentence-transformers
- [ ] T090 [US5] Implement embed_text(text) and embed_books(books) methods
- [ ] T091 [US5] Create `chapter-3/src/rag/vector_store.py` with DuckDBVectorStore class
- [ ] T092 [US5] Implement VSS extension setup and book_embeddings table creation
- [ ] T093 [US5] Implement semantic_search(query, top_k) using array_cosine_distance
- [ ] T094 [US5] Add HNSW index creation after data population
- [ ] T095 [US5] Add user-friendly error messages for empty search results

### Tool Registry Implementation

- [ ] T096 [US5] Create `chapter-3/src/tools/__init__.py`
- [ ] T097 [US5] Create `chapter-3/src/tools/tool_registry.py` with ToolRegistry class
- [ ] T098 [US5] Implement register_tool(tool) with metadata (name, description, schema, capabilities)
- [ ] T099 [US5] Implement get_tool(name) for direct lookup
- [ ] T100 [US5] Implement list_tools(capability) for capability-based filtering

### Tool Search Implementation

- [ ] T101 [US5] Create `chapter-3/src/tools/tool_search.py` with ToolSearch class
- [ ] T102 [US5] Implement search_by_name(query) for name-based lookup
- [ ] T103 [US5] Implement search_by_description(query) using embedding similarity

### Data Analysis Agent

- [ ] T104 [US5] Create `chapter-3/src/agents/data_analysis_agent.py` with DataAnalysisAgent class
- [ ] T105 [US5] Integrate code execution for complex analytics
- [ ] T106 [US5] Integrate semantic search for book discovery

### CLI and Makefile for US5

- [ ] T107 [US5] Add `make generate-embeddings` target to generate book embeddings
- [ ] T108 [US5] Add `make semantic-search` target for interactive semantic search

### Documentation for US5

- [ ] T109 [P] [US5] Create `chapter-3/docs/06-advanced-tools-rag.md` explaining RAG scope decisions

**Checkpoint**: User Story 5 complete - semantic search works with 70%+ top-3 precision

---

## Phase 8: User Story 6 - Multi-Agent System with Orchestration (Priority: P6)

**Goal**: Build multi-agent system with search, analytics, recommendation agents (Sub-feature 003f)

**Independent Test**: Ask multi-step query requiring multiple agents, verify correct routing

### Unit Tests for User Story 6

- [ ] T110 [P] [US6] Create `chapter-3/tests/unit/test_agents.py` with tests for each agent type
- [ ] T111 [P] [US6] Create `chapter-3/tests/unit/test_protocol.py` with A2A message protocol tests

### Integration Tests for User Story 6

- [ ] T112 [P] [US6] Create `chapter-3/tests/integration/test_multi_agent.py` with end-to-end multi-step query tests

### A2A Protocol Implementation

- [ ] T113 [US6] Create `chapter-3/src/a2a/__init__.py`
- [ ] T114 [US6] Create `chapter-3/src/a2a/protocol.py` with QueryType enum and AgentMessage dataclass
- [ ] T115 [US6] Create `chapter-3/src/a2a/server.py` with in-process message routing

### Specialized Agents Implementation

- [ ] T116 [US6] Create `chapter-3/src/agents/search_agent.py` with SearchAgent class
- [ ] T117 [US6] Implement search_agent with tools: search_books, get_book_details, locate_book, semantic_search
- [ ] T118 [US6] Create `chapter-3/src/agents/analytics_agent.py` with AnalyticsAgent class
- [ ] T119 [US6] Implement analytics_agent with tools: get_library_stats, list_by_category, list_by_status, execute_analytics
- [ ] T120 [US6] Create `chapter-3/src/agents/recommendation_agent.py` with RecommendationAgent class
- [ ] T121 [US6] Implement recommendation_agent with signal strength consideration ("avoid weak signal books")

### Orchestrator Implementation

- [ ] T122 [US6] Create `chapter-3/src/agents/orchestrator_agent.py` with OrchestratorAgent class
- [ ] T123 [US6] Implement query classification (search / analytics / multi-step)
- [ ] T124 [US6] Implement agent discovery and routing
- [ ] T125 [US6] Implement result aggregation from multiple agents
- [ ] T126 [US6] Add routing decision display for transparency
- [ ] T127 [US6] Add user-friendly error messages for agent failures

### CLI and Makefile for US6

- [ ] T128 [US6] Add unified multi-agent CLI to orchestrator_agent.py
- [ ] T129 [US6] Add `make multi-agent` target to start multi-agent system
- [ ] T130 [US6] Add routing visualization in CLI output

### Documentation for US6

- [ ] T131 [P] [US6] Create `chapter-3/docs/07-a2a-multi-agent.md` tying to Google A2A concepts

**Checkpoint**: User Story 6 complete - multi-agent system routes queries at 85%+ accuracy

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final quality improvements affecting all user stories

- [ ] T132 [P] Run ruff linting on all chapter-3/ Python files and fix issues
- [ ] T133 [P] Run mypy type checking on all chapter-3/ Python files and fix issues
- [ ] T134 [P] Verify all docstrings follow Google style
- [ ] T135 Add structured logging (JSON) across all modules
- [ ] T136 Verify all edge cases have user-friendly error messages
- [ ] T137 Run `make test` and ensure 80%+ unit test coverage
- [ ] T138 Run quickstart.md validation - execute all steps and verify
- [ ] T139 Update chapter-3/README.md with final instructions
- [ ] T140 Create sample queries document for each sub-feature

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
              US3 (P3) ──────────────────────► US4 (P4)
              003c: Tools                      003d: Code Exec
                     │                                │
                     ▼                                ▼
              US5 (P5) ──────────────────────► US6 (P6)
              003e: RAG                        003f: Multi-Agent
                                                      │
                                                      ▼
                                              Phase 9 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Parallelize With |
|-------|------------|----------------------|
| US1 (003a) | Phase 2 only | None (foundational) |
| US2 (003b) | US1 (shared library layer) | None |
| US3 (003c) | US2 (same tool functions) | None |
| US4 (003d) | US3 (baseline comparison) | None |
| US5 (003e) | US4 (code execution pattern) | None |
| US6 (003f) | US5 (RAG + tool patterns) | None |

**Note**: This is a progressive learning path - each story builds on the previous. Stories CANNOT be parallelized across sub-features.

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
Task: "Create chapter-3/Makefile with targets"
Task: "Create chapter-3/.env.example"
Task: "Create chapter-3/README.md"
```

### User Story 1 Tests (Parallel)

```bash
# Launch all US1 tests together:
Task: "Create chapter-3/tests/unit/test_domain.py"
Task: "Create chapter-3/tests/unit/test_repository.py"
Task: "Create chapter-3/tests/integration/test_data_load.py"
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
| **Total Tasks** | 140 |
| **Setup (Phase 1)** | 6 |
| **Foundational (Phase 2)** | 5 |
| **US1 Tasks** | 30 |
| **US2 Tasks** | 13 |
| **US3 Tasks** | 13 |
| **US4 Tasks** | 17 |
| **US5 Tasks** | 25 |
| **US6 Tasks** | 22 |
| **Polish (Phase 9)** | 9 |
| **Parallelizable Tasks** | 47 |

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
