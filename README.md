# Redefining Data Engineering with AI

> **AI-Powered Data Engineering Development Environment**
> A Docker-based development environment with integrated AI task management, combining Python 3.11, Java 11, PySpark, DuckDB, and modern AI development tools.

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://www.python.org/)
[![Task Master](https://img.shields.io/badge/Task%20Master-AI-orange)](https://www.npmjs.com/package/task-master-ai)

---

## 📋 Table of Contents

- [Quick Start (5 Minutes)](#-quick-start-5-minutes)
- [Project Overview](#-project-overview)
- [Task Master AI Setup](#-task-master-ai-setup)
- [MCP Server Configuration](#-mcp-server-configuration)
- [Docker Development Environment](#-docker-development-environment)
- [IDE Integration](#-ide-integration)
- [Project Structure](#-project-structure)
- [Development Workflow](#-development-workflow)
- [Common Commands](#-common-commands)
- [Troubleshooting](#-troubleshooting)
- [Advanced Topics](#-advanced-topics)
- [Appendix](#-appendix)

---

## 🚀 Quick Start (5 Minutes)

For experienced developers, here's the fastest way to get started:

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd Redefining-DataEngineering-With-AI

# 2. Install Task Master globally
npm install -g task-master-ai

# 3. Initialize Task Master with Claude Code integration
task-master init --rules claude

# 4. Start Docker environment
docker compose up -d

# 5. Verify the environment
./scripts/test-environment.sh

# 6. Open in Claude Code and start working
claude
```

✅ **You're ready!** Run `task-master next` to see your first task.

---

## 💡 Project Overview

### Purpose

This project creates a production-ready, AI-enhanced data engineering development environment that combines:
- **Containerized Infrastructure**: Docker-based environment for consistency across platforms
- **Modern Data Stack**: PySpark, DuckDB, Apache Superset for data processing and visualization
- **AI Task Management**: Task Master AI for intelligent project planning and execution
- **IDE Integration**: Seamless integration with VS Code, Cursor, and Claude Code

### Technology Stack

| Category | Technologies |
|----------|-------------|
| **Runtime** | Python 3.11, Java 11 (Eclipse Temurin) |
| **Data Processing** | PySpark 3.5.4, DuckDB, SQLGlot |
| **Cloud Integration** | Google Cloud BigQuery, Cloud Storage |
| **Visualization** | Apache Superset 4.1.1 |
| **Testing** | pytest |
| **AI Tools** | Task Master AI, Claude Code |
| **Container** | Docker, Docker Compose |
| **IDE** | VS Code, Cursor (with DevContainer support) |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Development Machine                      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Claude Code  │  │   VS Code    │  │    Cursor    │      │
│  │    (CLI)     │  │ DevContainer │  │ DevContainer │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
│         ┌──────────────────┴───────────────────┐            │
│         │         Task Master AI                │            │
│         │    (.taskmaster/ + CLAUDE.md)         │            │
│         └──────────────────┬───────────────────┘            │
│                            │                                 │
│    ┌───────────────────────┴────────────────────────┐       │
│    │          Docker Environment                     │       │
│    │  ┌────────────────────────────────────────┐    │       │
│    │  │   rdewai-dev Container                 │    │       │
│    │  │                                        │    │       │
│    │  │  • Python 3.11 + Java 11              │    │       │
│    │  │  • PySpark + DuckDB                   │    │       │
│    │  │  • Apache Superset                    │    │       │
│    │  │  • Google Cloud SDKs                  │    │       │
│    │  │                                        │    │       │
│    │  │  Volumes:                              │    │       │
│    │  │  - ./workspace → /workspace           │    │       │
│    │  │  - rdewai-data → /data                │    │       │
│    │  │  - rdewai-cache → /root/.cache        │    │       │
│    │  └────────────────────────────────────────┘    │       │
│    └─────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 Task Master AI Setup

Task Master AI is a powerful CLI tool that helps manage project tasks with AI-powered assistance, integrated seamlessly with Claude Code.

### Prerequisites

- **Node.js** 16+ ([Download](https://nodejs.org/))
- **npm** (comes with Node.js)

### Installation

```bash
# Install Task Master globally
npm install -g task-master-ai

# Verify installation
task-master --version
```

### Initialization

The `--rules claude` flag creates a `CLAUDE.md` file that Claude Code automatically loads for context:

```bash
# Initialize Task Master with Claude Code integration
task-master init --rules claude
```

**What this does:**
- ✅ Creates `.taskmaster/` directory structure
- ✅ Generates `CLAUDE.md` with AI instructions
- ✅ Sets up `tasks.json` for task management
- ✅ Creates `config.json` for AI model configuration
- ✅ Initializes templates and documentation folders

### Model Configuration

Configure AI models for task generation and updates:

```bash
# Interactive setup (recommended)
task-master models --setup

# Or set specific models
task-master models --set-main claude-sonnet-4-20250514
task-master models --set-research perplexity-sonar-pro
task-master models --set-fallback gpt-4o-mini
```

### API Key Setup

Task Master supports multiple AI providers. At minimum, configure one provider:

<details>
<summary><strong>📝 API Key Configuration Methods</strong></summary>

**Option 1: Using .env file (CLI usage)**

Create a `.env` file in your project root:

```bash
# Claude (Recommended)
ANTHROPIC_API_KEY=your_anthropic_key_here

# Research features (Highly recommended)
PERPLEXITY_API_KEY=your_perplexity_key_here

# Additional providers (optional)
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_google_key_here
XAI_API_KEY=your_xai_key_here
```

**Option 2: Using MCP configuration (Claude Code integration)**

See [MCP Server Configuration](#-mcp-server-configuration) section below.

</details>

### File Structure Created

```
.taskmaster/
├── tasks/
│   ├── tasks.json          # Main task database
│   └── task-*.md           # Individual task files (auto-generated)
├── docs/
│   ├── prd.txt             # Product requirements document
│   └── *-report.md         # Validation/analysis reports
├── reports/
│   └── task-complexity-report.json
├── templates/
│   └── example_prd.txt
├── config.json             # AI model configuration
├── CLAUDE.md              # Claude Code integration (auto-loaded)
└── AGENT.md               # Agent instructions
```

---

## 🔌 MCP Server Configuration

MCP (Model Context Protocol) enables Task Master AI to work directly within Claude Code.

### Setup .mcp.json

Create or update `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "task-master-ai": {
      "command": "npx",
      "args": ["-y", "task-master-ai"],
      "env": {
        "ANTHROPIC_API_KEY": "your_anthropic_key_here",
        "PERPLEXITY_API_KEY": "your_perplexity_key_here",
        "OPENAI_API_KEY": "your_openai_key_here",
        "GOOGLE_API_KEY": "your_google_key_here"
      }
    }
  }
}
```

⚠️ **Security Note**: Never commit API keys to version control. Use environment variables or secure secret management.

### Available MCP Tools

When connected via MCP, these tools become available in Claude Code:

| Tool | CLI Equivalent | Description |
|------|---------------|-------------|
| `initialize_project` | `task-master init` | Initialize Task Master in project |
| `parse_prd` | `task-master parse-prd` | Generate tasks from PRD document |
| `get_tasks` | `task-master list` | List all tasks |
| `next_task` | `task-master next` | Get next available task |
| `get_task` | `task-master show <id>` | View task details |
| `set_task_status` | `task-master set-status` | Update task status |
| `add_task` | `task-master add-task` | Create new task with AI |
| `expand_task` | `task-master expand` | Break task into subtasks |
| `update_task` | `task-master update-task` | Update task details |
| `update_subtask` | `task-master update-subtask` | Add notes to subtask |
| `analyze_project_complexity` | `task-master analyze-complexity` | Analyze task complexity |
| `models` | `task-master models` | Configure AI models |

### Verifying MCP Connection

In Claude Code, you can verify the connection:

```bash
# Claude Code will show available MCP servers when connected
# Look for "task-master-ai" in the MCP servers list
```

### Fallback to CLI

If MCP is unavailable, all functionality is accessible via CLI:

```bash
task-master next        # Get next task
task-master show 5      # View task 5
task-master list        # List all tasks
```

---

## 🐳 Docker Development Environment

### Prerequisites

| Requirement | Minimum Version | Download Link |
|------------|----------------|---------------|
| **Docker Desktop** | 20.10+ | [docker.com](https://www.docker.com/products/docker-desktop) |
| **Docker Compose** | 2.0+ | Included with Docker Desktop |
| **RAM** | 8GB | (16GB recommended) |
| **Disk Space** | 10GB | For images and volumes |

### Building the Environment

```bash
# Clean build (recommended for first-time setup)
docker compose build --no-cache

# Quick build (uses cache)
docker compose build
```

**Build includes:**
- Base image with Python 3.11 and Java 11
- All Python packages from requirements.txt
- PySpark, DuckDB, Superset, and cloud SDKs
- Development tools and utilities

### Starting the Environment

```bash
# Start in detached mode
docker compose up -d

# Start with logs visible
docker compose up

# Check container status
docker compose ps
```

### Accessing the Container

```bash
# Open bash shell in container
docker compose exec rdewai-dev bash

# Run commands directly
docker compose exec rdewai-dev python --version
docker compose exec rdewai-dev pyspark
```

### Volume Mounts

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `./` | `/workspace` | Project files (live sync) |
| `rdewai-data` | `/data` | Persistent data storage |
| `rdewai-cache` | `/root/.cache` | Package cache, pip cache |

💡 **Tip**: All changes in `/workspace` are immediately reflected on your host machine.

### Port Mappings

| Port | Service | Access URL |
|------|---------|-----------|
| 8088 | Apache Superset | http://localhost:8088 |
| 4040 | Spark UI | http://localhost:4040 (when Spark job runs) |
| 8080 | Additional Services | http://localhost:8080 |

### Health Checks

The container includes automated health checks:

```bash
# Check container health
docker inspect rdewai-dev | grep -A 10 "Health"

# Manual health verification
docker compose exec rdewai-dev python --version
```

### Resource Requirements

**Minimum:**
- RAM: 8GB
- CPU: 2 cores
- Disk: 10GB

**Recommended:**
- RAM: 16GB
- CPU: 4 cores
- Disk: 20GB

---

## 🔧 IDE Integration

### VS Code / Cursor DevContainer

#### Installation

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

#### Opening in Container

1. Open project folder in VS Code/Cursor
2. Press `F1` or `Cmd/Ctrl+Shift+P`
3. Select **"Dev Containers: Reopen in Container"**
4. Wait for container to build and start

#### Auto-Installed Extensions

The DevContainer automatically installs:
- **Python** (`ms-python.python`)
- **Pylance** (`ms-python.vscode-pylance`)
- **Jupyter** (`ms-toolsai.jupyter`)
- **Docker** (`ms-azuretools.vscode-docker`)

#### Settings Applied

```json
{
  "python.defaultInterpreterPath": "/usr/local/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black"
}
```

### Claude Code Integration

#### Auto-Loading CLAUDE.md

Claude Code automatically loads `.taskmaster/CLAUDE.md` when you start:

```bash
claude
```

This provides Claude with:
- Task Master command reference
- Project-specific context
- Development workflow guidelines
- Custom instructions

#### Using Task Master Commands

Within Claude Code, use Task Master naturally:

```
> Show me the next task

Claude Code will use: task-master next
```

Or call MCP tools directly via the integrated tools.

#### Custom Slash Commands

Create custom commands in `.claude/commands/`:

<details>
<summary><strong>Example: taskmaster-next.md</strong></summary>

```markdown
Find the next available Task Master task and show its details.

Steps:
1. Run `task-master next` to get the next task
2. If a task is available, run `task-master show <id>` for full details
3. Provide a summary of what needs to be implemented
4. Suggest the first implementation step
```

Usage: `/taskmaster-next`

</details>

#### Tool Allowlist Configuration

Configure allowed tools in `.claude/settings.json`:

```json
{
  "allowedTools": [
    "Edit",
    "Bash(task-master *)",
    "Bash(git *)",
    "Bash(docker *)",
    "mcp__task-master-ai__*"
  ]
}
```

---

## 📂 Project Structure

```
Redefining-DataEngineering-With-AI/
├── .taskmaster/                    # Task Master AI directory
│   ├── tasks/
│   │   ├── tasks.json             # Main task database (auto-managed)
│   │   ├── task-1.md              # Individual task files
│   │   └── task-2.md
│   ├── docs/
│   │   ├── prd.txt                # Product requirements document
│   │   └── docker-validation-report.md
│   ├── reports/
│   │   └── task-complexity-report.json
│   ├── templates/
│   │   └── example_prd.txt
│   ├── config.json                # AI model configuration
│   ├── CLAUDE.md                  # Claude Code auto-loaded context
│   └── AGENT.md                   # Agent instructions
│
├── .claude/                       # Claude Code configuration
│   ├── commands/                  # Custom slash commands
│   └── settings.json              # Tool permissions & preferences
│
├── .devcontainer/                 # VS Code DevContainer config
│   └── devcontainer.json          # Container specification
│
├── scripts/                       # Utility scripts
│   ├── test-environment.sh        # Basic environment test
│   ├── comprehensive-validation.sh # Full validation suite
│   ├── start-dev.sh               # Start development services
│   ├── stop-dev.sh                # Stop services
│   └── run-tests.sh               # Run pytest suite
│
├── docker-compose.yml             # Container orchestration
├── Dockerfile                     # Multi-stage image definition
├── requirements.txt               # Python dependencies
├── .env.example                   # API key template
├── .gitignore                     # Git ignore rules
├── .mcp.json                      # MCP server configuration
├── CLAUDE.md                      # Claude Code instructions
├── DOCKER.md                      # Docker setup guide
└── README.md                      # This file
```

---

## 🔄 Development Workflow

### Initial Setup Flow

When starting a new project or feature:

```bash
# 1. Create or obtain a PRD (Product Requirements Document)
# Place it in .taskmaster/docs/prd.txt

# 2. Parse the PRD to generate tasks
task-master parse-prd .taskmaster/docs/prd.txt

# 3. Analyze task complexity
task-master analyze-complexity --research

# 4. View the complexity report
task-master complexity-report

# 5. Expand all tasks into subtasks
task-master expand --all --research
```

### Daily Development Loop

```bash
# 1. Get next available task
task-master next

# 2. Review task details
task-master show <id>

# 3. Mark task as in-progress
task-master set-status --id=<id> --status=in-progress

# 4. Implement the task
# ...work on the task...

# 5. Log implementation notes (optional but recommended)
task-master update-subtask --id=<id> --prompt="Implemented X, encountered Y, resolved with Z"

# 6. Run validation/tests
./scripts/test-environment.sh
pytest

# 7. Mark task as complete
task-master set-status --id=<id> --status=done
```

### Git Integration

**Commit Message Format:**

```bash
git commit -m "feat: implement user authentication (task 1.2)

- Added JWT token generation
- Implemented login endpoint
- Added user session management

Task-Master-ID: 1.2"
```

**Creating Pull Requests:**

```bash
gh pr create --title "Complete task 1.2: User authentication" \
  --body "Implements JWT auth system as specified in task 1.2"
```

### Validation Scripts

```bash
# Basic environment validation
./scripts/test-environment.sh

# Comprehensive validation (runs 19 tests)
./scripts/comprehensive-validation.sh

# Run Python tests
docker compose exec rdewai-dev pytest

# Run specific test file
docker compose exec rdewai-dev pytest tests/test_auth.py
```

---

## 📖 Common Commands

### Task Master Commands

| Command | Description | Example |
|---------|-------------|---------|
| `task-master init` | Initialize project | `task-master init --rules claude` |
| `task-master list` | Show all tasks | `task-master list --status=pending` |
| `task-master next` | Get next available task | `task-master next` |
| `task-master show <id>` | View task details | `task-master show 5` |
| `task-master set-status` | Update task status | `task-master set-status --id=5 --status=done` |
| `task-master add-task` | Create new task | `task-master add-task --prompt="Add login feature"` |
| `task-master expand` | Break into subtasks | `task-master expand --id=5 --research` |
| `task-master update-task` | Update task details | `task-master update-task --id=5 --prompt="Add OAuth"` |
| `task-master update-subtask` | Add subtask notes | `task-master update-subtask --id=5.2 --prompt="notes"` |
| `task-master models` | Configure AI models | `task-master models --setup` |

### Docker Commands

| Command | Description | Example |
|---------|-------------|---------|
| `docker compose up -d` | Start environment | `docker compose up -d` |
| `docker compose down` | Stop environment | `docker compose down` |
| `docker compose ps` | Show container status | `docker compose ps` |
| `docker compose logs` | View logs | `docker compose logs rdewai-dev` |
| `docker compose exec` | Run command in container | `docker compose exec rdewai-dev bash` |
| `docker compose build` | Rebuild images | `docker compose build --no-cache` |
| `docker stats` | View resource usage | `docker stats rdewai-dev` |

### Development Commands

| Command | Description | Example |
|---------|-------------|---------|
| `pyspark` | Start PySpark shell | `docker compose exec rdewai-dev pyspark` |
| `pytest` | Run tests | `docker compose exec rdewai-dev pytest` |
| `python -m pytest` | Run pytest with options | `docker compose exec rdewai-dev python -m pytest -v` |
| `superset db upgrade` | Initialize Superset DB | `docker compose exec rdewai-dev superset db upgrade` |
| `superset run` | Start Superset server | `docker compose exec rdewai-dev superset run -h 0.0.0.0` |

---

## 🔧 Troubleshooting

### Task Master Issues

<details>
<summary><strong>❌ Error: "API key not found"</strong></summary>

**Solution:**

1. Check your `.env` file or `.mcp.json` configuration
2. Verify API key is correctly formatted
3. Ensure environment variables are loaded:

```bash
# Check if .env is sourced
source .env

# Verify key is set
echo $ANTHROPIC_API_KEY
```

</details>

<details>
<summary><strong>❌ Error: "Model not configured"</strong></summary>

**Solution:**

```bash
# Configure models interactively
task-master models --setup

# Or set manually
task-master models --set-main claude-sonnet-4-20250514
```

</details>

<details>
<summary><strong>❌ MCP Connection Failed in Claude Code</strong></summary>

**Solution:**

1. Check `.mcp.json` syntax is valid JSON
2. Verify Task Master is installed: `npm list -g task-master-ai`
3. Test CLI directly: `task-master next`
4. Restart Claude Code
5. Use CLI as fallback if MCP issues persist

</details>

### Docker Issues

<details>
<summary><strong>❌ Error: "Port already in use"</strong></summary>

**Solution:**

```bash
# Find process using the port (e.g., 8088)
lsof -i :8088

# Kill the process or change port in docker-compose.yml
docker compose down
# Edit docker-compose.yml ports section
docker compose up -d
```

</details>

<details>
<summary><strong>❌ Container won't start / Memory error</strong></summary>

**Solution:**

```bash
# Increase Docker Desktop memory allocation
# Docker Desktop → Settings → Resources → Memory → 8GB+

# Clean up Docker system
docker system prune -a --volumes

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

</details>

<details>
<summary><strong>❌ Build cache issues</strong></summary>

**Solution:**

```bash
# Force clean rebuild
docker compose down
docker compose build --no-cache --pull
docker compose up -d
```

</details>

### Integration Issues

<details>
<summary><strong>❌ Claude Code not loading CLAUDE.md</strong></summary>

**Solution:**

1. Verify file exists: `ls -la .taskmaster/CLAUDE.md`
2. Check file isn't empty: `cat .taskmaster/CLAUDE.md | wc -l`
3. Restart Claude Code
4. Manually reference context if needed

</details>

<details>
<summary><strong>❌ DevContainer won't connect</strong></summary>

**Solution:**

1. Install "Dev Containers" extension in VS Code
2. Check Docker Desktop is running
3. Rebuild DevContainer: `Cmd/Ctrl+Shift+P` → "Dev Containers: Rebuild Container"
4. Check `.devcontainer/devcontainer.json` is valid JSON

</details>

<details>
<summary><strong>❌ Permission errors in container</strong></summary>

**Solution:**

```bash
# Most operations run as root in container
docker compose exec rdewai-dev bash

# If you need specific permissions
docker compose exec -u root rdewai-dev bash
```

</details>

---

## 🎓 Advanced Topics

### Parallel Development with Git Worktrees

Work on multiple tasks simultaneously:

```bash
# Create worktrees for parallel development
git worktree add ../rdewai-auth feature/auth-system
git worktree add ../rdewai-api feature/api-refactor

# Run separate Claude Code sessions
cd ../rdewai-auth && claude    # Terminal 1
cd ../rdewai-api && claude     # Terminal 2
```

### Multi-Claude Session Workflows

For complex projects, use multiple Claude instances:

```bash
# Terminal 1: Main development
cd project && claude

# Terminal 2: Testing and validation
cd project && claude

# Terminal 3: Documentation
cd project && claude
```

### Custom Model Configuration

Configure different models for different roles:

```bash
# Set high-performance model for main tasks
task-master models --set-main claude-opus-4-20250514

# Set fast model for research
task-master models --set-research perplexity-sonar-pro

# Set economical fallback
task-master models --set-fallback gpt-4o-mini
```

### Creating Custom Slash Commands

Create `.claude/commands/review.md`:

```markdown
Review the current task implementation: $ARGUMENTS

Steps:
1. Read the task details: `task-master show $ARGUMENTS`
2. Review the implementation code
3. Run tests: `pytest`
4. Provide code review feedback
5. Suggest improvements
```

Usage: `/review 5`

### Automated Task Workflows

Create shell scripts for common workflows:

```bash
#!/bin/bash
# File: scripts/auto-task.sh

# Get next task
TASK_ID=$(task-master next | grep "ID:" | awk '{print $2}')

# Mark in progress
task-master set-status --id=$TASK_ID --status=in-progress

# Show details
task-master show $TASK_ID

# After implementation, mark done
# task-master set-status --id=$TASK_ID --status=done
```

---

## 📚 Appendix

### Full Task Master Command Reference

<details>
<summary><strong>View All Commands</strong></summary>

```bash
# Project Management
task-master init                    # Initialize project
task-master parse-prd <file>        # Parse PRD into tasks

# Task Operations
task-master list                    # List all tasks
task-master next                    # Get next available task
task-master show <id>               # View task details
task-master add-task                # Create new task
task-master set-status              # Update task status
task-master remove-task <id>        # Delete task

# Task Breakdown
task-master expand --id=<id>        # Expand task to subtasks
task-master expand --all            # Expand all tasks
task-master add-subtask             # Add subtask manually
task-master remove-subtask          # Remove subtask

# Task Updates
task-master update-task             # Update specific task
task-master update-subtask          # Update subtask with notes
task-master update --from=<id>      # Update multiple tasks

# Analysis
task-master analyze-complexity      # Analyze all tasks
task-master complexity-report       # View analysis report

# Dependencies
task-master add-dependency          # Add dependency
task-master remove-dependency       # Remove dependency
task-master validate-dependencies   # Check dependency issues
task-master fix-dependencies        # Auto-fix dependencies

# Configuration
task-master models                  # View/configure AI models
task-master generate                # Regenerate task files

# Utility
task-master move                    # Move/reorder tasks
task-master clear-subtasks          # Clear task subtasks
```

</details>

### Environment Variable Reference

| Variable | Purpose | Required | Example |
|----------|---------|----------|---------|
| `ANTHROPIC_API_KEY` | Claude models | ⭐ Recommended | `sk-ant-...` |
| `PERPLEXITY_API_KEY` | Research features | ⭐ Recommended | `pplx-...` |
| `OPENAI_API_KEY` | GPT models | Optional | `sk-...` |
| `GOOGLE_API_KEY` | Gemini models | Optional | `AIza...` |
| `XAI_API_KEY` | Grok models | Optional | `xai-...` |
| `OPENROUTER_API_KEY` | Multiple models | Optional | `sk-or-...` |
| `PYTHONUNBUFFERED` | Python output | Auto-set | `1` |
| `JAVA_HOME` | Java runtime | Auto-set | `/usr/lib/jvm/...` |
| `SPARK_HOME` | PySpark location | Auto-set | `/usr/local/lib/...` |

### Port Usage Reference

| Port | Service | Status | Access |
|------|---------|--------|--------|
| 8088 | Apache Superset | Mapped | http://localhost:8088 |
| 4040 | Spark UI | Mapped | http://localhost:4040 (when job runs) |
| 8080 | Additional Services | Mapped | http://localhost:8080 |

### API Provider Comparison

| Provider | Models | SWE Score | Cost | Best For |
|----------|--------|-----------|------|----------|
| **Anthropic** | Claude Sonnet 4, Opus 4 | 72.7% | $3-$75/M tokens | Main development |
| **Perplexity** | Sonar Pro, Deep Research | N/A | $1-$8/M tokens | Research tasks |
| **OpenAI** | GPT-4o, o1, o3-mini | 33-49% | $0.15-$60/M tokens | Fallback |
| **Google** | Gemini 2.5 Pro | 63.8% | Free tier available | Alternative main |
| **Claude Code** | Integrated | 72.7% | Free | Best integration |

💡 **Recommendation**: Use Claude Code (free) for main and fallback, Perplexity for research.

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Task Master AI](https://www.npmjs.com/package/task-master-ai) for intelligent task management
- [Claude Code](https://claude.com/claude-code) for AI-powered development
- Apache Spark, DuckDB, and Superset communities

---

**Need Help?**
- 📖 [Task Master Documentation](https://www.npmjs.com/package/task-master-ai)
- 💬 [Claude Code Docs](https://docs.claude.com/en/docs/claude-code)
- 🐛 [Report Issues](../../issues)

---

<div align="center">

**Built with ❤️ using AI-Enhanced Development Tools**

[⬆ Back to Top](#redefining-data-engineering-with-ai)

</div>
