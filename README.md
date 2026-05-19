# Redefining Data Engineering with AI

> **Modern Local-First Data Engineering Development Environment**
> Fast, reproducible local development with UV package manager, DuckDB, SQLMesh, and Apache Superset.

[![Python](https://img.shields.io/badge/Python-3.10_|_3.11_|_3.12-green)](https://www.python.org/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1.3-orange)](https://duckdb.org/)
[![Superset](https://img.shields.io/badge/Superset-4.1.1-purple)](https://superset.apache.org/)

---

## 🚀 Quick Start

```bash
# 1. Clone and navigate to the repository
git clone <your-repo-url>
cd Redefining-DataEngineering-With-AI
```


### Prerequisites

- **Python 3.10, 3.11, or 3.12** - [Download](https://www.python.org/downloads/)
- **Docker** (only for data extraction) - [Download](https://www.docker.com/)

### LLM API Keys

For AI features, choose a provider and obtain an API key:

| Provider | Get API Key |
|----------|-------------|
| **OpenRouter** (Recommended) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Ollama** (Local) | No key needed - [ollama.ai](https://ollama.ai) |

Keep this API key noted or saved, you will know how to add this into configuration.

---

✅ **You're ready to start developing!**


## 💡 What This Project Provides

A modern local-first data engineering development environment with:

- **UV Package Manager** for fast, reliable Python dependency management
- **DuckDB 1.1.3** for embedded analytics and fast CSV processing
- **SQLMesh** for SQL-based data transformations
- **Apache Superset 4.1.1** for business intelligence and data visualization
- **Makefile workflow** for standardized development commands
- **Reproducible builds** with uv.lock for consistent environments

---

## 🛠️ Development Workflow

### Available Make Targets

```bash
make help           # Show all available commands
make dev-setup      # Set up development environment (< 5 min)
make raw-data-copy  # Extract Synthea CSV data from Docker (< 2 min)
make load-raw-data  # Load CSV files into DuckDB tables (< 10 min)
make superset-init  # Initialize Superset database and admin user
make superset-run   # Start Superset web server on localhost:8088
make test           # Run all tests with pytest
make clean          # Remove generated files and virtual environment
```

### Initial Setup

```bash
# 1. Set up development environment
make dev-setup

# This will:
# - Check for UV and Python prerequisites
# - Create a virtual environment (.venv)
# - Install all dependencies (DuckDB, SQLMesh, Superset, pytest)
# - Validate the installation
```

### Update SpecKit (if needed):

SpecKit is used for feature specification and task management. To update to the latest version:

```bash
# Back up your constitution first (known issue - it gets overwritten)
cp .specify/memory/constitution.md .specify/memory/constitution.md.bak

# Run init with --force to update templates
uvx --from git+https://github.com/github/spec-kit.git specify init --ai claude --here --force

# Restore your constitution
cp .specify/memory/constitution.md.bak .specify/memory/constitution.md
```

### Working with Data

```bash
# Extract raw Synthea healthcare data
make raw-data-copy

# This will:
# - Pull Docker image with Synthea data
# - Copy CSV files to data/raw/
# - Clean up temporary containers
#
# Result: 18 CSV files (~4.3GB) in data/raw/

# Load CSV data into DuckDB
make load-raw-data

# This will:
# - Load all 18 CSV files into DuckDB tables
# - Create tables in the 'synthea' schema
# - Display progress and row counts
#
# Result: DuckDB database at data/duckdb/raw.db with 18 tables
```

### Using Apache Superset

```bash
# Initialize Superset (first time only)
make superset-init

# This will:
# - Create Superset database and tables
# - Set up roles and permissions
# - Create admin user (username: admin, password: admin)
# - Configure DuckDB as a pre-connected data source

# Start Superset web server
make superset-run

# This will:
# - Auto-detect available port (8088-8100)
# - Start Superset with hot-reload enabled
# - Display URL and login credentials

# Access Superset at the displayed URL (usually http://localhost:8088)
# Login: admin / admin
```

**Pre-configured Data Sources:**
- **DuckDB Analytics** - Ready to use at `data/duckdb/raw.db` (synthea schema)
  - Use SQL Lab to query data
  - Create datasets and charts
  - Build dashboards

### Running Tests

```bash
# Run all tests
make test

# Or activate venv and run pytest directly
source .venv/bin/activate
pytest tests/ -v
```

---

## 🔧 IDE Integration

### VS Code / Cursor DevContainer

The project includes DevContainer configuration, but uses the pre-built Docker image:

1. Install [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open project folder
3. `F1` → **"Dev Containers: Reopen in Container"**
4. Container will pull the pre-built image

Auto-installed extensions:
- Python + Pylance
- Jupyter
- Docker

### Claude Code

```bash
# Start Claude Code (auto-loads CLAUDE.md)
claude
```

---

## 📂 Project Structure

```
Redefining-DataEngineering-With-AI/
├── Makefile                       # Development workflow automation
├── pyproject.toml                 # UV project configuration
├── uv.lock                        # Dependency lock file (committed)
├── superset_config.py             # Superset configuration (committed)
├── .venv/                         # Virtual environment (gitignored)
│
├── data/
│   ├── raw/                       # Synthea CSV data (gitignored)
│   └── duckdb/                    # DuckDB databases (gitignored)
│       └── raw.db                 # Synthea data (synthea schema)
│
├── chapter-2/                     # AI Engineering (RAG, MCP, Agentic AI)
├── chapter-3/                     # Business Analyst Agent (DRD Plugin)
├── chapter-4/                     # Multi-Agent Artifact Chain (7 plugins)
│
├── templates/
│   └── cookiecutter-chapter/      # Cookiecutter scaffold for chapter-5+
│
├── scripts/
│   ├── validate-environment.sh    # Prerequisite validation
│   ├── add_duckdb_connection.py   # Auto-configure DuckDB in Superset
│   └── clean-outputs.sh           # Reset chapter-3/4 outputs & memory for fresh runs
│
├── tests/
│   ├── integration/               # Integration tests
│   └── unit/                      # Unit tests
│
├── .superset/                     # Superset metadata (gitignored)
├── docker-compose.yml             # Docker for data extraction only
├── Dockerfile                     # Docker for data extraction only
└── README.md                      # This file
```

---

## 📖 Chapters

### Chapter 2: AI Engineering with Library Management Data

Demonstrates modern AI engineering patterns — **RAG**, **MCP**, and **Agentic AI** — using a Library Management dataset with 200 books in DuckDB.

- RAG: Retrieval-Augmented Generation with vector embeddings and semantic search
- MCP: Model Context Protocol server with code execution for token efficiency
- Agentic AI: Multi-agent orchestration with specialist agents

See [chapter-2/README.md](chapter-2/README.md) for full details.

### Chapter 3: Business Analyst Agent

A single Claude Code plugin that acts as a **Business Analyst Agent**, generating, updating, and validating **Data Requirements Documents (DRDs)** from business inputs for the Patient 360 use case.

- 1 plugin, 3 skills (create-drd, update-drd, validate-drd)
- Interactive Q&A elicitation workflow
- Automatic validation via PostToolUse hooks

See [chapter-3/README.md](chapter-3/README.md) for full details.

### Chapter 4: Multi-Agent Artifact Chain — Reference Implementation

Six Claude Code plugins forming a **multi-agent artifact chain** where each role produces a structured artifact that feeds the next:

```
DRD → HLD → DMS → STM → DQS → LLD
```

| Plugin | Role | Artifact | Format |
|--------|------|----------|--------|
| ba-plugin | Business Analyst | DRD (Data Requirements Document) | Markdown |
| architect-plugin | Data Architect | HLD (High-Level Design) | Markdown |
| data-modeler-plugin | Data Modeler | DMS (Data Model Specification) | Markdown + YAML |
| mapping-analyst-plugin | Mapping Analyst | STM (Source-to-Target Mapping) | Excel (.xlsx) |
| dq-engineer-plugin | DQ Engineer | DQS (Data Quality Specification) | Markdown + SE YAML |
| technical-lead-plugin | Technical Lead | LLD (Low-Level Design) | Markdown + Config + DAG |

Chapter-4 is the **canonical reference implementation** for the six planning
plugins. Sprint-backlog generation and code implementation continue in
Chapter 5.

See [chapter-4/README.md](chapter-4/README.md) for full details.

**Want to try it yourself?** After cloning, reset the reference outputs and run the agents to generate your own artifacts:

```bash
# 1. Clean existing outputs (keeps DRD as starting input)
./scripts/clean-outputs.sh

# 2. Follow the step-by-step walkthrough
```

See the [Hands-On Guide](chapter-4/HANDS-ON-GUIDE.md) for the full walkthrough — from plugin installation through generating all 6 artifacts.

### Chapter 5: Full-Chain Workspace — Planning + Story-Driven Implementation

Chapter 5 is a **workspace** that runs the entire pipeline end-to-end — from
business request through generated code. It ships two implementation-phase
plugins (Scrum Master, Developer) and reuses the six Chapter-4 planning
plugins as a single source of truth, eight in total:

```
DRD → HLD → DMS → STM → DQS → LLD → Stories → Code
```

| Plugin | Role | Output |
|--------|------|--------|
| ba-plugin, architect-plugin, data-modeler-plugin, mapping-analyst-plugin, dq-engineer-plugin, technical-lead-plugin | Planning chain | DRD → LLD (sourced from chapter-4 — `rdewai-plugins` marketplace) |
| scrum-master-plugin | Scrum Master | Sprint Backlog (Epics & Stories, multi-file markdown) |
| developer-plugin | Developer | Airflow DAGs, CI/CD pipelines, Bronze ingestion framework |

The chapter-5 plugins (`scrum-master`, `developer`) are registered under the
`rdewai-chapter5-plugins` marketplace; the planning plugins come from the
`rdewai-plugins` marketplace in chapter-4. From `chapter-5/`, run
`make install-plugins` to install all eight at once.

See [chapter-5/CLAUDE.md](chapter-5/CLAUDE.md) for full details.

A **cookiecutter template** is also provided (`templates/cookiecutter-chapter/`) so readers can scaffold their own equivalent chapter project.

#### Prerequisites

The project uses `uv` — no separate install needed. Run via `uvx`:

```bash
# Verify uv is available
uv --version
```

#### Generate Your Chapter 5 Directory

```bash
uvx cookiecutter templates/cookiecutter-chapter/ --overwrite-if-exists
```

The `--overwrite-if-exists` flag makes the command safe to re-run — it regenerates into an existing directory without errors.

You will be prompted for four values (press Enter to accept defaults):

```
chapter_name [chapter-5]:      # top-level folder name
project_name [patient_360]:    # Python package / project name
python_version [3.12]:         # Python version for pyproject.toml
author_name [Data Engineer]:   # your name
```

This generates the following structure:

```
chapter-5/
├── inputs/                      # drop Chapter 4 approved artifacts here
├── outputs/                     # chapter-5 generated outputs
├── developer-plugin/            # AI developer agent (code + story orchestration)
│   └── skills/
│       ├── create-dag/ update-dag/ validate-dag/                 # Airflow DAGs
│       ├── create-ingestion/ update-ingestion/ validate-ingestion/  # Bronze ingestion
│       ├── create-pipeline/ update-pipeline/ validate-pipeline/  # CI/CD pipeline
│       ├── implement-stories/   # dispatch create-/update- per story or epic
│       ├── validate-stories/    # verify story ACs (read-only)
│       ├── complete-stories/    # atomic gate — close stories/epics when all ACs pass
│       └── apply-learnings/     # apply corrections from learnings queue
└── patient_360/                 # main Python project
    ├── src/patient_360/         # bronze / silver / gold / utils packages
    ├── tests/                   # mirrors src/ — bronze / silver / gold
    ├── airflow/dags/            # Airflow DAG files
    ├── airflow/configs/         # DAG configuration YAML
    ├── contracts/               # table contracts (DDL + DQ pointers)
    ├── dq_rules/                # DQ rule definitions (Spark Expectations)
    ├── ddl/liquibase/           # schema migration changelogs
    ├── _infra/docker|ci|cd/     # infrastructure configuration
    ├── Makefile
    └── pyproject.toml
```

#### After Generation

```bash
cd chapter-5/patient_360

# Install dependencies
make dev-setup

# Run tests (empty suite passes out of the box)
make test

# Install all Claude plugins (chapter-4 planning + chapter-5 implementation)
make install-plugins

# Start generating DAGs from your approved LLD
/developer-plugin:create-dag

# Or drive it from the Scrum backlog (story/epic/sprint)
/developer-plugin:implement-stories EPIC-02
/developer-plugin:validate-stories  EPIC-02
/developer-plugin:complete-stories  EPIC-02   # blocks unless every child story + AC passes
```

---

## 🔄 Daily Development Workflow

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Work with data
python your_analysis.py

# 3. Run DuckDB queries
python -c "import duckdb; conn = duckdb.connect('data.db'); ..."

# 4. Test your changes
pytest tests/ -v

# 5. Start Superset for visualization (if needed)
make superset-run
```

---

## 📖 Common Commands

### Makefile Commands (Primary Workflow)

```bash
make dev-setup      # Set up development environment
make raw-data-copy  # Extract Synthea data
make load-raw-data  # Load CSV data into DuckDB
make superset-init  # Initialize Superset
make superset-run   # Start Superset server
make test           # Run all tests
make clean          # Clean up generated files
make help           # Show all available commands
```

### UV Package Manager Commands

```bash
uv sync             # Install/update dependencies
uv add <package>    # Add new dependency
uv run <command>    # Run command in virtual environment
uv lock             # Update lock file
```

### Python Development

```bash
source .venv/bin/activate  # Activate virtual environment
python your_script.py      # Run Python scripts
pytest tests/ -v           # Run tests with verbose output
```

### Docker (Data Extraction Only)

**Note**: Docker is only used for extracting raw Synthea data. Development happens locally.

```bash
make raw-data-copy         # Preferred: Use Makefile target

# Manual Docker commands (if needed):
docker pull ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data
docker run --rm -v $(pwd)/data/raw:/data <image> <copy-command>
```

---

## 🔧 Troubleshooting

### UV / Python Issues

**UV not found:**
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your shell
exec $SHELL
```

**Wrong Python version:**
```bash
# Check current Python version
python3 --version

# Install Python 3.12 with UV
uv python install 3.12

# Or download from python.org
```

**Dependency conflicts:**
```bash
# Clean and rebuild
make clean
make dev-setup
```

### Superset Issues

**Port 8088 already in use:**
```bash
# The Makefile automatically detects available ports (8088-8100)
# Just run make superset-run and it will use the next available port

make superset-run
```

**Superset won't start:**
```bash
# Make sure you've initialized first
make superset-init

# Then start the server
make superset-run
```

**Can't find DuckDB database:**
```bash
# The DuckDB Analytics connection is auto-configured during init
# If it's missing, re-run initialization:
make clean
make dev-setup
make superset-init
```

**pkg_resources error:**
```bash
# Reinstall dependencies (setuptools should be included)
make clean
make dev-setup
```

### Docker Issues (Data Extraction)

**Docker daemon not running:**
```bash
# macOS/Windows: Open Docker Desktop
# Linux: sudo systemctl start docker
```

**Image pull fails with authentication/permission error:**

The Docker image is private. Even if you have access on GitHub, Docker needs to be authenticated separately with GHCR (GitHub Container Registry).

```bash
# Option 1: Using GitHub CLI (recommended)
echo $(gh auth token) | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Option 2: Using a Personal Access Token (PAT)
# Create a PAT at https://github.com/settings/tokens with `read:packages` scope
echo YOUR_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

After authenticating, retry `make raw-data-copy`.

**Image pull fails (network/other errors):**
```bash
# Pull manually
docker pull ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data
```

---

## 🎯 What's Installed

### Core Dependencies

- **DuckDB 1.1.3** - Fast analytical database
- **duckdb-engine** - SQLAlchemy driver for DuckDB
- **SQLMesh** - SQL-based data transformations
- **Apache Superset 4.1.1** - Business intelligence platform
- **marshmallow <4** - Data serialization (pinned for Superset compatibility)
- **pytest 8.3.4** - Testing framework
- **setuptools** - Python packaging tools
- **openpyxl 3.1+** - Excel file generation for Source-to-Target Mappings (Chapter 4)
- **jinja2** - Template rendering for artifact generation (Chapter 4)
- **pyyaml** - YAML parsing for schema blocks and SE rules (Chapter 4)

### Python Version Support

- **Python 3.10** ✅
- **Python 3.11** ✅
- **Python 3.12** ✅

### Development Tools

- **UV Package Manager** - Fast Python package installer
- **Make** - Build automation
- **Git** - Version control

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## 📄 License

This project is licensed under the MIT License.

---

## 📚 Additional Resources

- [UV Documentation](https://docs.astral.sh/uv/) - UV package manager guide
- [DuckDB Documentation](https://duckdb.org/docs/) - DuckDB SQL reference
- [SQLMesh Documentation](https://sqlmesh.readthedocs.io/) - SQLMesh transformation guide
- [Apache Superset Documentation](https://superset.apache.org/docs/intro) - Superset BI platform
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code) - Claude AI assistant

## 📋 Documentation

- [Makefile API Contract](specs/001-uv-makefile-migration/contracts/makefile-api.md) - Detailed Makefile target documentation
- [DOCKER.md](DOCKER.md) - Docker setup for data extraction
- [Quickstart Guide](specs/001-uv-makefile-migration/quickstart.md) - Step-by-step setup guide

---

<div align="center">

**Built with ❤️ using UV + Modern Data Stack + AI Tools**

[⬆ Back to Top](#redefining-data-engineering-with-ai)

</div>
