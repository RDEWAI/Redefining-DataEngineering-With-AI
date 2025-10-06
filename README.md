# Redefining Data Engineering with AI

> **Docker-based Data Engineering Development Environment**
> Production-ready containerized environment with Python 3.11, PySpark, DuckDB, Apache Superset, and AI-powered task management.

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://www.python.org/)
[![PySpark](https://img.shields.io/badge/PySpark-3.5.4-orange)](https://spark.apache.org/)

---

## 🚀 Quick Start

```bash
# 1. Clone and navigate to the repository
git clone <your-repo-url>
cd Redefining-DataEngineering-With-AI

# 2. Install Task Master AI (optional, for task management)
npm install -g task-master-ai
task-master init --rules claude

# 3. Start Docker environment
docker compose up -d

# 4. Verify installation
./scripts/test-environment.sh

# 5. Access the container
docker compose exec rdewai-dev bash
```

✅ **You're ready to start developing!**

---

## 💡 What This Project Provides

A containerized data engineering development environment with:

- **Python 3.11** + **Java 11** runtime
- **PySpark 3.5.4** for distributed data processing
- **DuckDB** for embedded analytics
- **Apache Superset 4.1.1** for data visualization
- **Google Cloud SDKs** (BigQuery, Cloud Storage)
- **Task Master AI** integration for intelligent task management ([learn more](https://www.npmjs.com/package/task-master-ai))
- **DevContainer** support for VS Code/Cursor

---

## 🤖 Task Master AI Setup (Optional)

Task Master AI helps manage project tasks with AI-powered assistance. While optional, it's integrated throughout this project.

### Installation

```bash
# Install globally
npm install -g task-master-ai

# Initialize in project
task-master init --rules claude

# Configure AI models (requires API key)
task-master models --setup
```

### Basic Usage

```bash
task-master list              # Show all tasks
task-master next              # Get next available task
task-master show <id>         # View task details
task-master set-status --id=<id> --status=done
```

📖 **Full Documentation**: [Task Master AI](https://www.npmjs.com/package/task-master-ai)

---

## 🐳 Docker Development Environment

### Prerequisites

- **Docker Desktop** 20.10+ ([download](https://www.docker.com/products/docker-desktop))
- **RAM**: 8GB minimum, 16GB recommended
- **Disk Space**: 10GB for images and volumes

### Building the Environment

```bash
# First-time setup (clean build)
docker compose build --no-cache

# Subsequent builds (uses cache)
docker compose build
```

### Starting Services

```bash
# Start in background
docker compose up -d

# View logs
docker compose logs -f rdewai-dev

# Check status
docker compose ps
```

### Container Access

```bash
# Interactive shell
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
| `rdewai-cache` | `/root/.cache` | Package cache |

### Exposed Ports

| Port | Service | Access |
|------|---------|--------|
| 8088 | Apache Superset | http://localhost:8088 |
| 4040 | Spark UI | http://localhost:4040 |
| 8080 | Additional Services | http://localhost:8080 |

### Validation

```bash
# Basic environment test
./scripts/test-environment.sh

# Comprehensive validation (19 tests)
./scripts/comprehensive-validation.sh
```

---

## 🔧 IDE Integration

### VS Code / Cursor DevContainer

1. Install [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open project folder
3. `F1` → **"Dev Containers: Reopen in Container"**
4. Wait for container to build

Auto-installed extensions:
- Python + Pylance
- Jupyter
- Docker

### Claude Code

```bash
# Start Claude Code (auto-loads .taskmaster/CLAUDE.md)
claude

# Claude Code will have access to Task Master commands
# and project context automatically
```

---

## 📂 Project Structure

```
Redefining-DataEngineering-With-AI/
├── .taskmaster/                   # Task Master AI files
│   ├── tasks/tasks.json           # Task database
│   ├── docs/prd.txt               # Requirements document
│   ├── CLAUDE.md                  # Claude Code auto-loaded context
│   └── config.json                # AI model configuration
│
├── .devcontainer/                 # VS Code DevContainer config
│   └── devcontainer.json
│
├── scripts/                       # Utility scripts
│   ├── test-environment.sh        # Quick environment test
│   └── comprehensive-validation.sh # Full validation suite
│
├── docker-compose.yml             # Container orchestration
├── Dockerfile                     # Multi-stage image build
├── requirements.txt               # Python dependencies
├── .env.example                   # API key template
└── README.md                      # This file
```

---

## 🔄 Development Workflow

### With Task Master

```bash
# Get next task
task-master next

# Mark in progress
task-master set-status --id=<id> --status=in-progress

# Implement the task...

# Mark complete
task-master set-status --id=<id> --status=done
```

### Without Task Master

Standard development workflow:

```bash
# 1. Start environment
docker compose up -d

# 2. Access container
docker compose exec rdewai-dev bash

# 3. Develop and test
python your_script.py
pytest tests/

# 4. Validate
./scripts/test-environment.sh
```

---

## 📖 Common Commands

### Docker Commands

```bash
docker compose up -d              # Start services
docker compose down               # Stop services
docker compose ps                 # Container status
docker compose logs rdewai-dev    # View logs
docker compose exec rdewai-dev bash  # Access shell
docker compose build --no-cache   # Rebuild from scratch
```

### Development Commands (Inside Container)

```bash
pyspark                           # Start PySpark shell
pytest                            # Run tests
python -m pytest -v               # Verbose test output
superset db upgrade               # Initialize Superset
superset run -h 0.0.0.0          # Start Superset server
```

---

## 🔧 Troubleshooting

### Docker Issues

**Port already in use:**
```bash
# Find and kill process
lsof -i :8088
# Or change port in docker-compose.yml
```

**Container won't start / Memory error:**
```bash
# Increase Docker memory: Settings → Resources → 8GB+
# Clean up Docker system
docker system prune -a --volumes
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

**Build cache issues:**
```bash
docker compose build --no-cache --pull
```

### DevContainer Issues

**Won't connect:**
1. Install "Dev Containers" extension
2. Verify Docker Desktop is running
3. Rebuild: `Cmd/Ctrl+Shift+P` → "Rebuild Container"

### Task Master Issues

**API key errors:**
- Check `.env` file configuration
- Verify environment variables are loaded

**Model configuration:**
```bash
task-master models --setup
```

📖 See [Task Master docs](https://www.npmjs.com/package/task-master-ai) for detailed troubleshooting.

---

## 🎯 What's Installed

### Python Packages

- **Data Processing**: `pyspark`, `duckdb`, `sqlglot`
- **Cloud Integration**: `google-cloud-bigquery`, `google-cloud-storage`
- **Visualization**: `apache-superset`
- **Testing**: `pytest`

### Runtime Environment

- **Python**: 3.11.13
- **Java**: OpenJDK 11 (Eclipse Temurin)
- **PySpark**: 3.5.4
- **DuckDB**: Latest
- **Superset**: 4.1.1

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## 📄 License

This project is licensed under the MIT License.

---

## 📚 Additional Resources

- [Task Master AI Documentation](https://www.npmjs.com/package/task-master-ai)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
- [PySpark Documentation](https://spark.apache.org/docs/latest/api/python/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Apache Superset Documentation](https://superset.apache.org/docs/intro)

---

<div align="center">

**Built with ❤️ using Docker + AI Development Tools**

[⬆ Back to Top](#redefining-data-engineering-with-ai)

</div>
