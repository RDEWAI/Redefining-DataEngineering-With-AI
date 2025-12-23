# Redefining Data Engineering with AI

> **Modern Local-First Data Engineering Development Environment**
> Fast, reproducible local development with UV package manager, DuckDB, SQLMesh, and Apache Superset.

[![UV](https://img.shields.io/badge/UV-Package_Manager-blue)](https://docs.astral.sh/uv/)
[![Python](https://img.shields.io/badge/Python-3.10_|_3.11_|_3.12-green)](https://www.python.org/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1.3-orange)](https://duckdb.org/)
[![Superset](https://img.shields.io/badge/Superset-4.1.1-purple)](https://superset.apache.org/)

---

## 🚀 Quick Start

```bash
# 1. Clone and navigate to the repository
git clone <your-repo-url>
cd Redefining-DataEngineering-With-AI

# 2. Set up development environment (< 5 minutes)
make dev-setup

# 3. (Optional) Extract raw Synthea data (< 2 minutes)
make raw-data-copy

# 4. Activate virtual environment
source .venv/bin/activate
```

✅ **You're ready to start developing!**

### Prerequisites

- **UV Package Manager** - [Install](https://docs.astral.sh/uv/)
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
├── scripts/
│   ├── validate-environment.sh    # Prerequisite validation
│   └── add_duckdb_connection.py   # Auto-configure DuckDB in Superset
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

**Image pull fails:**
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
