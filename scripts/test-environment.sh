#!/bin/bash
# Test development environment setup

echo "Testing RDEWAI development environment..."
echo ""

echo "=== Python Version ==="
docker run --rm rdewai-dev:latest python --version

echo ""
echo "=== Java Version ==="
docker run --rm rdewai-dev:latest java -version

echo ""
echo "=== Installed Python Packages ==="
docker run --rm rdewai-dev:latest pip list | grep -E "pytest|pyspark|duckdb|google-cloud|superset|sqlglot"

echo ""
echo "=== PySpark Test ==="
docker run --rm rdewai-dev:latest python -c "from pyspark.sql import SparkSession; print('PySpark import successful')"

echo ""
echo "=== DuckDB Test ==="
docker run --rm rdewai-dev:latest python -c "import duckdb; print('DuckDB version:', duckdb.__version__)"

echo ""
echo "Environment test complete!"
