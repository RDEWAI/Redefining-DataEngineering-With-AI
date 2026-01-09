# OpenHands GUI Integration Guide

This guide explains how to use the OpenHands web interface with PWI (Planning with Intent) for running individual agents on-demand through a visual interface.

## Overview

The OpenHands GUI provides a chat-like interface for interacting with PWI agents. Instead of using the CLI, you can:

- Run individual agents on-demand (data_analyst, data_architect, etc.)
- View tool calls and results in real-time
- Manage multiple conversations
- Access all PWI custom tools through the visual interface

## Prerequisites

- **Docker**: Install from [docker.com](https://docker.com)
- **Docker Compose**: Usually included with Docker Desktop
- **LLM API Key**: From OpenRouter, OpenAI, Anthropic, or compatible provider

## Quick Start

### 1. Configure Environment

Create or update your `.env` file in the `chapter-4` directory:

```bash
cd chapter-4

# Create .env file
cat > .env << 'EOF'
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openrouter/anthropic/claude-3.5-haiku
EOF
```

### 2. Start the GUI

```bash
./scripts/start-openhands-gui.sh
```

Or manually with Docker Compose:

```bash
docker-compose -f docker-compose.openhands.yml up --build -d
```

### 3. Access the Interface

Open your browser to: **http://localhost:3000**

### 4. Stop the GUI

```bash
./scripts/stop-openhands-gui.sh
```

Or manually:

```bash
docker-compose -f docker-compose.openhands.yml down
```

## Available PWI Agents

The following PWI agents are available in the GUI:

| Agent | Purpose | Example Prompt |
|-------|---------|----------------|
| **data_analyst** | Generate Data Requirements Documents (DRD) | "Generate a DRD for the data described in my request" |
| **data_architect** | Create Pipeline Architecture Documents (PAD) | "Create a PAD based on this DRD: [paste DRD]" |
| **mapping_engineer** | Build Data Mapping Documents (DMD) | "Build a DMD mapping for the source tables" |
| **dq_engineer** | Define Data Quality Specifications (DQS) | "Define DQS rules for the data quality" |
| **story_writer** | Write User Stories and Epics | "Write user stories for the data pipeline" |
| **sync_agent** | Create Consolidated Packages | "Create a package from all artifacts" |
| **validator_agent** | Validate Artifacts | "Validate this DRD: [paste content]" |

## Using Agents via Keywords

Agents are triggered by keywords in your prompts. You can use these trigger keywords:

- **data_analyst**: "DRD", "data requirements", "business request", "requirements document"
- **data_architect**: "PAD", "pipeline architecture", "architecture document"
- **mapping_engineer**: "DMD", "data mapping", "field mapping", "source to target"
- **dq_engineer**: "DQS", "data quality", "quality rules", "validation rules"
- **story_writer**: "user stories", "epics", "acceptance criteria"
- **validator_agent**: "validate", "check", "verify artifact"

## Available Tools

PWI provides 18 custom tools available in the GUI:

### DuckDB Tools
- `duckdb_query` - Execute SQL queries
- `duckdb_schema` - Get table schema information
- `duckdb_tables` - List all tables
- `duckdb_validate` - Validate SQL syntax

### CSV Tools
- `analyze_csv` - Analyze CSV file structure
- `csv_stats` - Get statistics for CSV columns
- `csv_sample` - Get sample rows from CSV

### Metadata Tools
- `query_metadata_catalog` - Query metadata catalog
- `get_lineage` - Get data lineage information
- `get_tags` - Get tags for data assets

### Artifact Tools
- `generate_artifact` - Generate PWI artifacts
- `save_artifact` - Save artifacts to files
- `validate_artifact` - Validate artifact format
- `list_artifact_types` - List available artifact types

## Example Workflows

### Generate a DRD

1. Start a new conversation
2. Enter: "Generate a DRD for the data. First explore the available tables."
3. The agent will:
   - Call `duckdb_tables` to list available tables
   - Call `duckdb_schema` on relevant tables
   - Generate the complete DRD document

### Explore the Database

1. Enter: "What tables are available in the database?"
2. The agent calls `duckdb_tables` and shows results
3. Follow up with: "Show me the schema for <schema>.<table>"

### Validate Artifacts

1. Enter: "Validate this DRD:" followed by pasting your DRD content
2. The validator_agent checks format and content requirements

## Configuration

### LLM Settings

Configure your LLM provider in `.env`:

```bash
# OpenRouter (recommended)
LLM_API_KEY=your-openrouter-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openrouter/anthropic/claude-3.5-haiku

# OpenAI
LLM_API_KEY=your-openai-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Anthropic
LLM_API_KEY=your-anthropic-key
LLM_BASE_URL=https://api.anthropic.com
LLM_MODEL=claude-3-5-sonnet-20241022
```

### Database Path

The DuckDB database path is configured via the `DUCKDB_PATH` environment variable. Set this to your project's database location.

### Workspace

The `chapter-4` directory is mounted at `/workspace` in the container. Generated files are saved there and accessible on your host machine.

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs openhands-pwi

# Check if port 3000 is in use
lsof -i :3000
```

### Tools Not Available

If tools aren't showing up, check the startup logs:

```bash
docker logs openhands-pwi | grep -i "registered"
```

You should see output like:
```
Registered 14 tools with SDK
```

### Database Connection Issues

Ensure the database file exists at the path specified in `DUCKDB_PATH`:

```bash
ls -la $DUCKDB_PATH
```

If missing, ensure your data is loaded into DuckDB first.

### API Key Errors

Verify your API key is set:

```bash
echo $LLM_API_KEY
```

Check the `.env` file doesn't have quotes around values.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (localhost:3000)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              OpenHands GUI (Docker Container)                │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              OpenHands Server (FastAPI)                 ││
│  │  ┌─────────────────┐  ┌──────────────────────────────┐ ││
│  │  │  React Frontend │  │       Agent Runtime          │ ││
│  │  └─────────────────┘  │  ┌──────────────────────────┐│ ││
│  │                       │  │     PWI Tools (14)       ││ ││
│  │                       │  │ ┌──────┐ ┌──────┐ ┌────┐ ││ ││
│  │                       │  │ │DuckDB│ │ CSV  │ │Meta│ ││ ││
│  │                       │  │ └──────┘ └──────┘ └────┘ ││ ││
│  │                       │  └──────────────────────────┘│ ││
│  │                       │  ┌──────────────────────────┐│ ││
│  │                       │  │   PWI Microagents (7)    ││ ││
│  │                       │  └──────────────────────────┘│ ││
│  │                       │  ┌──────────────────────────┐│ ││
│  │                       │  │    PWI Skills (5)        ││ ││
│  │                       │  └──────────────────────────┘│ ││
│  │                       └──────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│                              ▼                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Mounted Volumes                            ││
│  │  /workspace → chapter-4/ (read/write)                   ││
│  │  /workspace/data → data/ (read-only)                    ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  LLM Provider   │
                    │   (OpenRouter)  │
                    └─────────────────┘
```

## Comparison: GUI vs CLI

| Feature | GUI | CLI |
|---------|-----|-----|
| Individual agent runs | ✅ Full support | ✅ Full support |
| Full pipeline workflow | ❌ Manual steps | ✅ Automated |
| Real-time tool visualization | ✅ | ❌ |
| Multiple conversations | ✅ | ❌ |
| Session management | OpenHands native | PWI sessions |
| Review gates | ❌ | ✅ |
| Artifact validation | ✅ On-demand | ✅ Automated |

## Next Steps

- [Quickstart Guide](quickstart.md) - CLI-based workflows
- [Extensibility Guide](EXTENSIBILITY.md) - Add custom tools and agents
- [OpenHands SDK Reference](OPENHANDS_SDK_REFERENCE.md) - SDK documentation
