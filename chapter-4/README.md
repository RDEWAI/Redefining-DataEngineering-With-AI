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
- **File-Based Session Storage**: Each session stored as a directory with individual artifact files
- **Modular Validation System**: Artifact-specific validators (DMD, DQS, DRD, PAD) with format and content checks
- **Session Persistence**: Resume workflows, track progress
- **Review Gates**: CLI, file-based, or web review
- **Multi-Model Support**: Configure different LLM models per agent via OpenRouter
- **Tool-Use Capabilities**: Exploration agents can query DuckDB, analyze CSVs (OpenHands SDK)
- **Skills/Context Injection**: DuckDB knowledge skill auto-triggers for relevant queries
- **Validation Skills**: Auto-triggered validation knowledge for each artifact type
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
- **drd_validation**: DRD format requirements, required sections
- **dmd_validation**: DMD 13-column CSV format, layer values
- **dqs_validation**: DQS YAML structure, quality dimensions
- **pad_validation**: PAD sections, Mermaid diagram requirements

### Available Domain Tools (18)

| Category | Tools |
|----------|-------|
| DuckDB | `duckdb_query`, `duckdb_schema`, `duckdb_validate`, `duckdb_tables` |
| CSV | `analyze_csv`, `csv_stats`, `csv_sample` |
| Metadata | `query_metadata_catalog`, `get_lineage`, `get_tags` |
| Artifact | `generate_artifact`, `save_artifact`, `validate_artifact`, `list_artifact_types` |
| Validation | `validate_drd`, `validate_pad`, `validate_dmd`, `validate_dqs` |

See [docs/OPENHANDS_SDK_REFERENCE.md](docs/OPENHANDS_SDK_REFERENCE.md) for SDK documentation.

## Session Storage

Sessions use file-based storage with each session as a directory containing individual artifact files:

```
.pwi/sessions/
└── abc12345/                 # Session directory
    ├── session.json          # Metadata (state, timestamps, agent info)
    ├── drd.md                # Data Requirements Document
    ├── pad.md                # Pipeline Architecture Document
    ├── dmd.csv               # Data Mapping Document (13 columns)
    ├── dqs.yaml              # Data Quality Specification
    ├── stories.md            # User Stories
    └── package.md            # Final Delivery Package
```

**Benefits:**
- Artifacts viewable/editable directly in filesystem
- Smaller JSON files (metadata only)
- Clean git diffs
- Individual artifact versioning

### Migrating Existing Sessions

If you have existing sessions in the old inline format, run the migration script:

```bash
# Preview changes
python scripts/migrate_sessions.py --dry-run

# Execute migration
python scripts/migrate_sessions.py

# Migrate specific session
python scripts/migrate_sessions.py --session abc12345
```

## Artifact Validation

PWI includes a modular validation system for checking artifact quality:

```python
from pwi.openhands.tools.validation import validate_artifact

# Validate a DMD artifact
result = validate_artifact("dmd", csv_content)
print(f"Valid: {result.is_valid}")
print(f"Errors: {result.error_count}, Warnings: {result.warning_count}")

# With cross-reference validation
result = validate_artifact("dmd", csv_content, context={"drd": drd_content})
```

### Validation Checks by Artifact Type

| Artifact | Format Checks | Content Checks |
|----------|--------------|----------------|
| DRD | Markdown header, no code fences | Required sections, no placeholders |
| PAD | Markdown header, Mermaid diagrams | Layer definitions, technology stack |
| DMD | 13-column CSV, column order | Layer values (bronze/silver/gold) |
| DQS | YAML syntax, version header | Quality dimensions, gates |

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
│   │   │   └── validation/ # Artifact validators (DMD, DQS, DRD, PAD)
│   │   └── workflow/       # Event-sourced orchestration
│   ├── cli/                # Command-line interface
│   ├── dashboard/          # NiceGUI web interface
│   └── workflow/           # Session & state management
├── .openhands/
│   ├── microagents/        # Agent prompts/personas
│   └── skills/             # Contextual knowledge (DuckDB, validation)
├── .pwi/
│   └── sessions/           # Session storage (directory per session)
├── scripts/                # Utility scripts (migration, etc.)
├── docs/                   # Documentation
├── tests/                  # Test suite
└── requests/               # Sample business requests
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Quick Start](docs/quickstart.md) | Get up and running in 5 minutes |
| [CLI Reference](docs/cli-reference.md) | Complete command reference |
| [Workflow Guide](docs/WORKFLOW_GUIDE.md) | Pipeline execution, state machine, review gates, sessions |
| [Extensibility Guide](docs/EXTENSIBILITY.md) | Add custom tools, skills, and agents (step-by-step tutorials) |
| [OpenHands SDK Reference](docs/OPENHANDS_SDK_REFERENCE.md) | SDK integration details |
| [Migration Guide](docs/openhands_migration.md) | Migrate from legacy agents |
