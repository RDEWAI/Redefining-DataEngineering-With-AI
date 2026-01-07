# PWI - Planning with Intent

Transform business requests into structured Data Engineering artifacts through an AI-powered agent workflow.

## Installation

```bash
cd chapter-4
uv sync
```

## Quick Start

```bash
# Initialize a new project
pwi init --type data_engineering

# Run the planning workflow
pwi plan run requests/my-request.md

# Check session status
pwi session list
```

## Features

- **6 Specialized Agents**: Data Analyst, Data Architect, Mapping Engineer, DQ Engineer, Story Writer, Sync Agent
- **Artifact Generation**: DRD, PAD, DMD (CSV), DQS (YAML), Epics & Stories
- **Session Persistence**: Resume workflows, track progress
- **Review Gates**: CLI, file-based, or web review
- **Multi-Model Support**: Configure different LLM models per agent via OpenRouter
- **Tool-Use Capabilities**: Exploration agents can query DuckDB, analyze CSVs (OpenHands SDK)
- **Skills/Context Injection**: DuckDB knowledge skill auto-triggers for relevant queries
- **Artifact-Only Agents**: Some agents generate artifacts directly without tools to prevent exploration loops

## Architecture

```
Business Request
       ↓
┌──────────────────────────────────────────────────────────────┐
│                    PWI Workflow Controller                    │
├──────────────────────────────────────────────────────────────┤
│  data_analyst → data_architect → mapping_engineer →          │
│  dq_engineer → story_writer → sync_agent                     │
├──────────────────────────────────────────────────────────────┤
│  Tools: DuckDB | CSV Analysis | Metadata APIs | Artifacts    │
└──────────────────────────────────────────────────────────────┘
       ↓
DRD → PAD → DMD → DQS → Stories → Package
```

## Agent Pipeline

| Agent | Artifact | Format | Tools | Description |
|-------|----------|--------|-------|-------------|
| Data Analyst | DRD | Markdown | DuckDB, CSV | Explores data schema and generates requirements |
| Data Architect | PAD | Markdown | file_editor | Generates architecture from DRD context |
| Mapping Engineer | DMD | CSV | DuckDB, CSV, Metadata | Maps source to target fields |
| DQ Engineer | DQS | YAML | None | Outputs YAML directly from DRD+DMD context |
| Story Writer | Stories | Markdown | file_editor | Generates stories from all artifacts |
| Sync Agent | Package | Markdown | None | Consolidates all artifacts into package |

**Note**: Agents with "None" tools output artifacts directly as text to prevent exploration loops.

## Configuration

Create a `pwi.yaml` file or run `pwi init` to generate one:

```yaml
llm:
  provider: "openrouter"
  api_key: "${OPENROUTER_API_KEY}"
  default_model: "anthropic/claude-3-5-sonnet"

agents:
  data_analyst:
    model: "balanced"
    temperature: 0.7

review:
  enabled: true
  mode: "cli"  # cli, file, auto, skip
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `pwi init` | Initialize a new project |
| `pwi plan run <request.md>` | Run planning workflow |
| `pwi session list` | List all sessions |
| `pwi session status <id>` | Show session status |
| `pwi session resume <id>` | Resume a paused session |
| `pwi review show <id>` | Show pending review |
| `pwi review approve <id>` | Approve artifact |
| `pwi dashboard` | Start web UI |

## OpenHands SDK Integration

PWI uses the OpenHands SDK for agent orchestration with tool-use capabilities:

```python
from pwi.openhands.agents import create_pwi_agent, create_pwi_conversation
from pwi.openhands.tools import AGENT_TOOL_MAP

# Create an agent with auto-configured tools
agent = create_pwi_agent("data_analyst", llm_config={"model": "openai/gpt-4o-mini"})
conversation = create_pwi_conversation(agent, workspace="./output")

# Check available tools for each agent
print(AGENT_TOOL_MAP["data_analyst"])
# ['terminal', 'file_editor', 'task_tracker', 'duckdb_query', 'duckdb_schema', ...]

print(AGENT_TOOL_MAP["dq_engineer"])
# []  # No tools - outputs artifact directly
```

### Agent Tool Configuration

| Agent | Tools | Behavior |
|-------|-------|----------|
| data_analyst | DuckDB, CSV, terminal, file_editor | Explores data, generates DRD |
| data_architect | file_editor, task_tracker | Generates PAD from DRD context |
| mapping_engineer | DuckDB, CSV, Metadata, terminal | Maps fields with schema exploration |
| dq_engineer | **None** | Outputs DQS YAML directly |
| story_writer | file_editor, task_tracker | Generates stories from context |
| sync_agent | **None** | Outputs Package directly |

### Skills (Contextual Knowledge)

Agents receive contextual knowledge via Skills that auto-trigger on keywords:

- **duckdb**: DuckDB query patterns, table schemas, SQL syntax

### Available Domain Tools (14)

| Category | Tools |
|----------|-------|
| DuckDB | `duckdb_query`, `duckdb_schema`, `duckdb_validate`, `duckdb_tables` |
| CSV | `analyze_csv`, `csv_stats`, `csv_sample` |
| Metadata | `query_metadata_catalog`, `get_lineage`, `get_tags` |
| Artifact | `generate_artifact`, `save_artifact`, `validate_artifact`, `list_artifact_types` |

See [docs/OPENHANDS_SDK_REFERENCE.md](docs/OPENHANDS_SDK_REFERENCE.md) for SDK documentation.

## Development

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=pwi

# Run OpenHands integration tests
uv run pytest tests/integration/test_openhands_integration.py -v

# Validate OpenHands modules
uv run python -c "from pwi.openhands.agents import list_agents; print(list_agents())"
```

## Project Structure

```
chapter-4/
├── pwi/                    # Main package
│   ├── agents/             # Legacy agent implementations
│   ├── openhands/          # OpenHands SDK integration
│   │   ├── agents/         # Tool-enabled agents
│   │   ├── tools/          # Custom tools (DuckDB, CSV, etc.)
│   │   └── workflow/       # Event-sourced orchestration
│   ├── cli/                # Command-line interface
│   ├── dashboard/          # NiceGUI web interface
│   └── workflow/           # Session & state management
├── .openhands/
│   └── microagents/        # Skills/Microagents for OpenHands
├── docs/                   # Documentation
├── tests/                  # Test suite
└── requests/               # Sample business requests
```

## Documentation

- [Quick Start Guide](docs/quickstart.md)
- [CLI Reference](docs/cli-reference.md)
- [OpenHands Migration Guide](docs/openhands_migration.md)
