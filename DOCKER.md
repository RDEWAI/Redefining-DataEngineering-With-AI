# Docker Environment Documentation

## Architecture

This project uses a multi-stage Docker setup optimized for data engineering workflows.

### Base Image
- **Python**: 3.11-slim (Debian-based)
- **Java**: Eclipse Temurin 11 (OpenJDK)

### Key Components

#### 1. System Dependencies
- build-essential (gcc, g++, make)
- git
- curl, wget

#### 2. Python Packages
See `requirements.txt` for full list. Key packages:
- **PySpark 3.5.4**: Distributed data processing
- **DuckDB 1.1.3**: Embedded analytical database
- **Apache Superset 4.1.1**: Business intelligence platform
- **Google Cloud Libraries**: BigQuery and Cloud Storage integration
- **SQLGlot**: SQL parser and transpiler for cross-database compatibility

#### 3. Environment Variables
```bash
PYTHONUNBUFFERED=1              # Python output buffering
PYTHONDONTWRITEBYTECODE=1       # Disable .pyc files
SPARK_HOME=/usr/local/lib/python3.11/site-packages/pyspark
PYSPARK_PYTHON=python3
PYSPARK_DRIVER_PYTHON=python3
JAVA_HOME=/usr/lib/jvm/temurin-11-jdk-arm64
```

## Docker Compose Configuration

### Services
- **rdewai-dev**: Main development container

### Volumes
- `./` → `/workspace`: Project source code
- `rdewai-data`: Persistent data storage
- `rdewai-cache`: Python package cache

### Ports
- `8088`: Apache Superset web UI
- `4040`: Spark UI (active during Spark jobs)
- `8080`: General purpose port

### Health Checks
- Interval: 30 seconds
- Timeout: 10 seconds
- Start period: 10 seconds
- Retries: 3

## Build Optimization

### Layer Caching
Dockerfile is structured to maximize layer caching:
1. Base system dependencies (changes rarely)
2. Java installation (changes rarely)
3. Python package installation (changes with requirements.txt)
4. Application code (changes frequently)

### Image Size
- Base image: ~150MB
- With system deps: ~500MB
- Final image: ~3.5GB (including all Python packages)

### Build Time
- Cold build: ~5-10 minutes (depending on network)
- Cached build: ~30 seconds

## Usage Patterns

### Local Development
```bash
# Start with hot reload
docker-compose up

# Start detached
docker-compose up -d

# View logs
docker-compose logs -f rdewai-dev
```

### Running Commands
```bash
# Interactive shell
docker-compose exec rdewai-dev bash

# Run single command
docker-compose exec rdewai-dev python script.py

# Run PySpark
docker-compose exec rdewai-dev pyspark
```

### Data Persistence
- Project files: Bind mounted from host (live sync)
- Data files: Named volume `rdewai-data` (persists across restarts)
- Cache: Named volume `rdewai-cache` (speeds up package installs)

## Performance Tuning

### Memory Allocation
Docker Desktop settings:
- Minimum: 4GB RAM
- Recommended: 8GB RAM
- For large Spark jobs: 16GB+ RAM

### CPU Allocation
- Minimum: 2 cores
- Recommended: 4+ cores

### Spark Configuration
Set in environment or code:
```python
spark = SparkSession.builder \
    .config("spark.driver.memory", "4g") \
    .config("spark.executor.memory", "4g") \
    .getOrCreate()
```

## Troubleshooting

### Build Issues

#### Package conflicts
If you see dependency conflicts:
```bash
docker-compose build --no-cache
```

#### Network timeouts
Increase Docker daemon timeout in Docker Desktop settings.

### Runtime Issues

#### Out of memory
```bash
# Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory
```

#### Port conflicts
```bash
# Check what's using the port
lsof -i :8088

# Change port in docker-compose.yml
ports:
  - "8089:8088"  # Use 8089 on host instead
```

#### Permission issues
```bash
# Run as root (container default)
docker-compose exec rdewai-dev bash

# Or specify user
docker-compose exec -u 1000:1000 rdewai-dev bash
```

## Security Considerations

### Container Security
- Running as root (acceptable for local dev)
- No secrets in Dockerfile (use .env or docker-compose secrets)
- Base image from trusted source (python:3.11-slim)

### Network Security
- All services on bridge network (isolated from host)
- Only specified ports exposed to host
- No direct internet access from container (unless needed)

## Maintenance

### Updating Dependencies
```bash
# Update requirements.txt
# Rebuild image
docker-compose build --no-cache rdewai-dev

# Restart services
docker-compose up -d
```

### Cleaning Up
```bash
# Remove containers and networks
docker-compose down

# Remove volumes too
docker-compose down -v

# Remove unused Docker resources
docker system prune -a
```

## Best Practices

1. **Always use docker-compose** for consistent environments
2. **Pin package versions** in requirements.txt
3. **Use .dockerignore** to reduce build context
4. **Leverage layer caching** by ordering Dockerfile steps properly
5. **Monitor resource usage** with `docker stats`
6. **Regular cleanup** of unused images and volumes
