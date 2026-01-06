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
```

## CLI Commands

- `pwi init` - Initialize a new project
- `pwi plan run <request.md>` - Run planning workflow
- `pwi session list` - List all sessions
- `pwi session status <id>` - Show session status
- `pwi review show <id>` - Show pending review
- `pwi review approve <id>` - Approve artifact
- `pwi dashboard` - Start web UI

## Development

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=pwi
```
