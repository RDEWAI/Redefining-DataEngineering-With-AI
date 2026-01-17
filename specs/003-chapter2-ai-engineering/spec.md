# Feature Specification: Chapter 2 - AI Engineering with Library Management Data

**Feature Branch**: `003-chapter3-ai-engineering`
**Created**: 2025-12-13
**Status**: Draft
**Input**: User description: "Chapter 2: AI Engineering with Library Management Data - Epic covering MCP, tool use, code execution, RAG, and multi-agent systems"
**GitHub Epic**: #15
**Sub-Issues**: #16 (003a), #17 (003b), #18 (003c), #19 (003d), #20 (003e), #21 (003f)

## Clarifications

### Session 2025-12-14

- Q: What imports are allowed in the code execution sandbox? → A: Data analysis extended set (pandas, duckdb, numpy, matplotlib, seaborn)
- Q: How should the system handle edge cases and failures? → A: User-friendly error messages (explain what failed in plain language)

## Overview

This epic introduces AI Engineering concepts through progressive, hands-on examples using a Library Management IoT dataset. Learners will build from foundational data infrastructure through increasingly sophisticated AI patterns: Model Context Protocol (MCP), traditional tool use, code execution for token efficiency, RAG with semantic search, and culminating in multi-agent orchestration.

### Dataset

- **Source**: Kaggle Library Management dataset with IoT RFID tracking (enhanced with descriptions)
- **Size**: 200 books
- **Attributes**: Book_ID, Title, Author, Description, Category, Cabinet, Rack, Row, Signal_Strength, Timestamp, Status
- **Description**: 50-100 word book summaries for RAG semantic search
- **Status Values**: Present, Missing, Checked Out
- **Categories**: Programming, History, Science, Fiction, Thriller

### Domain Invariants

| Invariant          | Definition                                             |
| ------------------ | ------------------------------------------------------ |
| **Weak Signal**    | Signal_Strength < -55 dBm                              |
| **Missing Book**   | Status == "Missing" or not seen for >30 minutes        |
| **Location Anomaly** | Same Book_ID in different Cabinet within 5-minute window |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Library Data Setup and Query (Priority: P1)

As a learner, I want to set up the library data infrastructure and query books from a database so that I have a reproducible foundation for all subsequent AI engineering exercises.

**Why this priority**: This is the foundational layer - without reproducible data and a working query layer, no other features can be demonstrated or tested. Everything builds on this.

**Independent Test**: Can be fully tested by loading the CSV data, querying for books by category, and verifying all 200 records are accessible. Delivers immediate value as a working data layer.

**Acceptance Scenarios**:

1. **Given** a fresh environment with the library CSV file, **When** I run the data loading process, **Then** all 200 book records are persisted and queryable in the database.
2. **Given** the database is loaded, **When** I search for books by category "Programming", **Then** I receive all books matching that category with their full details.
3. **Given** the database is loaded, **When** I query for book availability, **Then** I see accurate status (Present/Missing/Checked Out) and physical location.

---

### User Story 2 - MCP Server for Library Tools (Priority: P2)

As a learner, I want to expose library data operations as MCP tools so that I understand how Model Context Protocol standardizes tool integration and enables plug-and-play AI tool connections.

**Why this priority**: MCP is the industry-standard protocol for AI tool integration. Understanding it unlocks interoperability with Claude Desktop, Claude CLI, and other MCP-compatible clients.

**Independent Test**: Can be tested by connecting an MCP client (e.g., Claude Desktop) to the library server and successfully executing tool calls like book search and availability check.

**Acceptance Scenarios**:

1. **Given** the MCP server is running, **When** I connect via an MCP client, **Then** I can discover all available library tools with their schemas.
2. **Given** I invoke the `search_books` tool with query "Python", **When** the tool executes, **Then** I receive matching books with title, author, category, and availability.
3. **Given** I invoke the `get_weak_signal_books` tool, **When** there are books with signal strength below threshold, **Then** I receive a list for RFID maintenance.

---

### User Story 3 - Traditional Tool Use with JSON Schema (Priority: P3)

As a learner, I want to build a Library Assistant using traditional JSON schema tool definitions so that I can measure baseline token usage and understand the standard tool-calling flow before optimizing it.

**Why this priority**: Traditional tool use establishes the baseline against which code execution improvements are measured. Without this baseline, the benefits of advanced patterns cannot be demonstrated.

**Independent Test**: Can be tested by asking the assistant natural language questions about books and measuring the token count for multi-tool conversations.

**Acceptance Scenarios**:

1. **Given** the Library Assistant is running, **When** I ask "What programming books are available?", **Then** the assistant uses appropriate tools and returns relevant results.
2. **Given** a multi-turn conversation, **When** I ask follow-up questions about specific books, **Then** the assistant maintains context and calls tools appropriately.
3. **Given** any query interaction, **When** the response is generated, **Then** the system logs token usage for later comparison.

---

### User Story 4 - Code Execution for Token Efficiency (Priority: P4)

As a learner, I want to compare code execution patterns against traditional tool use so that I can understand when and why code execution reduces token consumption significantly.

**Why this priority**: This demonstrates a key optimization technique from Anthropic's engineering practices, showing concrete token savings through measurement.

**Independent Test**: Can be tested by running the same complex query through both approaches and comparing token counts in the benchmark output.

**Acceptance Scenarios**:

1. **Given** a complex analytics query (e.g., "Show top 5 categories by missing books with average signal strength"), **When** executed via traditional tools, **Then** the token count is recorded.
2. **Given** the same query, **When** executed via code execution, **Then** the token count is recorded and is measurably lower than traditional tools.
3. **Given** generated code, **When** executed in the sandbox, **Then** it runs within security constraints (whitelist imports, execution timeout, memory limits).

---

### User Story 5 - Semantic Search with RAG (Priority: P5)

As a learner, I want to perform semantic searches over the book catalog so that I can find books using natural language descriptions even when exact keywords don't match.

**Why this priority**: RAG enables more natural user interactions and demonstrates a critical AI pattern. Builds on prior infrastructure.

**Independent Test**: Can be tested by searching for "that book about time travel" and receiving relevant fiction/science books even without exact title matches.

**Acceptance Scenarios**:

1. **Given** book embeddings are generated for titles, authors, and categories, **When** I search semantically, **Then** results are ranked by relevance.
2. **Given** a vague query like "books about adventure", **When** the RAG system processes it, **Then** I receive thematically relevant results across categories.
3. **Given** the tool registry, **When** I search for tools by capability description, **Then** I discover relevant tools dynamically.

---

### User Story 6 - Multi-Agent System with Orchestration (Priority: P6)

As a learner, I want to see specialized agents (search, analytics, recommendation) work together under an orchestrator so that I understand multi-agent system design and when to apply it.

**Why this priority**: This is the capstone experience demonstrating how to compose simpler AI components into sophisticated systems.

**Independent Test**: Can be tested by asking complex queries that require multiple agent types and verifying the orchestrator correctly routes and aggregates responses.

**Acceptance Scenarios**:

1. **Given** a search query, **When** the orchestrator receives it, **Then** it routes to the search agent and returns book results.
2. **Given** an analytics query like "How many books are missing?", **When** processed, **Then** the orchestrator routes to the analytics agent which uses code execution.
3. **Given** a multi-step query like "Find available programming books and recommend one with good signal strength", **When** processed, **Then** the orchestrator coordinates search, filters by availability, and applies recommendation logic.

---

### Edge Cases

**Handling Strategy**: All edge cases produce user-friendly error messages explaining what failed in plain language, supporting the educational goals of the project.

- **Empty database or data loading failure**: Display message indicating no data available and prompt to run the data loading process
- **Malformed queries or unsupported tool requests**: Return clear explanation of what was invalid and suggest correct usage
- **MCP connection drops during tool call**: Inform user of connection loss and suggest reconnection steps
- **Code execution timeout or out-of-memory**: Explain resource limit exceeded and suggest simplifying the query
- **Semantic search returns no results above threshold**: Indicate no matches found and suggest alternative search terms
- **Orchestrator agent failures or conflicting responses**: Report which agent failed and provide partial results if available
- **Book location data inconsistent (location anomaly)**: Flag the anomaly to the user as potential data quality issue

## Requirements *(mandatory)*

### Functional Requirements

#### 003a: Library Data Infrastructure

- **FR-001**: System MUST load all 200 book records from the CSV file into a queryable database
- **FR-002**: System MUST create a schema that preserves all book attributes (Book_ID, Title, Author, Description, Category, Cabinet, Rack, Row, Signal_Strength, Timestamp, Status)
- **FR-003**: System MUST provide a repository layer for common queries (search, filter by category, filter by status, location lookup)
- **FR-004**: System MUST provide an LLM abstraction layer supporting multiple providers (cloud API and local models)
- **FR-005**: System MUST implement token counting for benchmark comparisons

#### 003b: Basic MCP Server

- **FR-006**: System MUST expose library operations as MCP tools with proper JSON schema definitions
- **FR-007**: System MUST implement MCP resources for statistics, missing books list, and location map
- **FR-008**: System MUST implement MCP prompts for common query patterns
- **FR-009**: System MUST be configurable for use with MCP-compatible clients

#### 003c: Traditional Tool Use

- **FR-010**: System MUST implement a Library Assistant with JSON schema tool definitions
- **FR-011**: System MUST support multi-turn conversations with context preservation
- **FR-012**: System MUST log token usage per query for baseline measurement
- **FR-013**: System MUST support both cloud API and local model backends

#### 003d: Code Execution Pattern

- **FR-014**: System MUST execute generated code in a sandboxed environment
- **FR-015**: System MUST enforce security constraints: import whitelist (pandas, duckdb, numpy, matplotlib, seaborn), 30-second execution timeout, and memory limits
- **FR-016**: System MUST transform MCP tools into importable code-level APIs
- **FR-017**: System MUST provide benchmark comparing token usage between traditional and code execution approaches

#### 003e: Advanced Tool Use & RAG

- **FR-018**: System MUST maintain a tool registry with metadata (name, description, schema, capabilities)
- **FR-019**: System MUST support dynamic tool discovery by name and capability similarity
- **FR-020**: System MUST generate embeddings for book metadata (title, author, category)
- **FR-021**: System MUST perform semantic search using vector similarity
- **FR-022**: System MUST differentiate between semantic search fields (title, author, category) and structured query fields (status, location, signal_strength)

#### 003f: A2A Multi-Agent System

- **FR-023**: System MUST implement specialized agents: search, analytics, and recommendation
- **FR-024**: System MUST implement an orchestrator agent that classifies and routes queries
- **FR-025**: System MUST support multi-step query workflows across agents
- **FR-026**: System MUST aggregate results from multiple agents into coherent responses
- **FR-027**: System MUST display agent routing decisions to users for transparency

### Key Entities

- **Book**: Library item with ID, title, author, description (50-100 word summary for RAG), category, physical location (cabinet/rack/row), RFID signal strength, timestamp, and availability status
- **Location**: Physical position in library defined by Cabinet, Rack, and Row coordinates
- **Status**: Book availability state (Present, Missing, Checked Out)
- **Tool**: Registered operation with name, description, input schema, and capability tags
- **Agent**: Specialized AI component with defined responsibilities and tool access
- **Query**: User request that may require single or multiple agent involvement

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Data loading completes successfully with all 200 book records queryable
- **SC-002**: MCP server exposes at least 8 distinct tools discoverable by MCP clients
- **SC-003**: Library Assistant correctly handles at least 90% of test queries in the benchmark suite
- **SC-004**: Code execution approach demonstrates at least 30% token reduction compared to traditional tool use for complex analytics queries
- **SC-005**: Semantic search returns relevant results (top-3 precision > 70%) for natural language book queries
- **SC-006**: Multi-agent system correctly routes queries to appropriate agents at least 85% of the time
- **SC-007**: All code execution completes within the 30-second sandbox timeout
- **SC-008**: Learners can complete each sub-feature independently, with each building on the previous

## Dependencies

### External Dependencies

- Kaggle Library Management dataset (data/chapter-2/library_dataset_random.csv)
- LLM provider access (cloud API or local model runtime)
- Embedding model for vector generation

### Internal Dependencies

| Sub-Feature | Depends On |
| ----------- | ---------- |
| 003a        | Feature 002 (DuckDB CSV Loader pattern) |
| 003b        | 003a (shared library layer) |
| 003c        | 003b (same tool functions as MCP) |
| 003d        | 003c (baseline for comparison) |
| 003e        | 003d (code execution pattern) |
| 003f        | 003e (RAG + tool patterns) |

## Assumptions

1. Learners have basic Python knowledge and familiarity with data concepts
2. The Kaggle dataset is available and matches the expected schema
3. LLM providers (cloud or local) are accessible during exercises
4. Docker is available for reproducible data container builds
5. The existing DuckDB and UV package manager patterns from Feature 002 are followed
