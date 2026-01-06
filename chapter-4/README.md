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
- **Tool-Use Capabilities**: Agents can query DuckDB, analyze CSVs, and call external APIs (OpenHands SDK)

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

| Agent | Artifact | Format | Description |
|-------|----------|--------|-------------|
| Data Analyst | DRD | Markdown | Data Requirements Document |
| Data Architect | PAD | Markdown | Pipeline Architecture Document |
| Mapping Engineer | DMD | CSV | Data Mapping Document |
| DQ Engineer | DQS | YAML | Data Quality Specification |
| Story Writer | Stories | Markdown | User Stories & Epics |
| Sync Agent | Package | Markdown | Delivery Package Summary |

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

PWI now includes OpenHands SDK integration for tool-use capabilities:

```python
from pwi.openhands.agents import DataAnalystAgent, PWIAgentConfig
from pwi.openhands.tools import get_tools_for_agent

# Agents have access to tools
config = PWIAgentConfig(name="data_analyst", model="gpt-4o")
agent = DataAnalystAgent(config=config, llm_client=llm)

print(agent.tool_names)
# ['duckdb_query', 'duckdb_schema', 'duckdb_tables', 'analyze_csv', 'csv_stats']
```

### Available Tools (14)

| Category | Tools |
|----------|-------|
| DuckDB | `duckdb_query`, `duckdb_schema`, `duckdb_validate`, `duckdb_tables` |
| CSV | `analyze_csv`, `csv_stats`, `csv_sample` |
| Metadata | `query_metadata_catalog`, `get_lineage`, `get_tags` |
| Artifact | `generate_artifact`, `save_artifact`, `validate_artifact`, `list_artifact_types` |

See [docs/openhands_migration.md](docs/openhands_migration.md) for full documentation.

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
