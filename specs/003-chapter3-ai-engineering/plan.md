# Implementation Plan: Phase 7.5 - Enterprise Tool Simulation

**Branch**: `003-chapter3-ai-engineering` | **Date**: 2025-12-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-chapter3-ai-engineering/spec.md`

**Note**: This plan adds Phase 7.5 before Phase 8 (Multi-Agent System) to demonstrate the token efficiency advantage of code execution over traditional tool use at enterprise scale.

## Summary

Add 100 dummy tools simulating an enterprise environment with tools from different teams and projects. This demonstrates the core insight from Anthropic's "Tool Use" engineering paper: **code execution is dramatically more efficient than traditional tool calling when dealing with many tools**, because:

1. **Traditional Mode**: All tool definitions (JSON schemas) must be loaded into context for every request
2. **Code Execution Mode**: Tool APIs are available but definitions are compact; tools can be discovered dynamically

This phase provides empirical evidence for the paper's claims with a realistic enterprise scenario.

## Technical Context

**Language/Version**: Python 3.10-3.12 (aligned with existing project)
**Primary Dependencies**: OpenAI SDK, DuckDB, sentence-transformers (existing)
**Storage**: DuckDB at `chapter-3/data/duckdb/chapter3.db`
**Testing**: pytest with `uv run pytest`
**Target Platform**: macOS/Linux development environment
**Project Type**: Single project (chapter-3/)
**Performance Goals**: Demonstrate 60%+ token reduction with 100+ tools enabled
**Constraints**: All dummy tools must be realistic enterprise patterns
**Scale/Scope**: 100 dummy tools across 10 enterprise domains

## Constitution Check

*GATE: Must pass before implementation. Re-check after completion.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Code Quality | ✅ | Pre-commit hooks active, ruff/mypy enforced |
| Testing Standards | ✅ | Unit tests for tool generator, integration tests for assistant |
| User Experience | ✅ | `/enable-dummy-tools` command, `make assistant-dummy-tools` |
| Performance | ✅ | Token usage benchmarking is core deliverable |
| Reproducibility | ✅ | All code in UV-managed environment |

## Project Structure

### Documentation (this feature)

```text
specs/003-chapter3-ai-engineering/
├── plan.md                    # This file (Phase 7.5 plan)
├── research.md                # Existing research
├── data-model.md              # Update with DummyTool entity
├── quickstart.md              # Existing
├── contracts/                 # Existing
└── tasks.md                   # Update with Phase 7.5 tasks
```

### Source Code (repository root)

```text
chapter-3/
├── src/
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tool_registry.py        # Existing
│   │   ├── tool_search.py          # Existing
│   │   └── dummy_tools.py          # NEW: 100 enterprise dummy tools
│   ├── agents/
│   │   ├── library_assistant.py        # Update: add enable_dummy_tools
│   │   └── library_assistant_enhanced.py  # Update: add enable_dummy_tools
│   └── ...
├── scripts/
│   └── compare_modes.py            # Update: add --enable-dummy-tools flag
├── tests/
│   ├── unit/
│   │   └── test_dummy_tools.py     # NEW: test dummy tool generation
│   └── integration/
│       └── test_assistant_dummy.py # NEW: test assistant with dummy tools
├── docs/
│   └── 05.5-enterprise-tool-scale.md  # NEW: enterprise scale documentation
└── Makefile                        # Update: add assistant-dummy-tools target
```

**Structure Decision**: Single project extending existing `chapter-3/` structure

## Design: Enterprise Dummy Tools

### Domain Categories (10 Teams, 10 Tools Each = 100 Tools)

The dummy tools simulate an enterprise with multiple teams, each owning different services:

| Team | Domain | Example Tools |
|------|--------|---------------|
| **Engineering** | Code & CI/CD | `run_build`, `check_ci_status`, `trigger_deployment`, `get_test_coverage` |
| **Data Platform** | Data Services | `query_warehouse`, `get_data_lineage`, `validate_schema`, `refresh_dashboard` |
| **Security** | Compliance | `scan_vulnerabilities`, `check_access_permissions`, `audit_logs`, `rotate_secrets` |
| **HR** | Employee Data | `get_employee_info`, `submit_pto_request`, `check_org_chart`, `get_team_roster` |
| **Finance** | Accounting | `get_budget_status`, `submit_expense`, `generate_invoice`, `check_payment_status` |
| **Marketing** | Campaigns | `get_campaign_metrics`, `schedule_post`, `analyze_sentiment`, `generate_report` |
| **Sales** | CRM | `get_lead_details`, `update_opportunity`, `check_quota`, `forecast_revenue` |
| **Support** | Customer Service | `create_ticket`, `get_ticket_status`, `escalate_issue`, `search_knowledge_base` |
| **Infrastructure** | DevOps | `check_server_status`, `scale_service`, `get_metrics`, `restart_container` |
| **ML Platform** | AI/ML | `train_model`, `get_experiment_results`, `deploy_model`, `monitor_predictions` |

### Tool Definition Schema

Each dummy tool follows the standard JSON schema format:

```python
ToolDefinition(
    name="team_action_noun",  # e.g., "engineering_run_build"
    description="Detailed description of what this tool does in enterprise context.",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
            "param2": {"type": "integer", "description": "..."},
        },
        "required": ["param1"],
    },
)
```

### Token Impact Analysis

**Without Dummy Tools (Current State)**:
- Library tools: ~9 tools × ~150 tokens/tool = ~1,350 tokens for tool definitions
- System prompt: ~300 tokens
- Total context overhead: ~1,650 tokens

**With Dummy Tools (100 Additional)**:
- Library tools: ~1,350 tokens
- Dummy tools: ~100 tools × ~180 tokens/tool = ~18,000 tokens
- System prompt: ~300 tokens
- **Total context overhead: ~19,650 tokens** (12x increase!)

**Code Execution Advantage**:
- Code execution mode: Tool APIs are available but not in JSON schema form
- Discovery functions: `list_available_tools()`, `get_tool_info(name)`
- Only ~500 tokens for API stubs vs ~19,650 for full schemas
- **Expected reduction: 95%+ for tool definition overhead**

## Implementation Approach

### 1. Dummy Tool Generator (`chapter-3/src/tools/dummy_tools.py`)

```python
"""Enterprise dummy tools for scale testing.

This module generates 100 dummy tools across 10 enterprise domains
to demonstrate token efficiency of code execution vs traditional tools.
"""

from llm.base import ToolDefinition

ENTERPRISE_DOMAINS = {
    "engineering": [...],
    "data_platform": [...],
    "security": [...],
    # ... 10 domains total
}

def generate_dummy_tools() -> list[ToolDefinition]:
    """Generate 100 enterprise dummy tools."""
    ...

def get_dummy_tool_functions() -> dict[str, callable]:
    """Get dummy tool function implementations (all return mock data)."""
    ...
```

### 2. Assistant Integration

Update `LibraryAssistant` and `EnhancedLibraryAssistant` to support:

```python
class LibraryAssistant:
    def __init__(
        self,
        llm_provider: LLMProvider,
        enable_dummy_tools: bool = False,  # NEW
        ...
    ):
        self._enable_dummy_tools = enable_dummy_tools
        self._tools = self._get_tools()

    def _get_tools(self) -> list[ToolDefinition]:
        tools = LIBRARY_TOOL_DEFINITIONS.copy()
        if self._enable_dummy_tools:
            tools.extend(generate_dummy_tools())
        return tools
```

### 3. CLI Command: `/enable-dummy-tools`

Add to the interactive REPL:

```python
elif cmd == "/enable-dummy-tools":
    new_status = not assistant._enable_dummy_tools
    assistant.set_dummy_tools_enabled(new_status)
    status = "ENABLED" if new_status else "DISABLED"
    count = len(generate_dummy_tools()) if new_status else 0
    print(f"Enterprise dummy tools: {status} ({count} tools)")
```

### 4. Makefile Target: `make assistant-dummy-tools`

```makefile
assistant-dummy-tools: ## Start Library Assistant with 100 enterprise dummy tools
	@cd chapter-3 && uv run python -m src.agents.library_assistant_enhanced \
		--mode traditional \
		--enable-dummy-tools
```

### 5. Compare Modes Update

Update `scripts/compare_modes.py`:

```python
parser.add_argument(
    "--enable-dummy-tools",
    action="store_true",
    help="Enable 100 enterprise dummy tools to demonstrate scale impact"
)
```

## Phase 7.5 Tasks Summary

| Task ID | Description | Parallelizable |
|---------|-------------|----------------|
| T7.5-001 | Create `dummy_tools.py` with tool generator | ✗ |
| T7.5-002 | Generate 10 tools for Engineering domain | [P] |
| T7.5-003 | Generate 10 tools for Data Platform domain | [P] |
| T7.5-004 | Generate 10 tools for Security domain | [P] |
| T7.5-005 | Generate 10 tools for HR domain | [P] |
| T7.5-006 | Generate 10 tools for Finance domain | [P] |
| T7.5-007 | Generate 10 tools for Marketing domain | [P] |
| T7.5-008 | Generate 10 tools for Sales domain | [P] |
| T7.5-009 | Generate 10 tools for Support domain | [P] |
| T7.5-010 | Generate 10 tools for Infrastructure domain | [P] |
| T7.5-011 | Generate 10 tools for ML Platform domain | [P] |
| T7.5-012 | Add mock implementations for all dummy tools | ✗ |
| T7.5-013 | Update `library_assistant.py` with enable_dummy_tools | ✗ |
| T7.5-014 | Update `library_assistant_enhanced.py` with enable_dummy_tools | ✗ |
| T7.5-015 | Add `/enable-dummy-tools` CLI command | ✗ |
| T7.5-016 | Update `compare_modes.py` with --enable-dummy-tools flag | ✗ |
| T7.5-017 | Add `make assistant-dummy-tools` target | [P] |
| T7.5-018 | Add `make compare-modes-enterprise` target | [P] |
| T7.5-019 | Create `test_dummy_tools.py` unit tests | [P] |
| T7.5-020 | Create `test_assistant_dummy.py` integration tests | [P] |
| T7.5-021 | Create `05.5-enterprise-tool-scale.md` documentation | [P] |
| T7.5-022 | Run benchmark with dummy tools and record results | ✗ |
| T7.5-023 | Update `tasks.md` with Phase 7.5 tasks | ✗ |

**Total Tasks**: 23 | **Parallelizable**: 13

## Success Criteria

1. **SC-7.5-001**: 100 dummy tools generated across 10 enterprise domains
2. **SC-7.5-002**: Traditional mode with dummy tools uses 15,000+ tokens for tool definitions
3. **SC-7.5-003**: Code execution mode with dummy tools uses < 2,000 tokens for tool definitions
4. **SC-7.5-004**: `make assistant-dummy-tools` starts assistant with all tools loaded
5. **SC-7.5-005**: `/enable-dummy-tools` toggles dummy tools at runtime
6. **SC-7.5-006**: `compare_modes.py --enable-dummy-tools` shows 80%+ token reduction
7. **SC-7.5-007**: All existing tests continue to pass

## Dependencies

- **Requires**: Phase 7 (RAG/Semantic Search) complete
- **Blocks**: Phase 8 (Multi-Agent System)
- **Rationale**: This phase provides empirical evidence for choosing code execution in multi-agent scenarios

## Complexity Tracking

> No constitution violations. This is a straightforward feature extension.

## Key Files to Create/Modify

### New Files

1. `chapter-3/src/tools/dummy_tools.py` - Enterprise dummy tool generator
2. `chapter-3/tests/unit/test_dummy_tools.py` - Unit tests
3. `chapter-3/tests/integration/test_assistant_dummy.py` - Integration tests
4. `chapter-3/docs/05.5-enterprise-tool-scale.md` - Documentation

### Modified Files

1. `chapter-3/src/agents/library_assistant.py` - Add enable_dummy_tools
2. `chapter-3/src/agents/library_assistant_enhanced.py` - Add enable_dummy_tools
3. `chapter-3/scripts/compare_modes.py` - Add --enable-dummy-tools flag
4. `chapter-3/Makefile` - Add new targets
5. `specs/003-chapter3-ai-engineering/tasks.md` - Add Phase 7.5 tasks

## References

- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Anthropic: Tool Use Best Practices](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Model Context Protocol](https://modelcontextprotocol.io/)
