# PWI OpenHands SDK Integration

This module provides the OpenHands SDK integration for the Planning with Intent (PWI) framework, enabling tool-use capabilities for external system integration.

## Status: ✅ Complete (Phase 9 - Skills & Artifact-Only Agents)

## Quick Start

```python
from pwi.openhands.agents import create_pwi_agent, create_pwi_conversation, AGENT_TOOL_MAP

# Create an agent with auto-configured tools and skills
agent = create_pwi_agent("data_analyst", llm_config={"model": "openai/gpt-4o-mini"})
conversation = create_pwi_conversation(agent, workspace="./output")

# Send task and run
conversation.send_message("Analyze the healthcare data schema")
conversation.run()

# Check tool configuration
print(AGENT_TOOL_MAP["data_analyst"])
# ['terminal', 'file_editor', 'task_tracker', 'duckdb_query', 'duckdb_schema', ...]

print(AGENT_TOOL_MAP["dq_engineer"])
# []  # No tools - outputs artifact directly as text
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
│   ├── __init__.py      # Agent factory and utilities
│   └── factory.py       # create_pwi_agent, create_pwi_conversation
│
├── tools/               # Custom tools for agents
│   ├── __init__.py      # Tool exports and AGENT_TOOL_MAP
│   ├── base.py          # ToolRegistry class (legacy)
│   ├── duckdb_tool.py   # DuckDB query/schema tools
│   ├── csv_tool.py      # CSV analysis tools
│   ├── metadata_tool.py # Metadata API tools
│   └── artifact_tool.py # Artifact generation tools
│
└── workflow/            # Workflow orchestration
    ├── __init__.py      # Workflow exports
    └── controller.py    # PWIWorkflowController
```

## Agent Tool Configuration

| Agent | Tools | Behavior |
|-------|-------|----------|
| data_analyst | DuckDB, CSV, terminal, file_editor | Explores data, generates DRD |
| data_architect | file_editor, task_tracker | Generates PAD from DRD context |
| mapping_engineer | DuckDB, CSV, Metadata, terminal | Maps fields with schema exploration |
| dq_engineer | **None** | Outputs DQS YAML directly |
| story_writer | file_editor, task_tracker | Generates stories from context |
| sync_agent | **None** | Outputs Package directly |

**Artifact-Only Agents**: Agents with no tools output their artifact directly as text. This prevents exploration loops where agents repeatedly call tools instead of generating artifacts. The SDK captures text output as `MessageEvent` which is extracted as the artifact.

## Skills (Contextual Knowledge)

Skills are auto-discovered from `.openhands/skills/` and injected into agents based on keyword triggers:

```python
from pwi.openhands.agents import build_agent_context, discover_skills

# Discover available skills
skills = discover_skills()
# [SkillInfo(name='duckdb', triggers=['duckdb', 'sql query', ...]), ...]

# Build agent context with skills
agent_context = build_agent_context()
```

## Available Domain Tools (14)

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
  (explore)    (from DRD)        (explore)       (direct out)   (from all)   (direct out)
```

## Microagent Prompts

Agent prompts are loaded from `.openhands/microagents/`:

- `data_analyst.md` - DRD generation with exploration
- `data_architect.md` - PAD generation from DRD
- `mapping_engineer.md` - DMD generation with exploration
- `dq_engineer.md` - DQS YAML output (no tools)
- `story_writer.md` - Stories from all artifacts
- `sync_agent.md` - Package consolidation (no tools)

## Documentation

See [docs/OPENHANDS_SDK_REFERENCE.md](../../docs/OPENHANDS_SDK_REFERENCE.md) for SDK reference.

## Testing

```bash
# Run integration tests
uv run pytest tests/integration/test_openhands_integration.py -v

# Quick validation
uv run python -c "from pwi.openhands.agents import get_available_agent_types; print(get_available_agent_types())"
```
