# PWI Quickstart Guide

This guide will help you get started with PWI (Planning with Intent) in under 5 minutes.

## Prerequisites

- Python 3.10 or later
- UV package manager
- An OpenAI-compatible API key (OpenAI, OpenRouter, etc.)

## Installation

```bash
# Navigate to the chapter-4 directory
cd chapter-4

# Install dependencies with UV
uv sync

# Verify installation
uv run pwi --version
```

## Configuration

### Option 1: Environment Variables

Set the required environment variables:

```bash
export LLM_API_KEY=your-api-key
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=gpt-4o-mini
```

For OpenRouter:

```bash
export LLM_API_KEY=your-openrouter-key
export LLM_BASE_URL=https://openrouter.ai/api/v1
export LLM_MODEL=openai/gpt-4o-mini
```

### Option 2: Configuration File

Create a `.env` file in the chapter-4 directory:

```
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

Or initialize with a configuration file:

```bash
uv run pwi init --type data_engineering
```

This creates a `pwi.yaml` configuration file.

## Your First Workflow

### 1. Create a Request File

Create a file `requests/my-request.md`:

```markdown
# Customer 360 Analytics Platform

## Business Context
We need to build a customer analytics platform that integrates data from
our CRM, support tickets, and purchase history to create a unified customer view.

## Objectives
- Consolidate customer data from multiple sources
- Enable real-time customer segmentation
- Support churn prediction modeling

## Data Sources
- Salesforce CRM (customer profiles, interactions)
- Zendesk (support tickets)
- Stripe (transactions, subscriptions)

## Expected Outcomes
- Customer master data entity
- Activity timeline
- Risk scoring metrics
```

### 2. Run the Workflow

```bash
# Run the full planning workflow
uv run pwi plan run requests/my-request.md

# Or run with auto-approve to skip review gates
uv run pwi plan run requests/my-request.md --auto-approve
```

### 3. Monitor Progress

The workflow runs 6 agents in sequence:

1. **Data Analyst** - Generates Data Requirements Document (DRD)
2. **Data Architect** - Creates Pipeline Architecture Document (PAD)
3. **Mapping Engineer** - Produces Data Mapping Document (DMD) as CSV
4. **DQ Engineer** - Generates Data Quality Specification (DQS) as YAML
5. **Story Writer** - Creates Epics and User Stories
6. **Sync Agent** - Packages final deliverables

### 4. View Results

```bash
# List all sessions
uv run pwi session list

# View session details
uv run pwi session status <session-id>

# Artifacts are exported to output/<session-id>/
```

## Using the Dashboard

Start the web dashboard for a visual interface:

```bash
uv run pwi dashboard
```

Open http://127.0.0.1:8080 in your browser to:
- View all sessions
- Monitor workflow progress
- Review and approve artifacts
- Export results

## Using the OpenHands GUI (Alternative)

For a more interactive experience, you can use the OpenHands web interface to run individual PWI agents on-demand. This is a full alternative to the CLI.

### Quick Start

```bash
# Configure your LLM API key in .env
echo 'LLM_API_KEY=your-key-here' > .env
echo 'LLM_BASE_URL=https://openrouter.ai/api/v1' >> .env
echo 'LLM_MODEL=openrouter/anthropic/claude-3.5-haiku' >> .env

# Start the OpenHands GUI
./scripts/start-openhands-gui.sh

# Open http://localhost:3000 in your browser
```

### Example Prompts

Once in the GUI, try these prompts to interact with PWI agents:

| What You Want | Example Prompt |
|--------------|----------------|
| Generate DRD | "Generate a DRD for the data described in my request" |
| Explore data | "List all tables in the database" |
| Get schema | "Show me the schema for <schema>.<table>" |
| Create PAD | "Create a PAD based on this DRD: [paste DRD content]" |
| Validate | "Validate this DRD: [paste content]" |

### When to Use GUI vs CLI

| Use Case | Recommended |
|----------|-------------|
| Full pipeline workflow | CLI (`pwi plan run`) |
| Individual agent on-demand | GUI |
| Exploring data interactively | GUI |
| Automated pipelines | CLI |
| Real-time tool visualization | GUI |

See [OpenHands GUI Guide](openhands-gui.md) for detailed documentation.

## Common Commands

```bash
# Initialize project
uv run pwi init --type data_engineering

# Run workflow
uv run pwi plan run <request.md>

# Run with options
uv run pwi plan run <request.md> --auto-approve --project-name "My Project"

# Session management
uv run pwi session list
uv run pwi session status <id>
uv run pwi session resume <id>
uv run pwi session delete <id>

# Review commands
uv run pwi review show <id>
uv run pwi review approve <id>
uv run pwi review reject <id> --reason "Needs more detail"

# Start dashboard
uv run pwi dashboard --port 8080
```

## Next Steps

- Read the [CLI Reference](cli-reference.md) for detailed command documentation
- See [Configuration Guide](configuration.md) for advanced configuration options
- Try the [OpenHands GUI](openhands-gui.md) for an interactive web interface
- Explore the generated artifacts in the `output/` directory
