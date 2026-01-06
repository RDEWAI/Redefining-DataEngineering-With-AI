# PWI OpenHands SDK Integration

This module provides the OpenHands SDK integration for the Planning with Intent (PWI) framework, enabling tool-use capabilities for external system integration.

## Status: ✅ Complete (Phase 8)

## Quick Start

```python
from pwi.openhands.agents import DataAnalystAgent, PWIAgentConfig, PWIAgentState
from pwi.openhands.workflow import PWIWorkflowController

# Create an agent
config = PWIAgentConfig(name="data_analyst", model="gpt-4o")
agent = DataAnalystAgent(config=config, llm_client=llm)

# Check available tools
print(agent.tool_names)
# ['duckdb_query', 'duckdb_schema', 'duckdb_tables', 'analyze_csv', 'csv_stats']
```

## Module Structure

```
pwi/openhands/
├── __init__.py          # Main module exports
├── config.py            # OpenHands configuration adapter
├── runtime.py           # Runtime manager (Docker/local)
├── README.md            # This file
│
├── agents/              # OpenHands-based agents
│   ├── __init__.py      # Agent registry and utilities
│   ├── base.py          # BasePWIAgent with tool-use
│   ├── data_analyst.py  # DRD generation
│   ├── data_architect.py# PAD generation
│   ├── mapping_engineer.py # DMD generation
│   ├── dq_engineer.py   # DQS generation
│   ├── story_writer.py  # User Stories
│   └── sync_agent.py    # Package consolidation
│
├── tools/               # Custom tools for agents
│   ├── __init__.py      # Tool exports
│   ├── base.py          # ToolRegistry class
│   ├── duckdb_tool.py   # DuckDB query/schema tools
│   ├── csv_tool.py      # CSV analysis tools
│   ├── metadata_tool.py # Metadata API tools
│   └── artifact_tool.py # Artifact generation tools
│
└── workflow/            # Workflow orchestration
    ├── __init__.py      # Workflow exports
    ├── events.py        # Event types and EventStream
    ├── session_adapter.py # Session-Event bridge
    ├── review_handler.py # Review gate handlers
    └── controller.py    # PWIWorkflowController
```

## Available Tools (14)

| Category | Tools |
|----------|-------|
| DuckDB | `duckdb_query`, `duckdb_schema`, `duckdb_validate`, `duckdb_tables` |
| CSV | `analyze_csv`, `csv_stats`, `csv_sample` |
| Metadata | `query_metadata_catalog`, `get_lineage`, `get_tags` |
| Artifact | `generate_artifact`, `save_artifact`, `validate_artifact`, `list_artifact_types` |

## Agent Pipeline

```
data_analyst → data_architect → mapping_engineer → dq_engineer → story_writer → sync_agent
     ↓              ↓                 ↓                ↓              ↓            ↓
    DRD            PAD               DMD              DQS          Stories      Package
```

## Documentation

See [docs/openhands_migration.md](../../docs/openhands_migration.md) for comprehensive documentation.

## Testing

```bash
# Run integration tests
uv run pytest tests/integration/test_openhands_integration.py -v

# Quick validation
uv run python -c "from pwi.openhands.agents import list_agents; print(list_agents())"
```
