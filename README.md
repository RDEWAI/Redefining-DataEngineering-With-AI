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

# 2. Pull pre-built image and start Docker environment
docker compose pull
docker compose up -d

# 3. Verify installation
./scripts/test-environment.sh

# 4. Access the container
docker compose exec rdewai-dev bash
```

✅ **You're ready to start developing!**

---

## 💡 What This Project Provides

A pre-built containerized data engineering development environment with:

- **Python 3.11** + **Java 11** runtime
- **PySpark 3.5.4** for distributed data processing
- **DuckDB** for embedded analytics
- **Apache Superset 4.1.1** for data visualization
- **Google Cloud SDKs** (BigQuery, Cloud Storage)
- **Pre-built Docker image** from GitHub Container Registry

---

## 🐳 Docker Development Environment

### Prerequisites

- **Docker Desktop** 20.10+ ([download](https://www.docker.com/products/docker-desktop))
- **RAM**: 8GB minimum, 16GB recommended
- **Disk Space**: 10GB for images and volumes

### Starting Services

```bash
# Pull the pre-built image (first time or to get updates)
docker compose pull

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
├── .devcontainer/                 # VS Code DevContainer config
│   └── devcontainer.json
│
├── scripts/                       # Utility scripts
│   ├── test-environment.sh        # Quick environment test
│   └── comprehensive-validation.sh # Full validation suite
│
├── docker-compose.yml             # Container orchestration
├── Dockerfile                     # Image build (for reference)
├── requirements.txt               # Python dependencies
├── .env.example                   # API key template
└── README.md                      # This file
```

---

## 🔄 Development Workflow

```bash
# 1. Pull and start environment
docker compose pull
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
docker compose pull               # Pull latest pre-built image
docker compose up -d              # Start services
docker compose down               # Stop services
docker compose ps                 # Container status
docker compose logs rdewai-dev    # View logs
docker compose exec rdewai-dev bash  # Access shell
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
docker compose pull
docker compose up -d
```

**Image pull issues:**
```bash
# Pull the latest image manually
docker pull ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data
docker compose up -d
```

### DevContainer Issues

**Won't connect:**
1. Install "Dev Containers" extension
2. Verify Docker Desktop is running
3. Pull image manually: `docker compose pull`
4. Rebuild: `Cmd/Ctrl+Shift+P` → "Rebuild Container"

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

- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
- [PySpark Documentation](https://spark.apache.org/docs/latest/api/python/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Apache Superset Documentation](https://superset.apache.org/docs/intro)

---

<div align="center">

**Built with ❤️ using Docker + AI Development Tools**

[⬆ Back to Top](#redefining-data-engineering-with-ai)

</div>
