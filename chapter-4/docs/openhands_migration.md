# OpenHands SDK Migration Guide

This document describes the Phase 8 migration of PWI (Planning with Intent) from a custom agent framework to the OpenHands SDK, enabling tool-use capabilities for external system integration.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Agents](#agents)
5. [Tools](#tools)
6. [Workflow Orchestration](#workflow-orchestration)
7. [Skills/Microagents](#skillsmicroagents)
8. [Configuration](#configuration)
9. [Migration from Legacy](#migration-from-legacy)
10. [API Reference](#api-reference)

---

## Overview

### What Changed

| Aspect | Before (Legacy) | After (OpenHands) |
|--------|-----------------|-------------------|
| Agent Framework | Custom `BaseAgent` class | OpenHands-style `BasePWIAgent` |
| Tool Support | None | 14 tools for DuckDB, CSV, APIs |
| State Management | `transitions` state machine | Event-sourced `EventStream` |
| LLM Integration | Text-in/text-out completions | Tool-use with function calling |
| Skills | Prompt files only | YAML-frontmatter microagents |

### Key Benefits

- **Tool-Use Capabilities**: Agents can query DuckDB, analyze CSVs, and call external APIs
- **Event Sourcing**: Full audit trail and replay capability
- **Flexible Review Gates**: CLI, file-based, or auto-approve modes
- **Skills System**: Keyword-triggered domain knowledge injection

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    PWIWorkflowController                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ EventStream  │  │SessionAdapter│  │  ReviewHandler   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                         Agents                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │DataAnalyst │ │DataArchitect│ │MappingEng  │ │DQEngineer│ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
│  ┌────────────┐ ┌────────────┐                              │
│  │StoryWriter │ │ SyncAgent  │                              │
│  └────────────┘ └────────────┘                              │
├─────────────────────────────────────────────────────────────┤
│                         Tools                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │  DuckDB    │ │    CSV     │ │  Metadata  │ │ Artifact │ │
│  │  (4 tools) │ │ (3 tools)  │ │ (3 tools)  │ │ (4 tools)│ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Agent Control Loop

```python
while not state.is_complete:
    # 1. Build messages with context
    messages = agent._build_messages(state)

    # 2. Call LLM with tools
    response = llm.completion(messages, tools=agent.tools)

    # 3. Handle tool calls
    if response.tool_calls:
        for call in response.tool_calls:
            result = agent.execute_tool(call.name, call.arguments)
            state.tool_outputs.append(result)

    # 4. Extract final content
    else:
        state.artifacts[agent.ARTIFACT_TYPE] = response.content
        state.is_complete = True
```

### Event Flow

```
WorkflowStarted
    │
    ├──► AgentStarted (data_analyst)
    │       ├──► AgentToolCall (duckdb_tables)
    │       ├──► AgentToolResult
    │       └──► AgentCompleted
    │
    ├──► ReviewPending
    ├──► ReviewApproved
    │
    ├──► AgentStarted (data_architect)
    │       └──► AgentCompleted
    │
    ... (continues for all agents)
    │
    └──► WorkflowCompleted
```

---

## Quick Start

### Basic Usage

```python
from pwi.openhands.agents import (
    DataAnalystAgent,
    PWIAgentConfig,
    PWIAgentState,
)

# Create agent configuration
config = PWIAgentConfig(
    name="data_analyst",
    model="gpt-4o",
    temperature=0.7,
)

# Create agent
agent = DataAnalystAgent(config=config, llm_client=llm)

# Create initial state
state = PWIAgentState(
    session_id="session-001",
    business_request="Analyze healthcare patient data...",
)

# Run agent
result = await agent.run(state)

if result.success:
    print(f"Generated {result.artifact_type}: {len(result.artifact_content)} chars")
```

### Running Full Workflow

```python
from pwi.openhands.workflow import PWIWorkflowController

# Create controller
controller = PWIWorkflowController(
    session=session,
    session_manager=session_manager,
    config=pwi_config,
    llm_client=llm,
    auto_approve=False,  # Enable interactive review
)

# Run workflow
success = await controller.run()

if success:
    print("Workflow completed successfully!")
    print(f"Artifacts: {list(session.artifacts.keys())}")
```

---

## Agents

### Available Agents

| Agent | Artifact | Format | Required Inputs |
|-------|----------|--------|-----------------|
| `data_analyst` | DRD | markdown | None |
| `data_architect` | PAD | markdown | DRD |
| `mapping_engineer` | DMD | csv | DRD, PAD |
| `dq_engineer` | DQS | yaml | DRD, DMD |
| `story_writer` | Stories | markdown | DRD, PAD, DMD, DQS |
| `sync_agent` | Package | markdown | All above |

### Creating Agents

```python
from pwi.openhands.agents import get_agent, PWIAgentConfig

# Via factory function
config = PWIAgentConfig(name="data_analyst", model="gpt-4o")
agent = get_agent("data_analyst", config, llm_client)

# Direct instantiation
from pwi.openhands.agents import DataAnalystAgent
agent = DataAnalystAgent(config=config, llm_client=llm_client)
```

### Agent Tools

Each agent has access to specific tools:

```python
from pwi.openhands.tools import get_tools_for_agent

# Get tools for an agent
tools = get_tools_for_agent("data_analyst")
# Returns: [duckdb_query, duckdb_schema, duckdb_tables, analyze_csv, csv_stats]

tools = get_tools_for_agent("sync_agent")
# Returns: [generate_artifact, save_artifact, validate_artifact, list_artifact_types]
```

### Custom Agent

```python
from pwi.openhands.agents.base import BasePWIAgent, PWIAgentConfig

class CustomAgent(BasePWIAgent):
    AGENT_NAME = "custom_agent"
    ARTIFACT_TYPE = "custom"
    ARTIFACT_FORMAT = "markdown"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        return ["drd"]  # Requires DRD from previous agent

    def _get_default_prompt(self) -> str:
        return """You are a custom agent..."""
```

---

## Tools

### Tool Categories

#### DuckDB Tools (4)

| Tool | Description | Parameters |
|------|-------------|------------|
| `duckdb_query` | Execute SQL queries | `query`, `database_path` |
| `duckdb_schema` | Get table schema | `table_name`, `database_path` |
| `duckdb_tables` | List all tables | `database_path`, `schema` |
| `duckdb_validate` | Validate SQL syntax | `query` |

#### CSV Tools (3)

| Tool | Description | Parameters |
|------|-------------|------------|
| `analyze_csv` | Analyze CSV structure | `file_path` |
| `csv_stats` | Get column statistics | `file_path`, `columns` |
| `csv_sample` | Get sample rows | `file_path`, `n_rows` |

#### Metadata Tools (3)

| Tool | Description | Parameters |
|------|-------------|------------|
| `query_metadata_catalog` | Query metadata APIs | `catalog_type`, `query` |
| `get_lineage` | Get data lineage | `table_name`, `catalog_type` |
| `get_tags` | Get table/column tags | `table_name`, `catalog_type` |

#### Artifact Tools (4)

| Tool | Description | Parameters |
|------|-------------|------------|
| `generate_artifact` | Create structured artifact | `artifact_type`, `content`, `metadata` |
| `save_artifact` | Save to file | `artifact_type`, `content`, `output_dir` |
| `validate_artifact` | Validate format | `artifact_type`, `content` |
| `list_artifact_types` | List available types | None |

### Using Tools

```python
from pwi.openhands.tools import get_registry

registry = get_registry()

# Execute a tool
result = registry.execute(
    "duckdb_query",
    query="SELECT * FROM synthea.patients LIMIT 5",
    database_path="../data/duckdb/raw.db"
)

# List all tools
print(registry.tool_names)
```

### Registering Custom Tools

```python
from pwi.openhands.tools.base import create_tool, register_tool

# Define tool schema
CustomTool = create_tool(
    name="custom_tool",
    description="Does something custom",
    parameters={
        "param1": {"type": "string", "description": "First param"},
        "param2": {"type": "integer", "description": "Second param"},
    },
    required=["param1"],
)

# Define executor
def execute_custom_tool(param1: str, param2: int = 10):
    return {"success": True, "result": f"{param1}: {param2}"}

# Register
register_tool(CustomTool, execute_custom_tool)
```

---

## Workflow Orchestration

### Event Stream

The `EventStream` provides event-sourced state management:

```python
from pwi.openhands.workflow.events import (
    EventStream,
    WorkflowStartedEvent,
    AgentCompletedEvent,
)

# Create stream
stream = EventStream(session_id="session-001")

# Append events
stream.append(WorkflowStartedEvent(session_id="session-001"))

# Query events
completed = stream.get_events(event_type=PWIEventType.AGENT_COMPLETED)
last_event = stream.get_last_event()

# Serialize for persistence
data = stream.to_dict()

# Restore from serialized
restored = EventStream.from_dict("session-001", data)
```

### Review Handlers

```python
from pwi.openhands.workflow.review_handler import get_review_handler

# CLI interactive review
handler = get_review_handler("cli")

# File-based review (writes to disk, waits for approval file)
handler = get_review_handler("file", review_dir=Path("./review"))

# Auto-approve all
handler = get_review_handler("auto")

# Skip reviews entirely
handler = get_review_handler("skip")
```

### Session Adapter

Bridges PWI Session with EventStream:

```python
from pwi.openhands.workflow import SessionEventAdapter

adapter = SessionEventAdapter(
    session=session,
    session_manager=session_manager,
)

# Emit events (automatically updates session)
adapter.emit_workflow_started()
adapter.emit_agent_completed(
    agent_name="data_analyst",
    artifact_type="drd",
    artifact_format="markdown",
    prompt_tokens=1000,
    completion_tokens=500,
)

# Query state
completed_agents = adapter.get_completed_agents()
pending_review = adapter.get_pending_review_agent()
```

---

## Skills/Microagents

### Location

Skills are stored in `.openhands/microagents/` with YAML frontmatter:

```
.openhands/microagents/
├── repo.md              # Always loaded (type: repo)
├── data_analyst.md      # Keyword triggered
├── data_architect.md
├── mapping_engineer.md
├── dq_engineer.md
├── story_writer.md
└── sync_agent.md
```

### Skill Format

```markdown
---
name: data_analyst
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
  - DRD
  - data requirements
  - business request
---

# Data Analyst Agent

You are a Senior Data Analyst specializing in...

## Your Responsibilities
1. Analyze business requests
2. Identify data sources
...
```

### Trigger Types

| Type | Behavior |
|------|----------|
| `repo` | Always loaded for the repository |
| `knowledge` | Triggered by keywords in user input |

---

## Configuration

### Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=gpt-4o

# OpenHands Runtime
OPENHANDS_RUNTIME=local  # or "docker"
OPENHANDS_WORKSPACE=/workspace
```

### PWI Configuration

```yaml
# pwi.yaml
project:
  name: "healthcare-pipeline"
  output_dir: "output"

agents:
  data_analyst:
    model: "gpt-4o"
    temperature: 0.7
    max_tokens: 4096
  data_architect:
    model: "gpt-4o"
    temperature: 0.7
    max_tokens: 4096
  # ... other agents

review:
  enabled: true
  mode: "cli"  # cli, file, auto, skip
  timeout_minutes: 30
```

### OpenHandsConfig

```python
from pwi.openhands.config import OpenHandsConfig

# From environment
config = OpenHandsConfig.from_env()

# From PWI config
config = OpenHandsConfig.from_pwi_config(pwi_config)

# Get agent-specific config
agent_config = config.get_agent_config("data_analyst")
```

---

## Migration from Legacy

### Compatibility

The OpenHands implementation runs alongside the legacy code. Use the `USE_OPENHANDS` flag:

```python
import os

if os.getenv("USE_OPENHANDS", "false").lower() == "true":
    from pwi.openhands.workflow import PWIWorkflowController
    controller = PWIWorkflowController(...)
else:
    from pwi.workflow.orchestrator import WorkflowOrchestrator
    controller = WorkflowOrchestrator(...)
```

### Key Differences

| Legacy | OpenHands |
|--------|-----------|
| `BaseAgent` | `BasePWIAgent` |
| `AgentConfig` | `PWIAgentConfig` |
| `AgentResult` | `PWIAgentResult` |
| `Session.artifacts` | `PWIAgentState.artifacts` |
| `PWIWorkflow` (transitions) | `EventStream` |
| `WorkflowOrchestrator` | `PWIWorkflowController` |

### Migrating Custom Agents

Before:
```python
from pwi.agents.base import BaseAgent

class MyAgent(BaseAgent):
    AGENT_NAME = "my_agent"

    def get_required_inputs(self):
        return ["drd"]

    def _get_default_prompt(self):
        return "..."
```

After:
```python
from pwi.openhands.agents.base import BasePWIAgent

class MyAgent(BasePWIAgent):
    AGENT_NAME = "my_agent"

    def get_required_inputs(self):
        return ["drd"]

    def _get_default_prompt(self):
        return "..."

    # Now has access to self.tools, self.execute_tool(), etc.
```

---

## API Reference

### pwi.openhands.agents

```python
# Classes
BasePWIAgent          # Base class for all agents
PWIAgentConfig        # Agent configuration
PWIAgentState         # Agent execution state
PWIAgentResult        # Agent execution result

# Agent Classes
DataAnalystAgent
DataArchitectAgent
MappingEngineerAgent
DQEngineerAgent
StoryWriterAgent
SyncAgent

# Functions
get_agent(name, config, llm_client) -> BasePWIAgent
get_agent_sequence() -> list[str]
get_agent_info(name) -> dict
list_agents() -> list[dict]

# Constants
AGENT_REGISTRY: dict[str, type]
AGENT_SEQUENCE: list[str]
```

### pwi.openhands.tools

```python
# Classes
ToolRegistry           # Tool management

# Functions
get_registry() -> ToolRegistry
get_all_tools() -> list
get_tools_for_agent(name) -> list
create_tool(name, description, parameters, required) -> ChatCompletionToolParam
register_tool(tool, executor) -> None
```

### pwi.openhands.workflow

```python
# Classes
PWIWorkflowController  # Main orchestration
EventStream           # Event-sourced state
SessionEventAdapter   # Session-Event bridge

# Event Classes
PWIEvent              # Base event
WorkflowStartedEvent
WorkflowCompletedEvent
AgentStartedEvent
AgentCompletedEvent
ReviewPendingEvent
ReviewApprovedEvent
# ... and more

# Review Handlers
BaseReviewHandler
CLIReviewHandler
FileReviewHandler
AutoApproveHandler
SkipReviewHandler

# Functions
get_review_handler(mode, **kwargs) -> BaseReviewHandler
```

---

## Testing

Run integration tests:

```bash
# All OpenHands tests
uv run pytest tests/integration/test_openhands_integration.py -v

# With coverage
uv run pytest tests/integration/test_openhands_integration.py -v --cov=pwi.openhands
```

---

## Troubleshooting

### Common Issues

**DuckDB not found**
```
Error: No module named 'duckdb'
```
Solution: `uv add duckdb`

**Tool not registered**
```
ValueError: Tool not found: custom_tool
```
Solution: Ensure the tool module is imported to trigger auto-registration.

**Review timeout**
```
Review timed out after 30 minutes
```
Solution: Increase `review.timeout_minutes` in config or use `auto_approve=True`.

---

## Changelog

### Phase 8 (Current)
- Added OpenHands SDK integration
- Implemented 14 custom tools
- Migrated 6 agents to tool-use pattern
- Added event-sourced state management
- Created Skills/Microagents system
- Full backward compatibility maintained
