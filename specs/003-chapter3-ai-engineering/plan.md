# Implementation Plan: Chapter 3 - AI Engineering with Library Management Data

**Branch**: `003-chapter3-ai-engineering` | **Date**: 2025-12-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-chapter3-ai-engineering/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This feature implements a comprehensive AI Engineering learning path using a Library Management IoT dataset. The implementation progresses through six user stories: (1) Data Infrastructure, (2) MCP Server, (3) Traditional Tool Use, (4) Code Execution for Token Efficiency, (5) Semantic Search with RAG, and (6) Multi-Agent Orchestration. The primary technical approach uses DuckDB for data storage, Python with UV for dependency management, and follows the local-first development model established in Feature 002.

**Pre-Phase 7 Enhancement**: Before implementing Phase 7 (RAG), we will enhance the library dataset by adding a `Description` column containing rich textual summaries of each book. This enhancement is critical for RAG effectiveness, as semantic search requires substantial text content to generate meaningful embeddings and enable natural language queries. This change will require updates to code in Phases 3-6 that are already implemented.

## Technical Context

**Language/Version**: Python 3.10-3.12 (aligned with existing project from Feature 002)
**Primary Dependencies**: DuckDB 1.1.3, sentence-transformers (for embeddings), anthropic-sdk, mcp-sdk
**Storage**: DuckDB at `chapter-3/data/duckdb/chapter3.db` with `library` schema
**Testing**: pytest with unit/integration/contract test structure
**Target Platform**: Linux/macOS development environment, UV-managed virtual environment
**Project Type**: Single project (data engineering + AI agents under `chapter-3/`)
**Performance Goals**:
  - RAG semantic search: < 500ms p95 for top-K retrieval
  - Code execution: < 30 seconds timeout per sandbox execution
  - Token efficiency: 30%+ reduction for complex analytics vs traditional tool use
**Constraints**:
  - Sandbox security: whitelisted imports only (pandas, duckdb, numpy, matplotlib, seaborn)
  - Education-focused: all errors must be user-friendly with actionable guidance
  - Independent testability: each user story deliverable standalone
**Scale/Scope**:
  - 200 books in dataset
  - 8+ MCP tools
  - 3 specialized agents + 1 orchestrator
  - 6 progressive user stories with ~130 tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Quality Gates Evaluation

✅ **Code Quality & Maintainability**:
- Python with type hints, linting (ruff), PEP 8 compliance
- Google-style docstrings for all public APIs
- Cyclomatic complexity monitored per function

✅ **Testing Standards**:
- Unit tests: 80%+ coverage target
- Integration tests: verify component interactions
- Contract tests: validate tool schemas and data quality
- All tests runnable via `uv run pytest` and `make test`

✅ **User Experience Consistency**:
- CLI tools follow standard conventions
- Structured logging (JSON format)
- User-friendly error messages (no raw stack traces)
- Comprehensive documentation with quickstart guides

✅ **Performance & Scalability**:
- Benchmarking for token usage comparison (traditional vs code execution)
- Memory limits enforced in code sandbox
- Production-scale data testing (200 records validated)

✅ **Reproducibility & Environment Consistency**:
- UV-based dependency management with `pyproject.toml` and `uv.lock`
- Local-first development (no Docker dependency)
- `make dev-setup` for environment reproducibility
- Configuration as code (no manual setup)

**Violations Requiring Justification**: None. All constitutional requirements are met.

## Pre-Phase 7: Dataset Enhancement with Description Column

### Rationale

**Problem**: The current library dataset (`library_dataset_random.csv`) contains only structured metadata (Title, Author, Category, Location, Signal_Strength, Status). For effective RAG implementation in Phase 7, we need rich textual content that can be embedded and semantically searched.

**Solution**: Add a `Description` column containing 2-3 sentence book summaries (50-100 words) that:
1. Provide semantic context for vector embeddings
2. Enable natural language queries like "books about time travel" or "stories with mystery and adventure"
3. Demonstrate RAG's value over keyword-only search
4. Support educational goals by showing clear semantic similarity matching

**Impact on Previous Phases**: Since Phases 3-6 are already implemented, we must update:
- Domain model (Book dataclass)
- Database schema and CSV loader
- Repository queries (6 SELECT statements)
- Test fixtures
- Documentation

### Current Dataset Structure

**Columns (10)**: Book_ID, Title, Author, Category, Cabinet, Rack, Row, Signal_Strength, Timestamp, Status

**Enhanced Structure (11)**: Book_ID, Title, Author, **Description**, Category, Cabinet, Rack, Row, Signal_Strength, Timestamp, Status

### Files Requiring Updates

#### 1. Data Model (`chapter-3/src/library/domain.py`)

**Book dataclass (lines 69-135)**:
- Add `description: str` field after `author`
- Update `to_dict()` method to include `"description": self.description`
- Update `from_row()` classmethod to unpack description from tuple (position 3, after author)
- Update `from_dict()` classmethod to handle `description` key

**Example change**:
```python
@dataclass(frozen=True)
class Book:
    book_id: str
    title: str
    author: str
    description: str  # NEW FIELD
    category: Category
    location: Location
    signal_strength: float
    timestamp: datetime
    status: BookStatus
```

#### 2. CSV Loader (`chapter-3/scripts/load_library_csv_to_duckdb.py`)

**create_table() function (lines 35-56)**:
- Add `description VARCHAR NOT NULL` to schema (after author)

**load_csv() function (lines 70-109)**:
- Update INSERT statement to map CSV `Description` to database `description`

**validate_data() function (lines 112-167)**:
- Add "description" to NULL value checks
- Optional: Add length validation (50-300 characters)

**Example change**:
```sql
CREATE TABLE library.books (
    book_id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    author VARCHAR NOT NULL,
    description VARCHAR NOT NULL,  -- NEW COLUMN
    category VARCHAR NOT NULL CHECK (category IN ('Programming', 'History', 'Science', 'Fiction', 'Thriller')),
    ...
)
```

#### 3. Repository (`chapter-3/src/library/repository.py`)

**All SELECT queries need description column added**:
- `search_books()` (lines 96-99)
- `get_book_by_id()` (lines 124-126)
- `list_by_category()` (lines 149-151)
- `list_by_status()` (lines 179-181)
- `get_weak_signal_books()` (lines 207-209)
- `find_books_in_cabinet()` (lines 231-233)

**Example change**:
```python
sql = """
    SELECT book_id, title, author, description, category, cabinet, rack, row,
           signal_strength, timestamp, status
    FROM library.books
    WHERE ...
"""
```

#### 4. Tools (`chapter-3/src/library/tools.py`)

**No changes required!** ✅

Tools use `book.to_dict()` which will automatically include description once the domain model is updated. This demonstrates good encapsulation.

#### 5. Tests

**Unit tests**:
- `tests/unit/test_domain.py`: Update Book fixtures to include description
- `tests/unit/test_repository.py`: Update test data with descriptions
- `tests/unit/test_tools.py`: Add assertions for description in responses

**Integration tests**:
- `tests/integration/test_data_load.py`: Verify description column exists, no NULLs, length constraints

#### 6. Data File

**`chapter-3/data/raw/library/library_dataset_random.csv`**:
- Add `Description` column (insert after Author, before Category)
- Generate 200 unique, contextually appropriate descriptions

#### 7. Documentation

- `data-model.md`: Update Book entity to include Description field
- `spec.md`: Update FR-002 to list Description attribute
- `quickstart.md`: Update code examples to show Description field

### Implementation Plan

#### Task T000: Add Description Column (Pre-Phase 7)

**Sub-tasks**:

**T000.1**: Generate book descriptions and update CSV
- Create `chapter-3/scripts/generate_descriptions.py`
- Read existing CSV (200 books)
- Generate contextually appropriate descriptions per category:
  - Programming: Technical guides and tutorials
  - Fiction: Plot summaries with characters and themes
  - Thriller: Suspenseful plots with hooks
  - Science: Research topics and findings
  - History: Historical periods and significance
- Write enhanced CSV with Description column (position 4, after Author)
- Validate: 200 books, no data loss, descriptions 50-100 words

**T000.2**: Update domain model
- Edit `chapter-3/src/library/domain.py`
- Add `description: str` field to Book dataclass
- Update `to_dict()`, `from_row()`, `from_dict()` methods
- Run unit tests: `uv run pytest tests/unit/test_domain.py`

**T000.3**: Update CSV loader and database schema
- Edit `chapter-3/scripts/load_library_csv_to_duckdb.py`
- Add description column to CREATE TABLE statement
- Update INSERT statement to map Description from CSV
- Add description to validation checks
- Test: Run loader and verify description column exists

**T000.4**: Update repository queries
- Edit `chapter-3/src/library/repository.py`
- Add `description` to all 6 SELECT statements
- Run repository tests: `uv run pytest tests/unit/test_repository.py`

**T000.5**: Update test fixtures
- Edit `tests/unit/test_domain.py`: Add description to Book fixtures
- Edit `tests/unit/test_repository.py`: Add description to test data
- Edit `tests/integration/test_data_load.py`: Add description validation
- Run all unit tests: `uv run pytest tests/unit/ -v`

**T000.6**: Update integration tests
- Edit `tests/integration/test_data_load.py`
- Add assertions for description column
- Validate no NULL descriptions
- Check length constraints (50-300 characters)
- Run integration tests: `uv run pytest tests/integration/ -v`

**T000.7**: Update documentation
- Edit `specs/003-chapter3-ai-engineering/data-model.md`
- Edit `specs/003-chapter3-ai-engineering/spec.md` (FR-002)
- Update code examples in `quickstart.md`

**T000.8**: Validate end-to-end
- Delete existing database: `rm chapter-3/data/duckdb/chapter3.db`
- Run CSV loader: `python chapter-3/scripts/load_library_csv_to_duckdb.py`
- Run all tests: `uv run pytest tests/ -v`
- Verify 200 books with descriptions loaded
- Spot-check sample descriptions for quality

### Description Generation Strategy

**Approach**: Template-based generation with LLM assistance for quality and diversity

**Templates by Category**:

**Programming** (50 books):
- Pattern: "A comprehensive guide to {topic} covering {concepts}. Readers will learn {skills} through practical examples and real-world applications. Ideal for {audience}."
- Example: "A comprehensive guide to Python data structures covering lists, dictionaries, and sets. Readers will learn algorithmic thinking through practical examples and real-world applications. Ideal for intermediate developers."

**Fiction** (50 books):
- Pattern: "An epic tale of {protagonist} who {plot_hook}. Set in {setting}, this story explores themes of {themes} as {character} navigates {conflict}."
- Example: "An epic tale of a young adventurer who discovers a hidden realm beyond reality. Set in a world where dreams and reality merge, this story explores themes of identity and courage as the hero navigates between two worlds."

**Thriller** (50 books):
- Pattern: "When {inciting_incident}, {protagonist} must {goal} before {deadline}. A fast-paced thriller that will keep you on the edge of your seat with unexpected twists and psychological depth."
- Example: "When a mysterious code appears overnight in major cities worldwide, a cryptographer must decipher its meaning before global chaos ensues. A fast-paced thriller that will keep you on the edge of your seat with unexpected twists and psychological depth."

**Science** (50 books):
- Pattern: "Exploring the mysteries of {topic} through {methodology}. This book examines {research_questions} and presents {findings} that challenge our understanding of {domain}."
- Example: "Exploring the mysteries of quantum entanglement through experimental physics. This book examines whether particles can truly communicate instantaneously and presents findings that challenge our understanding of space and time."

**History** (50 books):
- Pattern: "A detailed examination of {period_or_event} focusing on {aspect}. Drawing from {sources}, this work illuminates {historical_significance} and its lasting impact on {modern_relevance}."
- Example: "A detailed examination of the Renaissance focusing on scientific revolution. Drawing from primary sources and archaeological evidence, this work illuminates how intellectual curiosity reshaped society and its lasting impact on modern scientific method."

**Quality Criteria**:
- Length: 50-100 words (2-3 sentences)
- Semantic diversity: Descriptions should vary enough to test RAG retrieval quality
- Context-appropriate: Match genre conventions and tone
- Natural language: Avoid overly formulaic phrasing
- Unique: Each description distinct (no copy-paste)

### Integration with Phase 7 (RAG)

Once the Description column is added, Phase 7 implementation will:

1. **T089** (`embeddings.py`): Generate embeddings primarily from Description field (with title/author as secondary signals)
2. **T091** (`vector_store.py`): Store description embeddings in DuckDB VSS table
3. **T093** (`semantic_search()`): Retrieve books by description similarity
4. **T087** (test): Validate retrieval accuracy using description-based queries like "books about time travel"
5. **SC-005** (success criteria): Achieve 70%+ top-3 precision enabled by rich descriptions

**Key Design Decision**: The Description field becomes the **primary content** for RAG embeddings, while title/author/category remain structured query fields. This separation aligns with RAG best practices: semantic search for unstructured text, traditional queries for structured metadata.

## Project Structure

### Documentation (this feature)

```text
specs/003-chapter3-ai-engineering/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (COMPLETED)
├── data-model.md        # Phase 1 output (COMPLETED - needs Description update)
├── quickstart.md        # Phase 1 output (COMPLETED - needs Description update)
├── contracts/           # Phase 1 output (COMPLETED)
└── tasks.md             # Phase 2 output (COMPLETED - will add T000.x pre-tasks)
```

### Source Code (repository root)

```text
chapter-3/
├── data/
│   ├── raw/
│   │   └── library/
│   │       └── library_dataset_random.csv    # WILL BE ENHANCED with Description
│   └── duckdb/
│       └── chapter3.db                        # library schema
├── src/
│   ├── library/
│   │   ├── domain.py                          # Book dataclass - NEEDS UPDATE
│   │   ├── repository.py                      # All SELECTs - NEEDS UPDATE
│   │   └── tools.py                           # No changes (uses to_dict)
│   ├── llm/
│   │   ├── base.py
│   │   ├── unified_client.py
│   │   ├── ollama_client.py
│   │   └── openrouter_client.py
│   ├── mcp_servers/
│   │   └── library_server.py
│   ├── agents/
│   │   ├── library_assistant.py
│   │   └── library_assistant_enhanced.py
│   ├── code_execution/
│   │   ├── sandbox.py
│   │   └── tool_api.py
│   ├── rag/                                   # Phase 7 - will use Description
│   │   ├── embeddings.py
│   │   └── vector_store.py
│   ├── tools/                                 # Phase 7
│   │   ├── tool_registry.py
│   │   └── tool_search.py
│   └── a2a/                                   # Phase 8
│       ├── protocol.py
│       └── server.py
├── scripts/
│   ├── load_library_csv_to_duckdb.py         # NEEDS UPDATE (schema + INSERT)
│   ├── generate_descriptions.py              # NEW - T000.1
│   ├── test_code_execution.py
│   └── compare_modes.py
├── tests/
│   ├── unit/
│   │   ├── test_domain.py                    # NEEDS UPDATE (fixtures)
│   │   ├── test_repository.py                # NEEDS UPDATE (test data)
│   │   ├── test_tools.py                     # NEEDS UPDATE (assertions)
│   │   ├── test_mcp_tools.py
│   │   ├── test_sandbox.py
│   │   └── test_unified_client.py
│   └── integration/
│       ├── test_data_load.py                 # NEEDS UPDATE (description validation)
│       ├── test_mcp_server.py
│       ├── test_assistant.py
│       └── test_code_execution.py
├── docs/
│   ├── 01-introduction.md
│   ├── 02-data-setup.md
│   ├── 03-mcp-tools.md
│   ├── 04-traditional-tool-use.md
│   ├── 05-code-execution.md
│   ├── 06-advanced-tools-rag.md               # Phase 7 - will document Description usage
│   └── 07-multi-agent-systems.md              # Phase 8
└── Makefile
```

**Structure Decision**: Single project structure chosen because all components (data infrastructure, agents, tools, RAG) are tightly integrated around the library management domain. A multi-project split would introduce unnecessary complexity for an educational feature where learners benefit from seeing the full stack in one coherent codebase.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations identified. All constitutional requirements are satisfied within the feature design.

## Phase 0: Research & Technical Decisions

**Status**: ✅ COMPLETED (documented in `research.md`)

Key decisions made:
- DuckDB VSS extension for vector similarity search
- sentence-transformers for embeddings (all-MiniLM-L6-v2 model)
- MCP SDK for tool protocol implementation
- Sandboxed code execution with RestrictedPython
- Agent-to-agent protocol using in-process message passing

## Phase 1: Design & Contracts

**Status**: ✅ COMPLETED

**Artifacts Generated**:
- `data-model.md`: Book entity, Tool registry, Agent types (needs Description update)
- `contracts/`: Tool JSON schemas for MCP and traditional tool use
- `quickstart.md`: Progressive learning path with code examples (needs Description update)
- Agent-specific context updated via `update-agent-context.sh`

**Data Model Highlights**:
- **Book Entity**: Book_ID, Title, Author, **Description (TO BE ADDED)**, Category, Cabinet, Rack, Row, Signal_Strength, Timestamp, Status
- **Tool Registry**: name, description, input_schema, capabilities (search/analytics/monitoring)
- **Agent Types**: Library Assistant, Code Execution Agent, Data Analysis Agent, Search/Analytics/Recommendation/Orchestrator Agents

## Implementation Phases

### Pre-Phase 7: Dataset Enhancement (T000.1 - T000.8)

**Goal**: Add Description column to library dataset and update all dependent code

**Estimated Effort**: 4-6 hours

**Tasks**:
1. Generate descriptions for 200 books
2. Update CSV file with Description column
3. Update Book domain model
4. Update database schema and loader
5. Update repository queries
6. Update test fixtures
7. Update documentation
8. End-to-end validation

**Success Criteria**:
- ✅ All 200 books have unique, contextually appropriate descriptions (50-100 words)
- ✅ Descriptions vary in semantic content (enables RAG diversity testing)
- ✅ No data corruption in existing columns
- ✅ CSV loads successfully into DuckDB with description column
- ✅ All existing tests pass with updated fixtures
- ✅ Integration tests validate description presence and constraints

**Checkpoint**: Description column integrated into all phases before starting Phase 7 RAG implementation

### Phase 7: Semantic Search with RAG (After Pre-Phase 7)

**Status**: PENDING (depends on T000 completion)

**Key Changes Enabled by Description Column**:
- Embeddings generated primarily from description text (rich semantic content)
- Semantic queries return relevant books based on description similarity
- RAG demonstrates clear value over keyword search
- Retrieval accuracy measurably higher due to textual content

## Next Steps

### Immediate Actions

1. **User Approval**: Confirm pre-Phase 7 dataset enhancement plan
2. **Execute T000.1**: Generate descriptions using LLM or template-based script
3. **Execute T000.2-T000.8**: Update code, tests, and documentation systematically
4. **Validate**: Run full test suite and verify end-to-end data loading
5. **Commit**: Commit enhanced dataset and code updates to branch
6. **Proceed to Phase 7**: Begin RAG implementation with rich textual data

### Decision Points

**Question for User**: Should we generate descriptions using:
- **Option A**: LLM-assisted generation (Claude/GPT) for higher quality and diversity
- **Option B**: Template-based generation with randomized elements for speed and reproducibility
- **Option C**: Hybrid approach (templates + LLM polish)

**Recommendation**: Option C (Hybrid) - Use templates for structure and consistency, then LLM to add variety and natural language flow. This balances quality, speed, and reproducibility.

## Summary

This plan documents the implementation approach for Chapter 3 - AI Engineering feature, with special focus on the critical pre-Phase 7 dataset enhancement. By adding a Description column to the library dataset **before** starting RAG implementation, we ensure:

1. **Better RAG demonstrations**: Semantic search works on rich textual content
2. **Realistic AI patterns**: Matches production RAG architectures
3. **Educational value**: Learners see clear semantic vs keyword search differences
4. **Immediate benefits**: Earlier phases (MCP, tools) already expose descriptions
5. **Avoid breaking changes**: Schema evolution handled proactively

**Key Artifacts**:
- **Branch**: `003-chapter3-ai-engineering`
- **Plan File**: `/Users/asingamaneni/Downloads/projects/rdewai/Redefining-DataEngineering-With-AI/specs/003-chapter3-ai-engineering/plan.md`
- **Enhanced Dataset**: `chapter-3/data/raw/library/library_dataset_random.csv` (with Description column)
- **Files Requiring Updates**: 7 source files, 5 test files, 3 documentation files

**Impact Assessment**:
- **Effort**: 4-6 hours total
- **Risk**: Low (backward-compatible for external consumers)
- **Benefit**: High (enables high-quality RAG in Phase 7)
- **Recommendation**: **Proceed with pre-Phase 7 enhancement** before starting Phase 7 tasks

This proactive approach ensures the RAG implementation in Phase 7 delivers maximum educational value by working with realistic, semantically rich textual data from the start.
