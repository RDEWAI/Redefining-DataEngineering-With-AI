# Implementation Plan: Chapter 3 - AI Engineering with Library Management Data

**Branch**: `003-chapter3-ai-engineering` | **Date**: 2025-12-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-chapter3-ai-engineering/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This plan adds **Phase 5.5: Code Quality & Unified LLM Client** between the completed Phase 5 (Traditional Tool Use) and the upcoming Phase 6 (Advanced Tool Use & RAG). This phase focuses on:

1. **Git Hooks**: Pre-commit and pre-push hooks for automated linting and testing
2. **Unified LLM Client**: Refactor to use OpenAI SDK for all providers (OpenRouter, Ollama, OpenAI) with unified configuration
3. **Usage Tracking**: Implement OpenRouter usage accounting for token and cost monitoring

This ensures code quality gates are in place and simplifies LLM client management before moving to more advanced AI patterns.

## Technical Context

**Language/Version**: Python 3.10-3.12 (aligned with existing project)
**Primary Dependencies**:
- openai>=1.0.0 (unified client SDK)
- pre-commit>=3.0.0 (git hooks framework)
- ruff>=0.1.0 (fast Python linter)
- pytest>=8.0.0 (testing framework)

**Storage**: DuckDB at `chapter-3/data/duckdb/chapter3.db` with `library` schema
**Testing**: pytest with pre-commit hooks for automated validation
**Target Platform**: Local development (macOS/Linux), CI/CD pipelines
**Project Type**: Single Python project with chapter-3/ root
**Performance Goals**:
- Pre-commit hooks: <5 seconds for lint checks
- Pre-push hooks: <30 seconds for unit tests
- LLM API response: <2 seconds for simple queries

**Constraints**:
- Must maintain backward compatibility with existing LLM provider interface
- Git hooks must not block emergency commits (allow --no-verify)
- Usage tracking must work with OpenRouter API

**Scale/Scope**:
- ~15 Python source files in chapter-3/src/
- ~8 test files in chapter-3/tests/
- 3 LLM providers (OpenRouter, Ollama, OpenAI)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Code Quality & Maintainability (NON-NEGOTIABLE)
✅ **PASS** - This phase directly enforces code quality through:
- Git hooks for automated linting (ruff)
- Type checking enforcement
- Pre-commit validation to prevent low-quality code from being committed

### Testing Standards (NON-NEGOTIABLE)
✅ **PASS** - Enhances testing through:
- Pre-push hooks that run unit tests automatically
- Prevents pushing code with failing tests
- Maintains 80%+ coverage requirement

### User Experience Consistency
✅ **PASS** - Improves UX through:
- Unified LLM client configuration (.env-based)
- Consistent error messages across providers
- Simplified provider switching (single base_url/api_key pattern)

### Performance & Scalability
✅ **PASS** - Optimizes performance through:
- Ruff (200x faster than flake8) for linting
- Fast pre-commit checks (<5s target)
- Usage tracking for cost monitoring and optimization

### Reproducibility & Environment Consistency
✅ **PASS** - Strengthens reproducibility through:
- UV-managed dependencies with locked versions
- Git hooks ensure code quality is consistent across all developers
- .env.example provides clear configuration template

### Quality Gates
✅ **PASS** - This phase adds new quality gates:
- **Pre-commit**: Ruff linting, type checking
- **Pre-push**: Unit test suite execution
- All existing gates (uv sync, make dev-setup) remain

**Constitution Compliance**: No violations. This phase strengthens adherence to all constitutional principles.

## Project Structure

### Documentation (this feature)

```text
specs/003-chapter3-ai-engineering/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification (already exists)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── contracts/           # Phase 1 output (/speckit.plan command)
```

### Source Code (repository root)

```text
chapter-3/
├── src/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py              # Existing: LLM provider interface
│   │   ├── unified_client.py    # NEW: OpenAI SDK-based unified client
│   │   ├── openrouter_client.py # DEPRECATED: Legacy OpenRouter (keep for migration)
│   │   └── ollama_client.py     # DEPRECATED: Legacy Ollama (keep for migration)
│   ├── library/
│   ├── agents/
│   ├── mcp_servers/
│   └── tools/
├── tests/
│   ├── unit/
│   │   └── test_unified_client.py  # NEW: Test unified LLM client
│   └── integration/
├── .env.example          # UPDATED: Unified LLM config
├── pyproject.toml        # UPDATED: Add pre-commit dependency
├── .pre-commit-config.yaml  # NEW: Pre-commit hook configuration
└── .git/
    └── hooks/
        ├── pre-commit    # NEW: Generated by pre-commit framework
        └── pre-push      # NEW: Generated by pre-commit framework

# Root-level (repository)
.gitignore                # UPDATED: Ignore .env files
```

**Structure Decision**: Single Python project structure maintained. This phase adds:
1. New unified LLM client module (chapter-3/src/llm/unified_client.py)
2. Pre-commit configuration at chapter-3 root
3. Git hooks in repository .git/hooks/ (applies to all commits)

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations - this section is not applicable.

---

## Phase 0: Outline & Research

### Research Tasks

1. **OpenAI SDK Compatibility with OpenRouter**
   - Research: OpenAI SDK can be used with OpenRouter by setting `base_url="https://openrouter.ai/api/v1"`
   - Decision: Use OpenAI SDK v1.0+ as unified client for all providers
   - Alternatives considered: Creating custom client, using httpx directly
   - Rationale: OpenAI SDK is well-maintained, type-safe, and already supports custom base URLs

2. **OpenRouter Usage Accounting API**
   - Research: OpenRouter supports usage accounting via response headers and /generation endpoint
   - Decision: Enable usage tracking via built-in usage parameter in API calls
   - Findings from web search:
     - Usage accounting adds ~200ms latency to last response
     - Returns detailed token counts using native tokenizer
     - Alternative: GET /api/v1/generation/{id} for post-request stats
     - Credits API: GET /api/v1/key for balance checking
   - Rationale: Built-in usage parameter provides accurate token counts without extra API calls

3. **Pre-commit Framework vs Manual Git Hooks**
   - Research: Pre-commit framework is the Python ecosystem standard (2025 best practices)
   - Decision: Use pre-commit framework with .pre-commit-config.yaml
   - Alternatives considered: Manual shell scripts in .git/hooks/
   - Rationale:
     - Multi-language support
     - Automatic hook installation via `pre-commit install`
     - Community-maintained hook repositories
     - Easy to configure and version control

4. **Ruff vs Flake8/Pylint for Linting**
   - Research: Ruff is 200x faster than traditional linters (2025 industry standard)
   - Decision: Use Ruff for linting and formatting (already in pyproject.toml)
   - Alternatives considered: Black + Flake8 + isort combo
   - Rationale: Single tool replaces multiple, extreme speed, Rust-based reliability

5. **Pre-push Testing Strategy**
   - Research: Pre-push hooks should run fast unit tests, not full integration suite
   - Decision: Run `uv run pytest tests/unit/ -v` in pre-push hook
   - Constraints: Must complete in <30 seconds to avoid developer friction
   - Alternatives considered: Run all tests (too slow), skip tests (defeats purpose)
   - Rationale: Balance between coverage and developer experience

### Research Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM Client SDK | OpenAI SDK v1.0+ | Industry standard, supports custom base URLs |
| Usage Tracking | Built-in `usage` parameter | Accurate token counts, minimal overhead (~200ms) |
| Git Hooks Framework | pre-commit | Python ecosystem standard, easy maintenance |
| Linter | Ruff | 200x faster than alternatives, single tool |
| Pre-push Tests | Unit tests only | Fast (<30s), catches most issues |

**Output**: research.md generated with all decisions documented

---

## Phase 1: Design & Contracts

### Data Model

**File**: `data-model.md`

#### Entity: UnifiedLLMClient

**Purpose**: Provides a single client interface for all LLM providers (OpenRouter, Ollama, OpenAI) using the OpenAI SDK.

**Fields**:
- `base_url`: str - API endpoint (OpenRouter, Ollama, or OpenAI)
- `api_key`: str - Authentication key (required for OpenRouter/OpenAI, optional for Ollama)
- `model`: str - Model identifier (e.g., "openai/gpt-4o-mini", "llama3.2")
- `provider_type`: str - Enum: "openrouter", "ollama", "openai"

**Relationships**:
- Implements `LLMProvider` interface from `base.py`
- Used by `LibraryAssistant` in `agents/library_assistant.py`

**Validation Rules**:
- `base_url` must be valid HTTP/HTTPS URL
- `api_key` required if provider_type is "openrouter" or "openai"
- `model` must not be empty string

**State Transitions**: N/A (stateless client)

#### Entity: UsageMetrics

**Purpose**: Tracks token usage and costs for OpenRouter API calls.

**Fields**:
- `prompt_tokens`: int - Input tokens consumed
- `completion_tokens`: int - Output tokens generated
- `total_tokens`: int - Sum of prompt + completion
- `model`: str - Model used for the request
- `cost_usd`: float - Estimated cost in USD (optional, if available from provider)

**Relationships**:
- Returned by `UnifiedLLMClient.generate()` in `LLMResponse.usage`

**Validation Rules**:
- All token counts must be non-negative integers
- `total_tokens` = `prompt_tokens` + `completion_tokens`

#### Entity: GitHookConfig

**Purpose**: Configuration for pre-commit and pre-push hooks.

**Fields**:
- `pre_commit_hooks`: List[str] - Hooks to run before commit (e.g., ["ruff", "mypy"])
- `pre_push_hooks`: List[str] - Hooks to run before push (e.g., ["pytest-unit"])

**Relationships**:
- Defined in `.pre-commit-config.yaml`

**Validation Rules**:
- Hook names must correspond to valid pre-commit hook IDs
- Hooks must be executable and return exit code 0 on success

### API Contracts

**File**: `contracts/unified_llm_client.yaml` (OpenAPI 3.0 format)

```yaml
# Configuration Contract (.env format)
# This is not a REST API, but a configuration schema

env_variables:
  LLM_BASE_URL:
    type: string
    required: true
    description: "API endpoint URL (OpenRouter, Ollama, or OpenAI)"
    examples:
      - "https://openrouter.ai/api/v1"
      - "http://localhost:11434/v1"
      - "https://api.openai.com/v1"

  LLM_API_KEY:
    type: string
    required: false
    description: "API key (required for OpenRouter/OpenAI, optional for Ollama)"
    examples:
      - "sk-or-v1-..."
      - "sk-..."

  LLM_MODEL:
    type: string
    required: true
    description: "Model identifier"
    examples:
      - "openai/gpt-4o-mini"
      - "anthropic/claude-3-haiku-20240307"
      - "llama3.2"

  LLM_ENABLE_USAGE_TRACKING:
    type: boolean
    required: false
    default: true
    description: "Enable token usage tracking (OpenRouter only)"

# Python API Contract
UnifiedLLMClient:
  constructor:
    parameters:
      - base_url: str
      - api_key: str | None
      - model: str
      - enable_usage_tracking: bool = True

  methods:
    generate:
      parameters:
        - messages: List[Message]
        - temperature: float = 0.7
        - max_tokens: int | None = None
        - tools: List[ToolDefinition] | None = None
      returns:
        type: LLMResponse
        fields:
          - content: str | None
          - tool_calls: List[ToolCall]
          - usage: UsageMetrics
          - model: str
```

**File**: `contracts/git_hooks.yaml`

```yaml
# Git Hooks Contract

pre_commit:
  hooks:
    - id: ruff-check
      name: "Ruff Linter"
      entry: "uv run ruff check"
      language: system
      types: [python]
      pass_filenames: true

    - id: ruff-format
      name: "Ruff Formatter"
      entry: "uv run ruff format --check"
      language: system
      types: [python]
      pass_filenames: true

    - id: mypy
      name: "Type Checker"
      entry: "uv run mypy"
      language: system
      types: [python]
      pass_filenames: false

pre_push:
  hooks:
    - id: pytest-unit
      name: "Unit Tests"
      entry: "uv run pytest tests/unit/ -v"
      language: system
      pass_filenames: false
      timeout: 30
```

### Quickstart Guide

**File**: `quickstart.md`

```markdown
# Phase 5.5 Quickstart: Code Quality & Unified LLM Client

## Prerequisites

- Completed Phase 5 (Traditional Tool Use)
- Python 3.10-3.12 with UV installed
- Git repository initialized

## Setup (5 minutes)

### 1. Install Pre-commit Hooks

```bash
cd chapter-3
uv add --dev pre-commit
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
```

### 2. Configure Environment

Update `.env` file:

```bash
# Unified LLM Configuration
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-api-key-here
LLM_MODEL=openai/gpt-4o-mini
LLM_ENABLE_USAGE_TRACKING=true
```

### 3. Test Git Hooks

```bash
# Test pre-commit hook
echo "print('test')" >> src/test_file.py
git add src/test_file.py
git commit -m "Test pre-commit hook"  # Should run ruff, mypy

# Test pre-push hook
git push  # Should run unit tests before pushing
```

## Usage

### Unified LLM Client

```python
from src.llm.unified_client import UnifiedLLMClient
from src.llm.base import Message

# Initialize client (auto-loads from .env)
client = UnifiedLLMClient.from_env()

# Generate response with usage tracking
response = client.generate(
    messages=[Message(role="user", content="Hello!")],
    temperature=0.7
)

print(f"Response: {response.content}")
print(f"Tokens used: {response.usage['total_tokens']}")
print(f"Model: {response.model}")
```

### Switching Providers

**OpenRouter**:
```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-...
LLM_MODEL=openai/gpt-4o-mini
```

**Ollama (local)**:
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=  # Leave empty
LLM_MODEL=llama3.2
```

**OpenAI**:
```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

## Verification

```bash
# Run all checks manually
uv run ruff check chapter-3/src/
uv run mypy chapter-3/src/
uv run pytest chapter-3/tests/unit/ -v

# Verify usage tracking
uv run python -c "
from src.llm.unified_client import UnifiedLLMClient
from src.llm.base import Message

client = UnifiedLLMClient.from_env()
response = client.generate(messages=[Message(role='user', content='Hi')])
assert 'total_tokens' in response.usage
print('✓ Usage tracking enabled')
"
```

## Troubleshooting

**Pre-commit hook fails on commit**:
- Check `.pre-commit-config.yaml` is present
- Run `uv run pre-commit run --all-files` to see specific errors

**Usage tracking not working**:
- Ensure `LLM_ENABLE_USAGE_TRACKING=true` in `.env`
- Verify `LLM_BASE_URL` points to OpenRouter (only provider supporting usage API)

**Ollama connection refused**:
- Start Ollama: `ollama serve`
- Ensure `LLM_BASE_URL=http://localhost:11434/v1` (note: `/v1` suffix required)
```

### Agent Context Update

Run the agent context update script:

```bash
cd /Users/asingamaneni/Downloads/projects/rdewai/Redefining-DataEngineering-With-AI
.specify/scripts/bash/update-agent-context.sh claude
```

This will update `CLAUDE.md` with:
- **Active Technologies**: pre-commit framework, OpenAI SDK
- **Recent Changes**: Phase 5.5 git hooks and unified LLM client

---

## Phase 2: Tasks Generation

**NOT INCLUDED IN THIS PLAN** - Phase 2 (tasks.md generation) is handled by the `/speckit.tasks` command after plan approval.

---

## Phase Breakdown (Reference)

This plan inserts a new phase between the completed Phase 5 and existing Phase 6:

- **Phase 0-1**: Data Infrastructure & MCP Server (✅ Complete)
- **Phase 2-3**: Basic MCP & Traditional Tool Use (✅ Complete)
- **Phase 4-5**: Code Execution & Traditional Tool Use (✅ Complete)
- **Phase 5.5**: Code Quality & Unified LLM Client (🆕 THIS PLAN)
- **Phase 6**: Advanced Tool Use & RAG (⏳ Pending)
- **Phase 7**: Multi-Agent System (⏳ Pending)

---

## Key Implementation Files

### Core Implementation

1. **chapter-3/src/llm/unified_client.py** (NEW)
   - UnifiedLLMClient class using OpenAI SDK
   - Support for OpenRouter, Ollama, OpenAI via base_url
   - Usage tracking integration (OpenRouter)

2. **chapter-3/.env.example** (UPDATE)
   - Unified configuration: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
   - Usage tracking flag: LLM_ENABLE_USAGE_TRACKING

3. **chapter-3/.pre-commit-config.yaml** (NEW)
   - Pre-commit hooks: ruff check, ruff format, mypy
   - Pre-push hooks: pytest unit tests

4. **chapter-3/pyproject.toml** (UPDATE)
   - Add pre-commit>=3.0.0 to dev dependencies

### Testing

5. **chapter-3/tests/unit/test_unified_client.py** (NEW)
   - Test OpenAI SDK initialization with different providers
   - Test usage tracking with OpenRouter
   - Test error handling for missing API keys

6. **chapter-3/tests/integration/test_assistant.py** (UPDATE)
   - Update to use UnifiedLLMClient instead of separate clients
   - Verify usage metrics are captured

### Documentation

7. **specs/003-chapter3-ai-engineering/research.md** (NEW)
   - Research findings from Phase 0
   - Technology decisions and rationale

8. **specs/003-chapter3-ai-engineering/data-model.md** (NEW)
   - UnifiedLLMClient entity definition
   - UsageMetrics entity definition

9. **specs/003-chapter3-ai-engineering/quickstart.md** (NEW)
   - Setup instructions for git hooks
   - Usage examples for unified client
   - Provider switching guide

---

## Success Criteria

**Phase 5.5 is complete when**:

1. ✅ Pre-commit hooks installed and running automatically
   - Ruff linting passes on all Python files
   - Type checking (mypy) passes on all source code
   - Hooks block commits with linting/type errors

2. ✅ Pre-push hooks running unit tests
   - Unit tests execute before every git push
   - Hook blocks push if tests fail
   - Tests complete in <30 seconds

3. ✅ Unified LLM client implemented
   - Single client class supports OpenRouter, Ollama, OpenAI
   - Configuration via .env (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)
   - Backward compatible with existing LLMProvider interface

4. ✅ Usage tracking functional
   - OpenRouter API returns token usage metrics
   - Usage data captured in LLMResponse.usage
   - Metrics include prompt_tokens, completion_tokens, total_tokens

5. ✅ All tests passing
   - `uv run pytest tests/unit/ -v` passes 100%
   - `uv run pytest tests/integration/ -v` passes 100%
   - New test_unified_client.py covers all client scenarios

6. ✅ Documentation complete
   - research.md documents all technology decisions
   - quickstart.md provides clear setup instructions
   - .env.example updated with unified configuration

---

## References

### Web Search Sources

**OpenRouter Usage Accounting**:
- [Usage Accounting | OpenRouter Documentation](https://openrouter.ai/docs/use-cases/usage-accounting)
- [OpenRouter API Reference](https://openrouter.ai/docs/api/reference/overview)
- [OpenRouter Review 2025: API Gateway, Latency & Pricing](https://skywork.ai/blog/openrouter-review-2025-api-gateway-latency-pricing/)

**Git Hooks & Pre-commit**:
- [pre-commit Framework](https://pre-commit.com/)
- [Effortless Code Quality: Pre-Commit Hooks Guide for 2025](https://gatlenculp.medium.com/effortless-code-quality-the-ultimate-pre-commit-hooks-guide-for-2025-57ca501d9835)
- [Git Hooks for Automated Code Quality Checks 2025](https://dev.to/arasosman/git-hooks-for-automated-code-quality-checks-guide-2025-372f)
- [Automating Code Quality Control with Pre-commit Hooks](https://medium.com/@gnetkov/automating-code-quality-control-with-pre-commit-hooks-fdbc1ec5cfea)

### Internal References

- Feature Spec: [spec.md](./spec.md)
- Constitution: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)
- Phase 5 Implementation: `chapter-3/src/agents/library_assistant.py`
- Existing LLM Clients: `chapter-3/src/llm/openrouter_client.py`, `chapter-3/src/llm/ollama_client.py`

---

## Migration Path

### Deprecation Strategy

**Legacy clients** (`openrouter_client.py`, `ollama_client.py`) will be:
1. Kept in codebase for backward compatibility
2. Marked as deprecated with docstring warnings
3. Not removed until Phase 6 completion (all code migrated)

**Migration steps**:
1. Phase 5.5: Introduce UnifiedLLMClient, update .env
2. Phase 6: Migrate agents to use UnifiedLLMClient
3. Phase 7: Remove legacy client files after full migration

This allows gradual migration without breaking existing code.

---

## Notes

- This plan does NOT include task generation (tasks.md) - that comes from `/speckit.tasks`
- All file paths are absolute from repository root
- Pre-commit hooks apply to entire repository, not just chapter-3/
- Usage tracking only works with OpenRouter; Ollama/OpenAI will return empty usage dict

---

**Plan Status**: ✅ Ready for Phase 0 (Research) execution
**Next Command**: Begin research phase or proceed to `/speckit.tasks` after approval
